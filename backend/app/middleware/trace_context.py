"""
Trace Context Middleware — Task 2 Production Hardening

Extracts or generates a trace_id for every incoming HTTP request and
injects it into the thread-local logging context so that every log line
emitted during that request automatically carries the trace_id,
execution_id, and pipeline_stage fields.

Usage (registered in main.py):
    app.add_middleware(TraceContextMiddleware)
"""
from __future__ import annotations

import uuid

from app.logging_config import clear_trace_context, set_trace_context
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp


class TraceContextMiddleware(BaseHTTPMiddleware):
    """
    For every request:
      1. Read X-Trace-ID header if present, otherwise generate a UUID.
      2. Set it in the thread-local logging context.
      3. Inject X-Trace-ID into the response headers so callers can
         correlate their own logs.
      4. Clear the context after the response is sent.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        trace_id = request.headers.get("X-Trace-ID") or str(uuid.uuid4())
        set_trace_context(
            trace_id=trace_id,
            execution_id="",
            pipeline_stage="http_request",
        )
        try:
            response: Response = await call_next(request)
            response.headers["X-Trace-ID"] = trace_id
            return response
        finally:
            clear_trace_context()


__all__ = ["TraceContextMiddleware"]
