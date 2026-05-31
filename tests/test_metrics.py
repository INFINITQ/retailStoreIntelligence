# You are writing tests for the /stores/{id}/metrics endpoint of a retail analytics API.

# FILE: tests/test_metrics.py

# Add this block at the very top:
# # PROMPT: Generate tests for GET /stores/{store_id}/metrics verifying unique visitor count,
# #          conversion rate computation, staff exclusion, zero-purchase handling, and
# #          avg_dwell_per_zone output structure.
# # CHANGES MADE: Added zero-visitor edge case test, fixed window_hours parameter usage,
# #               corrected expected conversion_rate precision.

# IMPLEMENT THE FOLLOWING TESTS:

# 1. `test_metrics_empty_store_returns_zeros(test_client)` — call /stores/STORE_BLR_002/metrics
#    with no events ingested; assert 200, unique_visitors=0, conversion_rate=0.0,
#    queue_depth=0. Do NOT assert null — assert 0.

# 2. `test_metrics_counts_unique_visitors(test_client, make_event)` — ingest 3 ENTRY events
#    for 3 different visitor_ids; assert unique_visitors=3.

# 3. `test_metrics_excludes_staff(test_client, make_event)` — ingest 2 ENTRY events
#    (is_staff=False) and 1 ENTRY (is_staff=True); assert unique_visitors=2.

# 4. `test_metrics_conversion_rate(test_client, test_db, make_event, seed_pos_transaction)` —
#    ingest 4 ENTRY events; mark 2 sessions as is_converted=True in test_db;
#    assert conversion_rate ≈ 0.5.

# 5. `test_metrics_zero_purchases_not_null(test_client, make_event)` — ingest events but
#    no POS transactions; assert conversion_rate=0.0 (not null, not error).

# 6. `test_metrics_avg_dwell_per_zone(test_client, make_event)` — ingest 3 ZONE_DWELL events
#    for zone_id="FOH" with dwell_ms=30000; assert avg_dwell_per_zone contains an entry for
#    "FOH" with avg_dwell_seconds ≈ 30.

# 7. `test_metrics_unknown_store_returns_404(test_client)` — call
#    /stores/STORE_UNKNOWN_999/metrics; assert 404.

# IMPORTS NEEDED: pytest, pytest_asyncio, httpx, uuid, datetime,
# tests.conftest (make_event, seed_pos_transaction)
