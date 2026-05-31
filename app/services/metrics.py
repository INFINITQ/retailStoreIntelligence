# You are writing the metrics computation service for a retail store CCTV analytics API.

# FILE: app/services/metrics.py
# PURPOSE: Compute real-time store metrics for GET /stores/{id}/metrics.
# All queries exclude is_staff=True events. "Today" is scoped to the last window_hours.

# TECH: Python 3.11, sqlalchemy.ext.asyncio, datetime

# IMPLEMENT:

# `async def compute_metrics(db: AsyncSession, store_id: str, window_hours: int = 24) -> MetricsResponse:`

# Steps:
# 1. Compute window: window_end = datetime.now(UTC), window_start = window_end - timedelta(hours=window_hours).

# 2. UNIQUE VISITORS: Count distinct visitor_ids from VisitorSession WHERE
#    store_id=store_id AND is_staff=False AND entry_timestamp BETWEEN window_start AND window_end.

# 3. CONVERSION RATE:
#    - Count sessions with is_converted=True (and is_staff=False) in window.
#    - conversion_rate = converted_count / max(unique_visitors, 1).
#    - If unique_visitors == 0: return 0.0.

# 4. AVG DWELL PER ZONE: Query Event table WHERE store_id=store_id AND is_staff=False
#    AND event_type IN ("ZONE_DWELL", "ZONE_EXIT") AND zone_id IS NOT NULL
#    AND timestamp IN window.
#    Group by zone_id; compute avg(dwell_ms), count(distinct visitor_id).
#    Load zone display_name from store_layout.json (read file via settings.store_layout_path).
#    Build list[ZoneDwell].

# 5. QUEUE DEPTH: Get the most recent BILLING_QUEUE_JOIN event's metadata_json["queue_depth"]
#    for this store within the last 1 hour. Default to 0 if none found.

# 6. ABANDONMENT RATE:
#    - Count BILLING_QUEUE_JOIN events (distinct visitor_id) in window.
#    - Count BILLING_QUEUE_ABANDON events (distinct visitor_id) in window.
#    - abandonment_rate = abandoned / max(joined, 1).

# 7. TOTAL TRANSACTIONS: Count rows in POSTransaction WHERE store_id=store_id
#    AND timestamp IN window.

# Return MetricsResponse with all computed values and the window timestamps as ISO strings.

# IMPORTS NEEDED:
#   sqlalchemy.ext.asyncio (AsyncSession), sqlalchemy (select, func, distinct, and_),
#   datetime (datetime, timedelta, timezone), json,
#   app.models.db_models (Event, VisitorSession, POSTransaction),
#   app.models.schemas (MetricsResponse, ZoneDwell), app.config (settings)
