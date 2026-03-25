import os
from crewai import Agent, Task, Crew, Process
from langchain_google_genai import ChatGoogleGenerativeAI
from crewai_tools import FileReadTool

file_read_tool = FileReadTool()

# Đặt temperature = 0.1 để AI trả lời chính xác
gemini_llm = ChatGoogleGenerativeAI(
    temperature=0.1, 
    model="gemini/gemini-2.5-flash",
    google_api_key=os.getenv("GEMINI_API_KEY")

)

backend_dev = Agent(
    role='Senior Backend Developer',
    goal='Review và tối ưu hóa logic các API (Create Account, Deposit, Transfer) dựa trên PostgreSQL và SQLAlchemy Async.',
    backstory='''Bạn là một lập trình viên Backend kỳ cựu chuyên làm Fintech. 
    QUY TẮC (BẠN PHẢI TUÂN THỦ TUYỆT ĐỐI):
    1. Đọc kỹ code hiện tại
    2. Kiểm tra chặt chẽ tính ACID. Đảm bảo mọi thao tác chuyển tiền nằm trong khối `async with session.begin():`.
    2. Bắt buộc dùng `decimal.Decimal` cho mọi biến liên quan đến tiền tệ. TUYỆT ĐỐI KHÔNG dùng `float`.
    3. Bảng Account không được có cột balance. Bảng LedgerEntries là append-only.
    4. Code sinh ra phải là một file hoàn chỉnh, có thể copy/paste để chạy được ngay với Uvicorn.
    ''',
    verbose=True,
    tools=[file_read_tool], # Cấp quyền đọc file
    llm=gemini_llm
)

system_architect = Agent(
    role='System Architect & Quality Assurance',
    goal='Refactor code của Backend Dev, áp dụng Clean Code, Centralized Exception Handling, TraceID Middleware và Structured Logging.',
    backstory='''Bạn là kiến trúc sư phần mềm khắt khe nhất thế giới. 
    QUY TẮC (BẠN PHẢI TUÂN THỦ TUYỆT ĐỐI):
    1. Không làm thay đổi logic ACID/Rollback của Dev.
    2. Phải viết một lớp `TraceIDMiddleware` chuẩn của FastAPI (kế thừa BaseHTTPMiddleware).
    3. Phải tạo class `BusinessException` và dùng `@app.exception_handler` để bắt lỗi tập trung, dọn sạch mọi khối `try/catch` thừa thãi ở tầng Router.
    4. Cấu hình logger xuất ra chuỗi có chứa [TraceID] để dễ dàng tra cứu.
    ''',
    verbose=True,
    allow_delegation=False,
    llm=gemini_llm
)

# ==========================================
# 2. KHỞI TẠO TASKS VỚI EXPECTED OUTPUT RÕ RÀNG
# ==========================================

develop_api_task = Task(
    description='''
        Sử dụng FileReadTool để đọc các file: `models.py`, `database.py`, và `routes/transfer.py`.
        
        Nhiệm vụ:
        1. Đánh giá logic hiện tại của 3 API: POST /accounts, POST /deposit, POST /transfer.
        2. Xác nhận cơ sở dữ liệu đang cấu hình chuẩn cho PostgreSQL (SQLAlchemy Async).
        3. Kiểm tra Flow của API Transfer: Tính tổng balance từ ledger -> Check số dư -> Insert transaction -> Insert 2 dòng ledger.
        4. Tinh chỉnh lại code (nếu cần) để đảm bảo chuẩn mực nhất, tự động Rollback nếu có lỗi.
    ''',
    expected_output='Một bản báo cáo chỉ ra các điểm cần tối ưu trong logic database/API hiện tại, kèm theo đoạn code đã được làm sạch (refactored) cho file `routes/transfer.py`.',
    agent=backend_dev,
    output_file='Backend.md'
)

refactor_quality_task = Task(
    description='''
        Sử dụng FileReadTool để đọc file `main.py`. Nhận kết quả từ Backend Developer để tích hợp.
        
        Nhiệm vụ:
        1. Cấu trúc lại file `main.py` để code gọn gàng nhất.
        2. Viết mã nguồn cho `TraceIDMiddleware` (nếu chưa có hoặc chưa chuẩn) để gắn UUID cho mọi request.
        3. Viết mã nguồn cho `BusinessException` và Exception Handler tập trung.
        4. Đảm bảo Logger được cấu hình xuất ra chuỗi có chứa `[TraceID]`.
    ''',
    expected_output='Mã nguồn hoàn chỉnh và siêu sạch cho các thành phần kiến trúc: `main.py`, Middleware và Exception. Sẵn sàng để chạy thử nghiệm.',
    agent=system_architect,
    output_file='Architect.md'
)


banking_crew = Crew(
    agents=[backend_dev, system_architect],
    tasks=[develop_api_task, refactor_quality_task],
    process=Process.sequential # Dev viết core logic -> Architect bọc Middleware và Logging xung quanh
)

if __name__ == "__main__":
    print("🚀 Bắt đầu quét và Refactor hệ thống Core Banking...")
    result = banking_crew.kickoff()
    print("✅ KẾT QUẢ REFATOR:")
    print(result)