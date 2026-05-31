# You are writing the heatmap computation service for a retail store CCTV analytics API.

# FILE: app/services/heatmap.py
# PURPOSE: Compute per-zone visit frequency and average dwell for GET /stores/{id}/heatmap.
# Normalise scores 0–100 and flag low-confidence zones (fewer than 20 sessions).

# TECH: Python 3.11, sqlalchemy.ext.asyncio, json

# IMPLEMENT:

# `async def compute_heatmap(db: AsyncSession, store_id: str, window_hours: int = 24) -> HeatmapResponse:`

# 1. Compute window.

# 2. Load zone definitions from store_layout.json. Build a dict
#    {zone_id: display_name} for all non-entry-exit zones.

# 3. Query the Event table: SELECT zone_id, COUNT(DISTINCT visitor_id) as visit_count,
#    AVG(dwell_ms) as avg_dwell_ms FROM events WHERE store_id=store_id AND is_staff=False
#    AND zone_id IS NOT NULL AND zone_id NOT IN ('ENTRY_THRESHOLD')
#    AND timestamp IN window GROUP BY zone_id.

# 4. Count total sessions in window (from VisitorSession) for the data_confidence flag.

# 5. For each zone in zone definitions (not just those with events — include zero-visit zones too):
#    - visit_count = result from query, default 0.
#    - avg_dwell_ms = result from query, default 0.0.
#    - data_confidence = (total_sessions >= 20).

# 6. Normalise: find max_visits across all zones. normalized_score = (zone_visits / max_visits) * 100.
#    If max_visits == 0, all scores = 0.0.

# 7. Sort zones by normalized_score descending.

# 8. Return HeatmapResponse with all zones, window timestamps.

# IMPORTS NEEDED:
#   sqlalchemy.ext.asyncio (AsyncSession), sqlalchemy (select, func, distinct, and_),
#   datetime (datetime, timedelta, timezone), json,
#   app.models.db_models (Event, VisitorSession),
#   app.models.schemas (HeatmapResponse, ZoneHeatmap), app.config (settings)
