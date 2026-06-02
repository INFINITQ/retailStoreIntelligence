# You are writing the health check router for a FastAPI retail analytics API.

# FILE: app/routers/health.py

import json
from datetime import datetime, timezone

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import check_db_health, get_db
from app.models.db_models import Event
from app.models.schemas import HealthResponse, StoreHealth

router = APIRouter(tags=["health"])


def _load_store_ids() -> list[str]:
    """Load known store IDs from store_mapping.json."""
    try:
        with open(settings.store_mapping_path, "r", encoding="utf-8") as f:
            mapping = json.load(f)
        return [s["api_store_id"] for s in mapping.get("stores", [])]
    except Exception:
        return ["STORE_BLR_002"]


@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    now = datetime.now(timezone.utc)

    # DB health
    db_ok = await check_db_health()
    db_status = "ok" if db_ok else "error"

    # Redis health
    redis_ok = False
    try:
        client = aioredis.from_url(settings.redis_url, decode_responses=True)
        async with client:
            await client.ping()
        redis_ok = True
    except Exception:
        pass
    redis_status = "ok" if redis_ok else "error"

    # Per-store health
    store_ids = _load_store_ids()
    store_healths: list[StoreHealth] = []
    any_stale = False

    for store_id in store_ids:
        result = await db.execute(
            select(func.max(Event.timestamp)).where(Event.store_id == store_id)
        )
        last_ts = result.scalar_one_or_none()

        if last_ts is None:
            store_healths.append(
                StoreHealth(
                    store_id=store_id,
                    last_event_timestamp=None,
                    minutes_since_last_event=None,
                    status="NO_DATA",
                )
            )
        else:
            last_ts_aware = (
                last_ts.replace(tzinfo=timezone.utc) if last_ts.tzinfo is None else last_ts
            )
            minutes_since = (now - last_ts_aware).total_seconds() / 60
            if minutes_since >= settings.stale_feed_minutes:
                status = "STALE_FEED"
                any_stale = True
            else:
                status = "OK"

            store_healths.append(
                StoreHealth(
                    store_id=store_id,
                    last_event_timestamp=last_ts_aware.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    minutes_since_last_event=round(minutes_since, 2),
                    status=status,
                )
            )

    # Overall status
    if not db_ok or not redis_ok:
        overall = "UNHEALTHY"
    elif any_stale:
        overall = "DEGRADED"
    else:
        overall = "HEALTHY"

    return HealthResponse(
        status=overall,
        timestamp=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        database=db_status,
        redis=redis_status,
        stores=store_healths,
    )
