# You are writing the conversion funnel service for a retail store CCTV analytics API.

# FILE: app/services/funnel.py
# PURPOSE: Compute the session-level conversion funnel for GET /stores/{id}/funnel.

from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db_models import Event, VisitorSession
from app.models.schemas import FunnelResponse, FunnelStage

_EXCLUDED_ZONES = {"ENTRY_THRESHOLD", "BILLING", "BILLING_QUEUE"}


async def compute_funnel(
    db: AsyncSession, store_id: str, window_hours: int = 24
) -> FunnelResponse:
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=window_hours)

    # ── Stage 1: Entry ── unique customer visitor_ids with a session in window
    sessions_result = await db.execute(
        select(VisitorSession).where(
            and_(
                VisitorSession.store_id == store_id,
                VisitorSession.is_staff == False,
                VisitorSession.entry_timestamp >= window_start,
                VisitorSession.entry_timestamp <= now,
            )
        )
    )
    all_sessions = sessions_result.scalars().all()

    # Deduplicate by visitor_id — re-entries should not double-count
    seen_visitors: set[str] = set()
    unique_sessions = []
    for s in all_sessions:
        if s.visitor_id not in seen_visitors:
            seen_visitors.add(s.visitor_id)
            unique_sessions.append(s)

    stage1_count = len(unique_sessions)

    if stage1_count == 0:
        zero_stages = [
            FunnelStage(stage="entry", count=0, drop_off_pct=0.0),
            FunnelStage(stage="zone_visit", count=0, drop_off_pct=0.0),
            FunnelStage(stage="billing_queue", count=0, drop_off_pct=0.0),
            FunnelStage(stage="purchase", count=0, drop_off_pct=0.0),
        ]
        return FunnelResponse(
            store_id=store_id,
            window_start=window_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            window_end=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            stages=zero_stages,
            total_sessions=0,
        )

    # ── Stage 2: Zone visit ── at least one product zone in zones_visited
    stage2_visitors: set[str] = set()
    for s in unique_sessions:
        zones = s.zones_visited or []
        product_zones = [z for z in zones if z not in _EXCLUDED_ZONES]
        if product_zones:
            stage2_visitors.add(s.visitor_id)
    stage2_count = len(stage2_visitors)

    # ── Stage 3: Billing queue ── distinct visitor_ids with BILLING_QUEUE_JOIN
    bq_result = await db.execute(
        select(distinct(Event.visitor_id)).where(
            and_(
                Event.store_id == store_id,
                Event.is_staff == False,
                Event.event_type == "BILLING_QUEUE_JOIN",
                Event.timestamp >= window_start,
                Event.timestamp <= now,
                Event.visitor_id.in_(seen_visitors),
            )
        )
    )
    stage3_visitors = {row[0] for row in bq_result}
    stage3_count = len(stage3_visitors)

    # ── Stage 4: Purchase ── sessions with is_converted=True
    stage4_visitors: set[str] = set()
    for s in unique_sessions:
        if s.is_converted:
            stage4_visitors.add(s.visitor_id)
    stage4_count = len(stage4_visitors)

    # ── Drop-off percentages ──
    def drop_pct(current: int, previous: int) -> float:
        if previous == 0:
            return 0.0
        drop = (previous - current) / previous * 100
        return max(0.0, round(drop, 2))

    stages = [
        FunnelStage(stage="entry", count=stage1_count, drop_off_pct=0.0),
        FunnelStage(stage="zone_visit", count=stage2_count, drop_off_pct=drop_pct(stage2_count, stage1_count)),
        FunnelStage(stage="billing_queue", count=stage3_count, drop_off_pct=drop_pct(stage3_count, stage2_count)),
        FunnelStage(stage="purchase", count=stage4_count, drop_off_pct=drop_pct(stage4_count, stage3_count)),
    ]

    return FunnelResponse(
        store_id=store_id,
        window_start=window_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        window_end=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        stages=stages,
        total_sessions=stage1_count,
    )
