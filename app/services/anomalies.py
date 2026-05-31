# You are writing the anomaly detection service for a retail store CCTV analytics API.

# FILE: app/services/anomalies.py
# PURPOSE: Detect and return active anomalies for GET /stores/{id}/anomalies.
# Four anomaly types: BILLING_QUEUE_SPIKE, CONVERSION_DROP, DEAD_ZONE, STALE_FEED.

# TECH: Python 3.11, sqlalchemy.ext.asyncio, uuid, datetime

# ANOMALY SPECIFICATIONS:

# 1. BILLING_QUEUE_SPIKE:
#    - Check queue_depth in the most recent BILLING_QUEUE_JOIN event (last 30 min).
#    - severity: WARN if depth >= queue_spike_threshold (default 5),
#                CRITICAL if >= queue_critical_threshold (default 10).
#    - suggested_action: "Activate additional billing counter immediately."
#    - details: {"current_depth": N, "threshold": T}

# 2. CONVERSION_DROP:
#    - Compute today's conversion_rate (last 24h window).
#    - Compute 7-day average: avg conversion_rate from VisitorSession, grouped by day,
#      for the 7 days before today.
#    - drop_pct = (seven_day_avg - today_rate) / max(seven_day_avg, 0.001) * 100
#    - severity: WARN if drop_pct >= 20%, CRITICAL if >= 40%.
#    - Only emit if seven_day_avg > 0.
#    - suggested_action: "Review today's promotions and floor staff allocation."
#    - details: {"today_rate": float, "seven_day_avg": float, "drop_pct": float}

# 3. DEAD_ZONE:
#    - For each zone (from store_layout.json), check if the most recent ZONE_ENTER or
#      ZONE_DWELL event for that zone in this store is more than dead_zone_minutes ago.
#    - Exclude BILLING and BILLING_QUEUE zones from dead zone check.
#    - severity: INFO.
#    - One anomaly per dead zone.
#    - suggested_action: f"Verify camera coverage for zone {zone_id}. Consider staff animation."
#    - details: {"zone_id": zone_id, "minutes_since_last_activity": float}

# 4. STALE_FEED:
#    - Check the most recent event for this store overall.
#    - If > stale_feed_minutes (default 10) ago: emit STALE_FEED anomaly.
#    - severity: WARN.
#    - suggested_action: "Check CCTV pipeline connectivity and camera feeds."
#    - details: {"minutes_since_last_event": float}

# IMPLEMENT:

# `async def compute_anomalies(db: AsyncSession, store_id: str) -> AnomalyResponse:`
# - Call the four detection checks above.
# - Aggregate all detected Anomaly objects.
# - Return AnomalyResponse(store_id=store_id, checked_at=now_iso, anomalies=anomalies,
#   anomaly_count=len(anomalies)).
# - Handle the case where there are 0 events (new store): return empty anomalies list,
#   except emit a STALE_FEED if zero events exist at all.

# Each check should be its own private async function:
#   `async def _check_queue_spike(db, store_id, settings) -> Optional[Anomaly]`
#   `async def _check_conversion_drop(db, store_id, settings) -> Optional[Anomaly]`
#   `async def _check_dead_zones(db, store_id, settings) -> list[Anomaly]`
#   `async def _check_stale_feed(db, store_id, settings) -> Optional[Anomaly]`

# IMPORTS NEEDED:
#   sqlalchemy.ext.asyncio (AsyncSession), sqlalchemy (select, func, and_, distinct),
#   datetime (datetime, timedelta, timezone), uuid, json,
#   app.models.db_models (Event, VisitorSession),
#   app.models.schemas (AnomalyResponse, Anomaly), app.config (settings)
