import logging
import sys
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

from routes.transfer import router as transfer_router
from contextvars import ContextVar


# CORRELATION ID CONTEXT CONFIGURATION
# 1. create a context variable to hold the correlation ID for each request
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="SYSTEM")


# 2. create a filter to automation add correlation ID to log records
class CorrelationIdFilter(logging.Filter):
    def filter(self, record):
        record.correlation_id = correlation_id_var.get()
        return True


# Global logger configuration
# logging.basicConfig(
#     level=logging.INFO,
#     format="%(asctime)s | %(levelname)-8s | [%(correlation_id)s] | %(name)s | %(message)s",
#     datefmt="%Y-%m-%d %H:%M:%S",
#     handlers=[
#         logging.FileHandler("app.log", encoding="utf-8"),
#         logging.StreamHandler(sys.stdout)
#     ]
# )
# logging.getLogger().addFilter(CorrelationIdFilter())

# ------------------------------------------------

# configure formatter and handlers
formatter = logging.Formatter(
    "%(asctime)s | %(levelname)-8s | [%(correlation_id)s] | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
correlation_filter = CorrelationIdFilter()

# console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
console_handler.addFilter(correlation_filter)

# file handler
file_handler = logging.FileHandler("app.log", encoding="utf-8")
file_handler.setFormatter(formatter)
file_handler.addFilter(correlation_filter)

# root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# delete default handlers
if root_logger.hasHandlers():
    root_logger.handlers.clear()

root_logger.addHandler(console_handler)
root_logger.addHandler(file_handler)

# # Force uvicorn loggers to use the same handlers and filters as our root logger
# logging.getLogger("uvicorn").handlers = root_logger.handlers
# logging.getLogger("uvicorn.access").handlers = root_logger.handlers

logger = logging.getLogger(__name__)

app = FastAPI(title="Mini Core Banking API")


@app.middleware("http")
async def add_correlation_id(request, call_next):
    request_id = str(uuid.uuid4())

    # save request ID in context variable
    token = correlation_id_var.set(request_id)

    # save into state of request for later use in route handlers
    request.state.correlation_id = request_id

    logger.info(f"Received request: {request.method} {request.url}")

    try:
        # push request into transfer.py function
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = request_id
        logger.info(f"Sent response: {response.status_code}")

        correlation_id_var.reset(token)
        return response

    except Exception as e:
        logger.error(f"Error processing request: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal Server Error",
                "message": "An unexpected error occurred. Please try again later.",
                "trace_id": request_id,
            },
            headers={"X-Correlation-ID": request_id},
        )

    finally:
        correlation_id_var.reset(token)


# Centralized router registration
@app.exception_handler(Exception)
# Global exception handler to catch unhandled exceptions and log them with correlation ID
async def global_exception_handler(request: Request, exc: Exception):
    # get ID of error request
    correlation_id = getattr(request.state, "correlation_id", "UNKNOWN")

    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred. Please try again later.",
            "trace_id": correlation_id,
        },
    )


app.include_router(transfer_router)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_config=None)