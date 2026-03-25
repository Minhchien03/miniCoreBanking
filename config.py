import logging
from middleware import trace_id_context # Import ContextVar from middleware

class TraceIDFormatter(logging.Formatter):
    """
    Custom formatter to inject TraceID into log records.
    It retrieves the trace_id from the ContextVar managed by TraceIDMiddleware.
    """
    def format(self, record):
        trace_id = trace_id_context.get()
        if trace_id:
            record.trace_id_str = f"[{trace_id}]"
        else:
            record.trace_id_str = ""
        return super().format(record)

def configure_logging():
    """
    Configures the root logger to use the custom TraceIDFormatter
    and output logs to BOTH the console and the app.log file.
    """
    # Define the log format, including the custom 'trace_id_str' attribute
    log_format = "%(levelname)s:     %(asctime)s %(trace_id_str)s %(name)s - %(message)s"
    formatter = TraceIDFormatter(log_format)

    # 1. Create a stream handler (outputs to console/terminal)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # 2. Create a file handler (outputs to app.log file)
    file_handler = logging.FileHandler("app.log", encoding="utf-8")
    file_handler.setFormatter(formatter)

    # Get the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO) # Set default logging level
    
    # Xóa các handler hiện có để tránh log bị lặp đúp khi FastAPI reload
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
        
    # Thêm CẢ HAI handler vào root logger
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Optional: Suppress uvicorn access logs to avoid duplicate or unformatted logs
    # Uvicorn's default access logs don't play well with custom formatters easily.
    # We can re-add them with our formatter if needed, but for simplicity, we disable them here.
    logging.getLogger("uvicorn.access").handlers = []
    logging.getLogger("uvicorn.access").propagate = False
    
    # Ensure uvicorn error logs still propagate
    logging.getLogger("uvicorn.error").propagate = True

    logging.info("Logging configured with TraceID support. Outputting to console and app.log")