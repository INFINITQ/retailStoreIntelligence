# You are writing edge-case tests for the retail store CCTV analytics API.
# These test the scenarios described as critical in the challenge problem statement.

# FILE: tests/test_edge_cases.py

# Add this block at the very top:
# # PROMPT: Generate edge-case tests for: empty store periods (zero traffic), all-staff clip
# #          (every event is is_staff=True), zero purchases (no POS transactions), re-entry
# #          not double-counting in funnel, and STALE_FEED health warning after 10+ minutes.
# # CHANGES MADE: Added assertion that API never returns null for numeric fields,
# #               added test for partial-clip scenario, improved staff-only assertions.

# IMPLEMENT THE FOLLOWING TESTS:

# 1. `test_empty_store_metrics_no_crash(test_client)` — call /metrics, /funnel, /heatmap,
#    /anomalies with zero events ingested. Assert all return 200, no 5xx. Assert all numeric
#    fields are 0 or 0.0 — never None/null.

# 2. `test_all_staff_events_excluded_from_metrics(test_client, make_event)` — ingest 10
#    ENTRY events all with is_staff=True; assert /metrics returns unique_visitors=0,
#    conversion_rate=0.0.

# 3. `test_all_staff_events_excluded_from_funnel(test_client, make_event)` — same 10 staff
#    events; /funnel returns all stage counts=0.

# 4. `test_zero_purchases_conversion_rate_is_zero(test_client, make_event)` — ingest 5
#    customer ENTRY events; no POS transactions; /metrics conversion_rate must be 0.0, not null.

# 5. `test_reentry_event_does_not_inflate_funnel(test_client, make_event)` — ingest ENTRY,
#    EXIT, REENTRY, EXIT for one visitor_id; /funnel "entry" stage count must be 1, not 2 or 3.

# 6. `test_health_stale_feed_after_10_minutes(test_client, make_event)` — ingest one event
#    with timestamp 15 minutes ago; call /health; assert store status is "STALE_FEED".

# 7. `test_health_returns_200_even_when_degraded(test_client)` — /health must always return
#    HTTP 200 (status conveyed in JSON body, not HTTP code).

# 8. `test_ingest_idempotency_same_event_100_times(test_client, make_event)` — POST same
#    single event 100 times; DB must have exactly 1 row with that event_id.
#    Assert final accepted count is consistent (does not error).

# 9. `test_heatmap_data_confidence_false_below_20_sessions(test_client, make_event)` —
#    ingest 10 sessions (below 20 threshold); assert all heatmap zones have data_confidence=False.

# 10. `test_heatmap_data_confidence_true_at_20_sessions(test_client, make_event)` —
#     ingest 20 unique visitor ZONE_ENTER events; assert data_confidence=True for visited zone.

# IMPORTS NEEDED: pytest, pytest_asyncio, httpx, uuid, datetime (datetime, timedelta, timezone),
# tests.conftest (make_event, seed_pos_transaction)
