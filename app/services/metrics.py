# You are writing the metrics computation service for a retail store CCTV analytics API.

# FILE: app/services/metrics.py
# PURPOSE: Compute real-time store metrics for GET /stores/{id}/metrics.

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.db_models import Event, POSTransaction, VisitorSession
from app.models.schemas import MetricsResponse, ZoneDwell


def _load_zone_display_names(layout_path: str) -> dict[str, str]:
    """Return mapping {zone_id: display_name} from store_layout.json."""
    try:
        with open(layout_path, "r", encoding="utf-8") as f:
            layout = json.load(f)
        return {z["zone_id"]: z.get("display_name", z["zone_id"]) for z in layout.get("zones", [])}
    except Exception:
        return {}


async def compute_metrics(
    db: AsyncSession, store_id: str, window_hours: int = 24
) -> MetricsResponse:
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=window_hours)

    # Auto-adjust window: if no events fall in the live window, expand to
    # cover the actual event range so historical data is always visible.
    from sqlalchemy import exists as sa_exists
    has_events = await db.execute(
        select(func.count(Event.id)).where(
            and_(
                Event.store_id == store_id,
                Event.timestamp >= window_start,
                Event.timestamp <= now,
            )
        )
    )
    if (has_events.scalar_one() or 0) == 0:
        range_result = await db.execute(
            select(func.min(Event.timestamp), func.max(Event.timestamp)).where(
                Event.store_id == store_id
            )
        )
        range_row = range_result.first()
        if range_row and range_row[0] is not None:
            now = range_row[1]
            if now.tzinfo is None:
                now = now.replace(tzinfo=timezone.utc)
            window_start = now - timedelta(hours=window_hours)

    # 1. UNIQUE VISITORS
    uv_result = await db.execute(
        select(func.count(distinct(VisitorSession.visitor_id))).where(
            and_(
                VisitorSession.store_id == store_id,
                VisitorSession.is_staff == False,
                VisitorSession.entry_timestamp >= window_start,
                VisitorSession.entry_timestamp <= now,
            )
        )
    )
    unique_visitors: int = uv_result.scalar_one() or 0

    # 2. CONVERSION RATE
    converted_result = await db.execute(
        select(func.count(VisitorSession.id)).where(
            and_(
                VisitorSession.store_id == store_id,
                VisitorSession.is_staff == False,
                VisitorSession.is_converted == True,
                VisitorSession.entry_timestamp >= window_start,
                VisitorSession.entry_timestamp <= now,
            )
        )
    )
    converted_count: int = converted_result.scalar_one() or 0
    conversion_rate = converted_count / max(unique_visitors, 1) if unique_visitors > 0 else 0.0

    # 3. AVG DWELL PER ZONE
    zone_names = _load_zone_display_names(settings.store_layout_path)

    dwell_result = await db.execute(
        select(
            Event.zone_id,
            func.avg(Event.dwell_ms).label("avg_dwell"),
            func.count(distinct(Event.visitor_id)).label("visit_count"),
        ).where(
            and_(
                Event.store_id == store_id,
                Event.is_staff == False,
                Event.event_type.in_(["ZONE_DWELL", "ZONE_EXIT"]),
                Event.zone_id.isnot(None),
                Event.timestamp >= window_start,
                Event.timestamp <= now,
            )
        ).group_by(Event.zone_id)
    )
    dwell_rows = dwell_result.all()

    avg_dwell_per_zone: list[ZoneDwell] = []
    for row in dwell_rows:
        avg_dwell_per_zone.append(
            ZoneDwell(
                zone_id=row.zone_id,
                display_name=zone_names.get(row.zone_id, row.zone_id),
                avg_dwell_seconds=round((row.avg_dwell or 0) / 1000.0, 2),
                visit_count=row.visit_count or 0,
            )
        )

    # 4. QUEUE DEPTH — most recent BILLING_QUEUE_JOIN in last 1 hour
    one_hour_ago = now - timedelta(hours=1)
    queue_result = await db.execute(
        select(Event.metadata_json).where(
            and_(
                Event.store_id == store_id,
                Event.event_type == "BILLING_QUEUE_JOIN",
                Event.timestamp >= one_hour_ago,
            )
        ).order_by(Event.timestamp.desc()).limit(1)
    )
    queue_row = queue_result.scalar_one_or_none()
    queue_depth = 0
    if queue_row and isinstance(queue_row, dict):
        queue_depth = queue_row.get("queue_depth") or 0

    # 5. ABANDONMENT RATE
    joined_result = await db.execute(
        select(func.count(distinct(Event.visitor_id))).where(
            and_(
                Event.store_id == store_id,
                Event.is_staff == False,
                Event.event_type == "BILLING_QUEUE_JOIN",
                Event.timestamp >= window_start,
                Event.timestamp <= now,
            )
        )
    )
    joined_count: int = joined_result.scalar_one() or 0

    abandoned_result = await db.execute(
        select(func.count(distinct(Event.visitor_id))).where(
            and_(
                Event.store_id == store_id,
                Event.is_staff == False,
                Event.event_type == "BILLING_QUEUE_ABANDON",
                Event.timestamp >= window_start,
                Event.timestamp <= now,
            )
        )
    )
    abandoned_count: int = abandoned_result.scalar_one() or 0
    abandonment_rate = abandoned_count / max(joined_count, 1) if joined_count > 0 else 0.0

    # 6. TOTAL TRANSACTIONS
    txn_result = await db.execute(
        select(func.count(POSTransaction.id)).where(
            and_(
                POSTransaction.store_id == store_id,
                POSTransaction.timestamp >= window_start,
                POSTransaction.timestamp <= now,
            )
        )
    )
    total_transactions: int = txn_result.scalar_one() or 0

    return MetricsResponse(
        store_id=store_id,
        window_start=window_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        window_end=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        unique_visitors=unique_visitors,
        conversion_rate=round(conversion_rate, 4),
        avg_dwell_per_zone=avg_dwell_per_zone,
        queue_depth=queue_depth,
        abandonment_rate=round(abandonment_rate, 4),
        total_transactions=total_transactions,
    )
