# You are writing the heatmap computation service for a retail store CCTV analytics API.

# FILE: app/services/heatmap.py
# PURPOSE: Compute per-zone visit frequency and average dwell for GET /stores/{id}/heatmap.

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.db_models import Event, VisitorSession
from app.models.schemas import HeatmapResponse, ZoneHeatmap


def _load_zone_defs(layout_path: str) -> dict[str, str]:
    """Return {zone_id: display_name} excluding entry/exit zones."""
    try:
        with open(layout_path, "r", encoding="utf-8") as f:
            layout = json.load(f)
        result = {}
        for z in layout.get("zones", []):
            if not z.get("is_entry_exit", False):
                result[z["zone_id"]] = z.get("display_name", z["zone_id"])
        return result
    except Exception:
        return {}


async def compute_heatmap(
    db: AsyncSession, store_id: str, window_hours: int = 24
) -> HeatmapResponse:
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=window_hours)

    # Load zone definitions (all non-entry-exit zones)
    zone_defs = _load_zone_defs(settings.store_layout_path)

    # Query event aggregates per zone
    agg_result = await db.execute(
        select(
            Event.zone_id,
            func.count(distinct(Event.visitor_id)).label("visit_count"),
            func.avg(Event.dwell_ms).label("avg_dwell_ms"),
        ).where(
            and_(
                Event.store_id == store_id,
                Event.is_staff == False,
                Event.zone_id.isnot(None),
                Event.zone_id != "ENTRY_THRESHOLD",
                Event.timestamp >= window_start,
                Event.timestamp <= now,
            )
        ).group_by(Event.zone_id)
    )
    agg_rows = agg_result.all()
    zone_data: dict[str, dict] = {}
    for row in agg_rows:
        zone_data[row.zone_id] = {
            "visit_count": row.visit_count or 0,
            "avg_dwell_ms": float(row.avg_dwell_ms or 0.0),
        }

    # Total sessions for data_confidence
    total_sessions_result = await db.execute(
        select(func.count(distinct(VisitorSession.visitor_id))).where(
            and_(
                VisitorSession.store_id == store_id,
                VisitorSession.is_staff == False,
                VisitorSession.entry_timestamp >= window_start,
                VisitorSession.entry_timestamp <= now,
            )
        )
    )
    total_sessions: int = total_sessions_result.scalar_one() or 0
    data_confidence: bool = total_sessions >= 20

    # Build per-zone list including zero-visit zones
    all_zones: list[dict] = []
    for zone_id, display_name in zone_defs.items():
        d = zone_data.get(zone_id, {"visit_count": 0, "avg_dwell_ms": 0.0})
        all_zones.append(
            {
                "zone_id": zone_id,
                "display_name": display_name,
                "visit_count": d["visit_count"],
                "avg_dwell_ms": d["avg_dwell_ms"],
            }
        )

    # Normalise scores
    max_visits = max((z["visit_count"] for z in all_zones), default=0)

    zones: list[ZoneHeatmap] = []
    for z in all_zones:
        norm = (z["visit_count"] / max_visits * 100) if max_visits > 0 else 0.0
        zones.append(
            ZoneHeatmap(
                zone_id=z["zone_id"],
                display_name=z["display_name"],
                visit_count=z["visit_count"],
                avg_dwell_ms=round(z["avg_dwell_ms"], 2),
                normalized_score=round(norm, 2),
                data_confidence=data_confidence,
            )
        )

    zones.sort(key=lambda z: z.normalized_score, reverse=True)

    return HeatmapResponse(
        store_id=store_id,
        window_start=window_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        window_end=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        zones=zones,
    )
