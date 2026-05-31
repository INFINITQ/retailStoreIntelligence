# You are writing the structured logging middleware for a FastAPI retail analytics API.

# FILE: app/middleware/logging.py
# PURPOSE: ASGI middleware that injects a UUID trace_id into every request context,
# logs structured request/response metadata using structlog, and ensures all 500 errors
# return a clean JSON body (no raw stack traces).

# TECH: Python 3.11, fastapi, starlette, structlog==24.4.0, uuid

# IMPLEMENT:

# 1. At module level, configure structlog:
#    - Processors: add_log_level, add_timestamp (ISO format), structlog.stdlib.PositionalArgumentsFormatter,
#      structlog.processors.StackInfoRenderer, structlog.dev.ConsoleRenderer in development,
#      structlog.processors.JSONRenderer in production.
#    - Read environment from app.config.settings.environment.
#    - Bind trace_id to a context variable using structlog.contextvars.

# 2. `class RequestLoggingMiddleware(BaseHTTPMiddleware):`

#    `async def dispatch(self, request: Request, call_next) -> Response:`
#    - Generate trace_id = str(uuid.uuid4()).
#    - Extract store_id from path params if present (check request.path_params.get("store_id")).
#    - Bind structlog context: structlog.contextvars.bind_contextvars(
#        trace_id=trace_id, store_id=store_id, path=request.url.path,
#        method=request.method, client_ip=request.client.host if request.client else "unknown")
#    - Record start = time.perf_counter().
#    - Call call_next(request) in try/except:
#      - On unhandled exception: log error with exc_info, return JSONResponse(status_code=500,
#        content={"error": "Internal server error", "trace_id": trace_id})
#    - After response: compute latency_ms = round((time.perf_counter()-start)*1000, 2).
#    - Log structured info: trace_id, store_id, endpoint=request.url.path,
#      method=request.method, status_code=response.status_code, latency_ms=latency_ms.
#    - Add X-Trace-Id header to response.
#    - Clear structlog context after response.
#    - Return response.

# 3. `def get_logger(name: str = __name__):`
#    - Returns structlog.get_logger(name).

# IMPORTS NEEDED:
#   fastapi (Request), fastapi.responses (JSONResponse), starlette.middleware.base (BaseHTTPMiddleware),
#   starlette.responses (Response), structlog, structlog.contextvars, uuid, time,
#   app.config (settings)
