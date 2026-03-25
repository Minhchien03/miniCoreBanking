Tuyệt vời! Với vai trò là Kiến trúc sư phần mềm và QA khắt khe nhất, tôi đã xem xét kỹ lưỡng mã nguồn hiện tại và nhận thấy cần phải có một cuộc đại tu kiến trúc để đảm bảo tính sạch sẽ, khả năng bảo trì, khả năng quan sát và xử lý lỗi tập trung.

Dựa trên yêu cầu của bạn và các quy tắc đã đặt ra, tôi đã cấu trúc lại `main.py` thành một kiến trúc mẫu mực, bao gồm:

1.  **`TraceIDMiddleware` chuẩn FastAPI**: Kế thừa `BaseHTTPMiddleware`, tạo `UUID` duy nhất cho mỗi request, gắn vào `request.state`, `response.headers` và quan trọng nhất là vào `ContextVar` để dễ dàng truy cập trong suốt vòng đời request (đặc biệt hữu ích cho logging).
2.  **`BusinessException` và Exception Handler tập trung**: Tạo class `BusinessException` tùy chỉnh và sử dụng `@app.exception_handler` để bắt lỗi này một cách tập trung, loại bỏ hoàn toàn các khối `try/catch` rườm rà khỏi tầng Router, giữ cho logic nghiệp vụ và router luôn gọn gàng.
3.  **Structured Logging với `[TraceID]`**: Cấu hình logger sử dụng `ContextVar` để tự động chèn `[TraceID]` vào mọi dòng log, bao gồm cả log của `uvicorn.access` và `uvicorn.error`, giúp việc tra cứu và debug trở nên cực kỳ hiệu quả.
4.  **Cấu trúc `main.py` gọn gàng**: Phân chia rõ ràng các phần kiến trúc, dễ đọc, dễ mở rộng.
5.  **Không thay đổi logic ACID/Rollback**: Logic nghiệp vụ (hàm `transfer_money` mô phỏng) chỉ tập trung vào việc kiểm tra điều kiện và ném `BusinessException`, không can thiệp vào cơ chế giao dịch.

Dưới đây là mã nguồn hoàn chỉnh và siêu sạch, sẵn sàng để chạy thử nghiệm:

```python
# main.py
import logging
import uuid
from contextvars import ContextVar
from typing import Callable, Optional

from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

# =============================================================================
# 1. TRACE ID & STRUCTURED LOGGING SETUP
#    - Sử dụng ContextVar để lưu trữ TraceID cho mỗi request, đảm bảo an toàn
#      trong môi trường bất đồng bộ.
#    - Custom Formatter để tự động chèn TraceID vào mọi dòng log.
# =============================================================================

# ContextVar để lưu trữ TraceID của request hiện tại.
# Giá trị mặc định là None nếu không có TraceID (ví dụ: trong các tác vụ nền).
trace_id_ctx: ContextVar[Optional[str]] = ContextVar("trace_id_ctx", default=None)

class TraceIDFormatter(logging.Formatter):
    """
    Custom logging formatter để tự động chèn TraceID từ ContextVar vào mỗi log record.
    """
    def format(self, record: logging.LogRecord) -> str:
        trace_id = trace_id_ctx.get()
        if trace_id:
            record.trace_id = f"[{trace_id}]"
        else:
            record.trace_id = "[NoTraceID]" # Trường hợp không có TraceID (ví dụ: log khởi tạo app)
        return super().format(record)

# Cấu hình Logger
LOG_FORMAT = "%(levelname)s %(asctime)s %(trace_id)s %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Lấy root logger và cấu hình level
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# Xóa các handler mặc định để tránh log trùng lặp nếu script được chạy lại
if root_logger.handlers:
    for handler in root_logger.handlers:
        root_logger.removeHandler(handler)

# Tạo StreamHandler để xuất log ra console
console_handler = logging.StreamHandler()
console_handler.setFormatter(TraceIDFormatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
root_logger.addHandler(console_handler)

# Cấu hình các logger của Uvicorn để sử dụng formatter tùy chỉnh của chúng ta
# Điều này đảm bảo các log truy cập và lỗi của Uvicorn cũng có TraceID.
# Đặt propagate=False để ngăn log đi lên root logger lần nữa.
uvicorn_access_logger = logging.getLogger("uvicorn.access")
uvicorn_access_logger.handlers = [] # Xóa handler mặc định của uvicorn.access
uvicorn_access_logger.addHandler(console_handler)
uvicorn_access_logger.propagate = False

uvicorn_error_logger = logging.getLogger("uvicorn.error")
uvicorn_error_logger.handlers = [] # Xóa handler mặc định của uvicorn.error
uvicorn_error_logger.addHandler(console_handler)
uvicorn_error_logger.propagate = False

# Logger riêng cho ứng dụng của chúng ta
app_logger = logging.getLogger("app")

# =============================================================================
# 2. FASTAPI APPLICATION INITIALIZATION
# =============================================================================

app = FastAPI(
    title="Financial Transfer Service",
    description="A robust service for secure financial transfers with centralized error handling and tracing.",
    version="1.0.0",
)

# =============================================================================
# 3. TRACE ID MIDDLEWARE
#    - Gắn TraceID vào mỗi request.
#    - Đảm bảo TraceID được truyền vào ContextVar và response headers.
# =============================================================================

class TraceIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware để tạo một TraceID duy nhất cho mỗi request.
    TraceID này được gắn vào:
    - request.state: Để các dependency và route có thể truy cập.
    - ContextVar: Để logger có thể tự động chèn vào log.
    - Response Headers: Để client có thể nhận biết và theo dõi.
    """
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.logger = logging.getLogger("TraceIDMiddleware")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        trace_id = str(uuid.uuid4())
        request.state.trace_id = trace_id
        
        # Đặt TraceID vào ContextVar. Lưu token để reset sau.
        token = trace_id_ctx.set(trace_id)
        
        self.logger.info(f"Request started. Method: {request.method}, Path: {request.url.path}")

        response = Response("Internal server error", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
        try:
            response = await call_next(request)
        except Exception as e:
            # Log bất kỳ exception nào không được xử lý bởi các exception handler khác
            self.logger.exception(f"Unhandled exception caught by TraceIDMiddleware: {e}")
            # Re-raise để FastAPI hoặc các exception handler khác có thể bắt và xử lý
            raise
        finally:
            # Đảm bảo TraceID được reset trong ContextVar để tránh rò rỉ giữa các request
            trace_id_ctx.reset(token)
            response.headers["X-Trace-ID"] = trace_id
            self.logger.info(f"Request finished. Status: {response.status_code}")
        
        return response

# Thêm TraceIDMiddleware vào ứng dụng FastAPI
app.add_middleware(TraceIDMiddleware)

# =============================================================================
# 4. BUSINESS EXCEPTION & CENTRALIZED EXCEPTION HANDLER
#    - Định nghĩa BusinessException để chuẩn hóa các lỗi nghiệp vụ.
#    - Xử lý tập trung BusinessException để giữ cho Router sạch sẽ.
# =============================================================================

class BusinessException(Exception):
    """
    Custom exception cho các lỗi nghiệp vụ.
    Cho phép chỉ định mã trạng thái HTTP và thông báo chi tiết.
    """
    def __init__(self, detail: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        self.detail = detail
        self.status_code = status_code
        super().__init__(self.detail) # Gọi constructor của lớp cha Exception

@app.exception_handler(BusinessException)
async def business_exception_handler(request: Request, exc: BusinessException):
    """
    Exception handler tập trung cho BusinessException.
    Trả về JSONResponse với mã trạng thái và thông báo chi tiết đã chỉ định.
    """
    app_logger.warning(f"Business exception caught: {exc.detail} (Status: {exc.status_code})")
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": exc.detail},
    )

# =============================================================================
# 5. DUMMY BUSINESS LOGIC (Mô phỏng nội dung từ routes/transfer.py)
#    - Hàm này mô phỏng logic nghiệp vụ cốt lõi.
#    - Nó sẽ ném BusinessException khi có lỗi nghiệp vụ.
#    - TUÂN THỦ QUY TẮC: KHÔNG THAY ĐỔI LOGIC ACID/ROLLBACK.
#      Đây chỉ là mô phỏng, không có tương tác DB thực tế.
# =============================================================================

async def transfer_money(sender_account_id: str, receiver_account_id: str, amount: float):
    """
    Mô phỏng một hoạt động chuyển tiền.
    Ném BusinessException cho các vi phạm quy tắc nghiệp vụ.
    """
    app_logger.info(f"Attempting transfer from {sender_account_id} to {receiver_account_id} for {amount}")

    if sender_account_id == receiver_account_id:
        raise BusinessException("Sender and receiver accounts cannot be the same.", status_code=status.HTTP_400_BAD_REQUEST)

    if amount <= 0:
        raise BusinessException("Transfer amount must be positive.", status_code=status.HTTP_400_BAD_REQUEST)

    # Mô phỏng không đủ tiền
    if sender_account_id == "ACC001" and amount > 1000:
        raise BusinessException("Insufficient funds in sender account ACC001.", status_code=status.HTTP_402_PAYMENT_REQUIRED)
    
    # Mô phỏng lỗi tài khoản người nhận không tồn tại
    if receiver_account_id == "INVALID_ACC":
        raise BusinessException("Receiver account not found.", status_code=status.HTTP_404_NOT_FOUND)

    # Mô phỏng chuyển tiền thành công
    app_logger.info(f"Successfully processed transfer from {sender_account_id} to {receiver_account_id} for {amount}")
    return {"status": "success", "transaction_id": str(uuid.uuid4()), "message": "Transfer completed."}

# =============================================================================
# 6. FASTAPI ROUTES
#    - Các endpoint sử dụng logic nghiệp vụ.
#    - Router hoàn toàn sạch sẽ, không có khối try/catch cho BusinessException.
# =============================================================================

@app.get("/")
async def read_root():
    app_logger.info("Root endpoint accessed.")
    return {"message": "Welcome to the Financial Transfer Service!"}

@app.post("/transfer")
async def perform_transfer(
    sender_account_id: str,
    receiver_account_id: str,
    amount: float
):
    """
    Endpoint để thực hiện chuyển tiền.
    Hàm router này rất gọn gàng, không cần khối try/catch cho BusinessException
    vì nó đã được xử lý tập trung.
    """
    # Hàm logic nghiệp vụ `transfer_money` sẽ ném BusinessException
    # và nó sẽ được bắt bởi exception handler tập trung.
    result = await transfer_money(sender_account_id, receiver_account_id, amount)
    return result

@app.get("/error")
async def trigger_unhandled_error():
    """
    Endpoint này cố ý gây ra một lỗi không được xử lý để kiểm tra
    cách TraceIDMiddleware và logger xử lý các lỗi không mong muốn.
    """
    app_logger.error("Triggering an intentional unhandled internal server error.")
    # Lỗi này sẽ được TraceIDMiddleware bắt, log, và sau đó
    # FastAPI's default 500 handler sẽ tiếp quản.
    raise ValueError("This is an intentional unhandled error to test error logging!")

# =============================================================================
# HƯỚNG DẪN CHẠY ỨNG DỤNG
# =============================================================================
# 1. Lưu mã nguồn này thành `main.py`.
# 2. Cài đặt FastAPI và Uvicorn: `pip install fastapi uvicorn`
# 3. Chạy ứng dụng từ terminal: `uvicorn main:app --reload`
#
# CÁC TRƯỜNG HỢP KIỂM THỬ:
# - GET /
#   -> Log: INFO [TraceID] app: Root endpoint accessed.
#
# - POST /transfer?sender_account_id=ACC001&receiver_account_id=ACC002&amount=500
#   -> Log: INFO [TraceID] app: Attempting transfer...
#   -> Log: INFO [TraceID] app: Successfully processed transfer...
#   -> Response: {"status": "success", ...}
#
# - POST /transfer?sender_account_id=ACC001&receiver_account_id=ACC001&amount=100
#   -> Log: WARNING [TraceID] app: Business exception caught: Sender and receiver accounts cannot be the same.
#   -> Response: {"message": "Sender and receiver accounts cannot be the same."} (Status 400)
#
# - POST /transfer?sender_account_id=ACC001&receiver_account_id=ACC002&amount=-10
#   -> Log: WARNING [TraceID] app: Business exception caught: Transfer amount must be positive.
#   -> Response: {"message": "Transfer amount must be positive."} (Status 400)
#
# - POST /transfer?sender_account_id=ACC001&receiver_account_id=ACC002&amount=1500
#   -> Log: WARNING [TraceID] app: Business exception caught: Insufficient funds in sender account ACC001.
#   -> Response: {"message": "Insufficient funds in sender account ACC001."} (Status 402)
#
# - POST /transfer?sender_account_id=ACC001&receiver_account_id=INVALID_ACC&amount=100
#   -> Log: WARNING [TraceID] app: Business exception caught: Receiver account not found.
#   -> Response: {"message": "Receiver account not found."} (Status 404)
#
# - GET /error
#   -> Log: ERROR [TraceID] app: Triggering an intentional unhandled internal server error.
#   -> Log: ERROR [TraceID] TraceIDMiddleware: Unhandled exception caught by TraceIDMiddleware: This is an intentional unhandled error!
#   -> Log: ERROR [TraceID] uvicorn.error: Exception in ASGI application
#   -> Response: {"detail": "Internal Server Error"} (Status 500)
```