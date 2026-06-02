# You are writing the FastAPI application factory for a retail store CCTV analytics API.

# FILE: app/main.py

import json

import redis.asyncio as aioredis
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app

from app.database import async_engine, init_db
from app.middleware.logging import RequestLoggingMiddleware
from app.routers.events import router as events_router
from app.routers.health import router as health_router
from app.routers.stores import router as stores_router
from app.config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title="Store Intelligence API",
        version="1.0.0",
        description="Retail CCTV analytics API for Apex Retail",
    )

    # ── Middleware (outermost first) ──
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggingMiddleware)

    # ── Routers ──
    app.include_router(events_router)
    app.include_router(stores_router)
    app.include_router(health_router)

    # ── Startup / shutdown ──
    @app.on_event("startup")
    async def on_startup() -> None:
        await init_db()

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        await async_engine.dispose()

    # ── Prometheus metrics endpoint ──
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

    # ── Global exception handler ──
    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "trace_id": "see X-Trace-Id header",
            },
        )

    # ── WebSocket live metrics ──
    @app.websocket("/ws/stores/{store_id}/live")
    async def live_metrics_ws(websocket: WebSocket, store_id: str):
        await websocket.accept()
        redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
        pubsub = redis_client.pubsub()
        await pubsub.subscribe("store_events")

        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                try:
                    data = json.loads(message["data"])
                except (json.JSONDecodeError, TypeError):
                    continue
                # Forward only events for this store
                if data.get("store_id") == store_id:
                    await websocket.send_text(json.dumps(data))
        except WebSocketDisconnect:
            await pubsub.unsubscribe("store_events")
        except Exception:
            await pubsub.unsubscribe("store_events")
        finally:
            await redis_client.aclose()

    return app


app = create_app()

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
