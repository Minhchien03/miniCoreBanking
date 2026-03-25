import uuid
from contextvars import ContextVar
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from typing import Callable, Awaitable, Optional

# ContextVar to store the trace_id for the current request context.
# This allows the trace_id to be accessed by loggers anywhere in the request's call stack.
trace_id_context: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)

class TraceIDMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware to generate and manage a unique TraceID for each incoming request.
    - Generates a UUID for each request.
    - Stores the TraceID in `request.state.trace_id` for direct access within endpoints.
    - Sets the TraceID in a `ContextVar` (`trace_id_context`) for structured logging.
    - Adds the TraceID to the response headers as `X-Trace-ID`.
    """
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        # Generate a unique TraceID for the request
        trace_id = str(uuid.uuid4())
        request.state.trace_id = trace_id # Store in request state

        # Set the trace_id in the ContextVar.
        # Store the token to reset the ContextVar properly later.
        token = trace_id_context.set(trace_id)

        try:
            # Process the request
            response = await call_next(request)
            # Add the TraceID to the response headers
            response.headers["X-Trace-ID"] = trace_id
        finally:
            # Ensure the ContextVar is reset to its previous state (or default)
            # This is crucial to prevent trace_id leakage across different requests in an async environment.
            trace_id_context.reset(token)
        return response