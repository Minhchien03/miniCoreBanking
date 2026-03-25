import logging
import uvicorn # Đã bổ sung import

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError # Import thêm lỗi mặc định
from starlette.exceptions import HTTPException as StarletteHTTPException # Import thêm lỗi mặc định
from starlette.responses import JSONResponse

from config import configure_logging
from middleware import TraceIDMiddleware
from exceptions import BusinessException
from routers import core_banking

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Core Banking API",
    description="Simple Core Banking System with ACID transactions, TraceID, and Centralized Exception Handling.",
    version="1.0.0",
)

app.add_middleware(TraceIDMiddleware)

# Handle Exceptions
@app.exception_handler(BusinessException)
async def business_exception_handler(request: Request, exc: BusinessException):
    # Lấy trace_id trực tiếp từ request, an toàn tuyệt đối 100%
    current_trace_id = getattr(request.state, "trace_id", "UNKNOWN")
    logger.warning(f"Business Exception caught: {exc.detail}", extra={"trace_id": current_trace_id})
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "trace_id": current_trace_id},
        headers=exc.headers,
    )

# Catch FastAPI error 422 separately to avoid being swallowed as 500
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    current_trace_id = getattr(request.state, "trace_id", "UNKNOWN")
    logger.warning(f"Data Validation Error: {exc.errors()}", extra={"trace_id": current_trace_id})
    return JSONResponse(
        status_code=422,
        content={"detail": "Invalid input data", "errors": exc.errors(), "trace_id": current_trace_id},
    )

# error 500 internal server error
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    current_trace_id = getattr(request.state, "trace_id", "UNKNOWN")
    logger.exception("Unhandled Exception caught", extra={"trace_id": current_trace_id}) 
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error", "trace_id": current_trace_id},
        headers={"X-Trace-ID": current_trace_id} # Đảm bảo TraceID luôn được trả về header khi lỗi xảy ra
    )

# API routers
app.include_router(core_banking.router, prefix="/api") 

@app.get("/", include_in_schema=False)
async def root():
    return {"message": "Welcome to Core Banking API! Visit /docs for API documentation."}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_config=None)