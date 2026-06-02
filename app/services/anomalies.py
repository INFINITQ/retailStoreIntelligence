# You are writing the anomaly detection service for a retail store CCTV analytics API.

# FILE: app/services/anomalies.py
# PURPOSE: Detect and return active anomalies for GET /stores/{id}/anomalies.
# Four anomaly types: BILLING_QUEUE_SPIKE, CONVERSION_DROP, DEAD_ZONE, STALE_FEED.

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import and_, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.db_models import Event, VisitorSession
from app.models.schemas import Anomaly, AnomalyResponse


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


async def _check_queue_spike(
    db: AsyncSession, store_id: str, cfg
) -> Optional[Anomaly]:
    """Check for billing queue spike in the last 30 minutes."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
    result = await db.execute(
        select(Event.metadata_json, Event.timestamp)
        .where(
            and_(
                Event.store_id == store_id,
                Event.event_type == "BILLING_QUEUE_JOIN",
                Event.timestamp >= cutoff,
            )
        )
        .order_by(Event.timestamp.desc())
        .limit(1)
    )
    row = result.first()
    if row is None:
        return None

    meta = row[0] or {}
    depth: int = meta.get("queue_depth") or 0
    if depth < cfg.queue_spike_threshold:
        return None

    if depth >= cfg.queue_critical_threshold:
        severity = "CRITICAL"
    else:
        severity = "WARN"

    return Anomaly(
        anomaly_id=str(uuid.uuid4()),
        anomaly_type="BILLING_QUEUE_SPIKE",
        severity=severity,
        description=f"Billing queue depth is {depth} (threshold: {cfg.queue_spike_threshold}).",
        suggested_action="Activate additional billing counter immediately.",
        detected_at=_now_iso(),
        details={"current_depth": depth, "threshold": cfg.queue_spike_threshold},
    )


async def _check_conversion_drop(
    db: AsyncSession, store_id: str, cfg
) -> Optional[Anomaly]:
    """Compare today's conversion rate with the 7-day rolling average."""
    now = datetime.now(timezone.utc)
    today_start = now - timedelta(hours=24)

    # Today's rate
    uv_today = await db.execute(
        select(func.count(distinct(VisitorSession.visitor_id))).where(
            and_(
                VisitorSession.store_id == store_id,
                VisitorSession.is_staff == False,
                VisitorSession.entry_timestamp >= today_start,
            )
        )
    )
    total_today: int = uv_today.scalar_one() or 0

    conv_today = await db.execute(
        select(func.count(VisitorSession.id)).where(
            and_(
                VisitorSession.store_id == store_id,
                VisitorSession.is_staff == False,
                VisitorSession.is_converted == True,
                VisitorSession.entry_timestamp >= today_start,
            )
        )
    )
    converted_today: int = conv_today.scalar_one() or 0
    today_rate = converted_today / max(total_today, 1) if total_today > 0 else 0.0

    # 7-day average (days before today)
    seven_days_ago = today_start - timedelta(days=7)
    uv_7d = await db.execute(
        select(func.count(distinct(VisitorSession.visitor_id))).where(
            and_(
                VisitorSession.store_id == store_id,
                VisitorSession.is_staff == False,
                VisitorSession.entry_timestamp >= seven_days_ago,
                VisitorSession.entry_timestamp < today_start,
            )
        )
    )
    total_7d: int = uv_7d.scalar_one() or 0

    conv_7d = await db.execute(
        select(func.count(VisitorSession.id)).where(
            and_(
                VisitorSession.store_id == store_id,
                VisitorSession.is_staff == False,
                VisitorSession.is_converted == True,
                VisitorSession.entry_timestamp >= seven_days_ago,
                VisitorSession.entry_timestamp < today_start,
            )
        )
    )
    converted_7d: int = conv_7d.scalar_one() or 0
    seven_day_avg = converted_7d / max(total_7d, 1) if total_7d > 0 else 0.0

    if seven_day_avg == 0:
        return None

    drop_pct = (seven_day_avg - today_rate) / max(seven_day_avg, 0.001) * 100

    if drop_pct >= cfg.conversion_critical_drop_pct:
        severity = "CRITICAL"
    elif drop_pct >= cfg.conversion_drop_threshold_pct:
        severity = "WARN"
    else:
        return None

    return Anomaly(
        anomaly_id=str(uuid.uuid4()),
        anomaly_type="CONVERSION_DROP",
        severity=severity,
        description=f"Conversion rate dropped {drop_pct:.1f}% vs 7-day average.",
        suggested_action="Review today's promotions and floor staff allocation.",
        detected_at=_now_iso(),
        details={
            "today_rate": round(today_rate, 4),
            "seven_day_avg": round(seven_day_avg, 4),
            "drop_pct": round(drop_pct, 2),
        },
    )


async def _check_dead_zones(
    db: AsyncSession, store_id: str, cfg
) -> list[Anomaly]:
    """Check each product zone for inactivity > dead_zone_minutes."""
    try:
        with open(cfg.store_layout_path, "r", encoding="utf-8") as f:
            layout = json.load(f)
    except Exception:
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=cfg.dead_zone_minutes)
    anomalies: list[Anomaly] = []
    billing_ids = {"BILLING", "BILLING_QUEUE"}

    for zone in layout.get("zones", []):
        zone_id = zone["zone_id"]
        if zone.get("is_entry_exit") or zone_id in billing_ids:
            continue

        last_activity = await db.execute(
            select(func.max(Event.timestamp)).where(
                and_(
                    Event.store_id == store_id,
                    Event.zone_id == zone_id,
                    Event.event_type.in_(["ZONE_ENTER", "ZONE_DWELL"]),
                )
            )
        )
        last_ts = last_activity.scalar_one_or_none()

        is_dead = (last_ts is None) or (last_ts < cutoff)
        if not is_dead:
            continue

        if last_ts is not None:
            minutes_since = (datetime.now(timezone.utc) - last_ts.replace(tzinfo=timezone.utc)).total_seconds() / 60
        else:
            minutes_since = float("inf")

        anomalies.append(
            Anomaly(
                anomaly_id=str(uuid.uuid4()),
                anomaly_type="DEAD_ZONE",
                severity="INFO",
                description=f"Zone {zone_id} has had no activity for {minutes_since:.0f}+ minutes.",
                suggested_action=f"Verify camera coverage for zone {zone_id}. Consider staff animation.",
                detected_at=_now_iso(),
                details={
                    "zone_id": zone_id,
                    "minutes_since_last_activity": round(minutes_since, 1)
                    if minutes_since != float("inf") else None,
                },
            )
        )
    return anomalies


async def _check_stale_feed(
    db: AsyncSession, store_id: str, cfg
) -> Optional[Anomaly]:
    """Emit STALE_FEED if last event is > stale_feed_minutes ago."""
    result = await db.execute(
        select(func.max(Event.timestamp)).where(Event.store_id == store_id)
    )
    last_ts = result.scalar_one_or_none()

    if last_ts is None:
        return Anomaly(
            anomaly_id=str(uuid.uuid4()),
            anomaly_type="STALE_FEED",
            severity="WARN",
            description="No events have been ingested for this store yet.",
            suggested_action="Check CCTV pipeline connectivity and camera feeds.",
            detected_at=_now_iso(),
            details={"minutes_since_last_event": None},
        )

    last_ts_aware = last_ts.replace(tzinfo=timezone.utc) if last_ts.tzinfo is None else last_ts
    minutes_since = (datetime.now(timezone.utc) - last_ts_aware).total_seconds() / 60

    if minutes_since < cfg.stale_feed_minutes:
        return None

    return Anomaly(
        anomaly_id=str(uuid.uuid4()),
        anomaly_type="STALE_FEED",
        severity="WARN",
        description=f"No events received in the last {minutes_since:.1f} minutes.",
        suggested_action="Check CCTV pipeline connectivity and camera feeds.",
        detected_at=_now_iso(),
        details={"minutes_since_last_event": round(minutes_since, 1)},
    )


async def compute_anomalies(db: AsyncSession, store_id: str) -> AnomalyResponse:
    cfg = settings
    anomalies: list[Anomaly] = []

    queue_anomaly = await _check_queue_spike(db, store_id, cfg)
    if queue_anomaly:
        anomalies.append(queue_anomaly)

    conv_anomaly = await _check_conversion_drop(db, store_id, cfg)
    if conv_anomaly:
        anomalies.append(conv_anomaly)

    dead_zones = await _check_dead_zones(db, store_id, cfg)
    anomalies.extend(dead_zones)

    stale = await _check_stale_feed(db, store_id, cfg)
    if stale:
        anomalies.append(stale)

    return AnomalyResponse(
        store_id=store_id,
        checked_at=_now_iso(),
        anomalies=anomalies,
        anomaly_count=len(anomalies),
    )
