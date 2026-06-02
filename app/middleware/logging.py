# You are writing the structured logging middleware for a FastAPI retail analytics API.

# FILE: app/middleware/logging.py
# PURPOSE: ASGI middleware that injects a UUID trace_id into every request context,
# logs structured request/response metadata using structlog, and ensures all 500 errors
# return a clean JSON body (no raw stack traces).

import time
import uuid

import structlog
import structlog.contextvars
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.config import settings

# ---------------------------------------------------------------------------
# Configure structlog once at module import time
# ---------------------------------------------------------------------------
_shared_processors = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.stdlib.PositionalArgumentsFormatter(),
    structlog.processors.StackInfoRenderer(),
]

if settings.environment == "production":
    _final_processor = structlog.processors.JSONRenderer()
else:
    _final_processor = structlog.dev.ConsoleRenderer()

structlog.configure(
    processors=_shared_processors + [_final_processor],
    wrapper_class=structlog.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        trace_id = str(uuid.uuid4())
        store_id = request.path_params.get("store_id", None)

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            trace_id=trace_id,
            store_id=store_id,
            path=request.url.path,
            method=request.method,
            client_ip=request.client.host if request.client else "unknown",
        )

        start = time.perf_counter()
        log = structlog.get_logger(__name__)

        try:
            response = await call_next(request)
        except Exception as exc:
            log.error("Unhandled exception", exc_info=exc)
            structlog.contextvars.clear_contextvars()
            return JSONResponse(
                status_code=500,
                content={"error": "Internal server error", "trace_id": trace_id},
            )

        latency_ms = round((time.perf_counter() - start) * 1000, 2)

        log.info(
            "request_handled",
            trace_id=trace_id,
            store_id=store_id,
            endpoint=request.url.path,
            method=request.method,
            status_code=response.status_code,
            latency_ms=latency_ms,
        )

        response.headers["X-Trace-Id"] = trace_id
        structlog.contextvars.clear_contextvars()
        return response


def get_logger(name: str = __name__):
    return structlog.get_logger(name)
