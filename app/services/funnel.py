# You are writing the conversion funnel service for a retail store CCTV analytics API.

# FILE: app/services/funnel.py
# PURPOSE: Compute the session-level conversion funnel for GET /stores/{id}/funnel.
# The unit of analysis is VisitorSession, not raw events.
# Re-entries must NOT double-count a visitor — use distinct visitor_ids as the unit.

# TECH: Python 3.11, sqlalchemy.ext.asyncio

# FUNNEL STAGES (in order):
# 1. "entry"         — unique visitors who entered (all non-staff sessions with entry_timestamp)
# 2. "zone_visit"    — visitors who visited at least one named product zone
#                      (session.zones_visited JSON array is non-empty; exclude ENTRY_THRESHOLD,
#                       BILLING, BILLING_QUEUE zone_ids)
# 3. "billing_queue" — visitors who had a BILLING_QUEUE_JOIN event
# 4. "purchase"      — visitors with is_converted=True

# IMPLEMENT:

# `async def compute_funnel(db: AsyncSession, store_id: str, window_hours: int = 24) -> FunnelResponse:`

# 1. Compute window (same as metrics.py).

# 2. Stage 1 — Entry: count distinct visitor_ids in VisitorSession WHERE store_id=store_id
#    AND is_staff=False AND entry_timestamp IN window.
#    This is total_sessions.

# 3. Stage 2 — Zone visit: from the same session set, count sessions WHERE
#    zones_visited JSON array has at least one element that is NOT in
#    ["ENTRY_THRESHOLD", "BILLING", "BILLING_QUEUE"].
#    Use a SQLAlchemy JSON path query or Python-side filtering on the result set.

# 4. Stage 3 — Billing queue: count distinct visitor_ids from Event WHERE
#    store_id=store_id AND is_staff=False AND event_type="BILLING_QUEUE_JOIN"
#    AND timestamp IN window.

# 5. Stage 4 — Purchase: count sessions with is_converted=True in window.

# 6. Compute drop-off %:
#    - entry→zone_visit: (stage1_count - stage2_count) / max(stage1_count, 1) * 100
#    - zone_visit→billing_queue: (stage2 - stage3) / max(stage2, 1) * 100
#    - billing_queue→purchase: (stage3 - stage4) / max(stage3, 1) * 100
#    - entry stage itself has drop_off_pct = 0.0.

# 7. Build and return FunnelResponse with four FunnelStage objects.

# EDGE CASE: If total_sessions == 0, return all stages with count=0 and drop_off_pct=0.0.

# IMPORTS NEEDED:
#   sqlalchemy.ext.asyncio (AsyncSession), sqlalchemy (select, func, distinct, and_, text),
#   datetime (datetime, timedelta, timezone),
#   app.models.db_models (Event, VisitorSession),
#   app.models.schemas (FunnelResponse, FunnelStage), app.config (settings)
