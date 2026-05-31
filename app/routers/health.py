# You are writing the health check router for a FastAPI retail analytics API.

# FILE: app/routers/health.py
# PURPOSE: GET /health endpoint. Returns service status, DB/Redis connectivity,
# last event timestamp per store, and STALE_FEED warnings.

# TECH: Python 3.11, fastapi, sqlalchemy.ext.asyncio, redis.asyncio

# IMPLEMENT:

# 1. `router = APIRouter(tags=["health"])`

# 2. `@router.get("/health", response_model=HealthResponse)`
#    `async def health_check(db: AsyncSession = Depends(get_db)) -> HealthResponse:`
#    - Check DB health: result = await check_db_health() from app.database.
#    - Check Redis health: ping Redis via redis.asyncio.from_url(settings.redis_url).ping();
#      wrap in try/except.
#    - For each known store_id (load from store_layout.json via settings.store_layout_path):
#      - Query max(events.timestamp) WHERE store_id = X.
#      - Compute minutes_since_last_event.
#      - status = "OK" if < stale_feed_minutes, "STALE_FEED" if >= stale_feed_minutes,
#        "NO_DATA" if no events found.
#    - Determine overall status:
#      - "UNHEALTHY" if DB or Redis is down.
#      - "DEGRADED" if any store is STALE_FEED.
#      - "HEALTHY" otherwise.
#    - Return HealthResponse(...).
#    - This endpoint must always return 200. Status is conveyed in the body, not HTTP code.

# IMPORTS NEEDED:
#   fastapi (APIRouter, Depends), sqlalchemy.ext.asyncio (AsyncSession), sqlalchemy (select, func),
#   redis.asyncio, datetime (datetime, timezone), json,
#   app.database (get_db, check_db_health), app.models.db_models (Event),
#   app.models.schemas (HealthResponse, StoreHealth), app.config (settings)
