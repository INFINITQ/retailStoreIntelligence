# You are writing the FastAPI application factory for a retail store CCTV analytics API.

# FILE: app/main.py
# PURPOSE: Create and configure the FastAPI app. Register middleware, routers, startup/shutdown
# events, WebSocket endpoint for live dashboard, Prometheus metrics, and global error handlers.

# TECH: Python 3.11, fastapi==0.115.4, uvicorn, starlette, redis.asyncio, prometheus_client

# IMPLEMENT:

# 1. `def create_app() -> FastAPI:`
#    - Create FastAPI(title="Store Intelligence API", version="1.0.0",
#                     description="Retail CCTV analytics API for Apex Retail").
#    - Add middleware (in this order, outermost first):
#      a. CORSMiddleware: allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
#      b. RequestLoggingMiddleware (from app.middleware.logging)
#    - Include routers: events_router (/events), stores_router (/stores), health_router (no prefix).
#    - Register startup event: call await init_db().
#    - Register shutdown event: dispose async_engine.
#    - Add Prometheus metrics endpoint at /metrics using prometheus_client.make_asgi_app().
#      Mount it: app.mount("/metrics", make_asgi_app())
#    - Add global exception handler for Exception → JSONResponse(500,
#      {"error": "Internal server error", "trace_id": "see X-Trace-Id header"}).
#    - Return app.

# 2. `@app.websocket("/ws/stores/{store_id}/live")`
#    `async def live_metrics_ws(websocket: WebSocket, store_id: str):`
#    - Accept the WebSocket connection.
#    - Subscribe to Redis pub/sub channel "store_events".
#    - In an async loop: listen for messages; if message is for store_id, forward to WebSocket.
#    - Handle WebSocketDisconnect gracefully (unsubscribe, log).
#    - Messages sent to client are JSON strings.

# 3. `app = create_app()` at module level.

# 4. `if __name__ == "__main__": uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)`

# IMPORTS NEEDED:
#   fastapi (FastAPI, WebSocket, WebSocketDisconnect), fastapi.middleware.cors (CORSMiddleware),
#   fastapi.responses (JSONResponse), prometheus_client (make_asgi_app),
#   redis.asyncio, uvicorn, json,
#   app.database (init_db, async_engine),
#   app.routers.events (router as events_router),
#   app.routers.stores (router as stores_router),
#   app.routers.health (router as health_router),
#   app.middleware.logging (RequestLoggingMiddleware),
#   app.config (settings)
