# You are writing tests for the /stores/{id}/anomalies endpoint of a retail analytics API.

# FILE: tests/test_anomalies.py

# Add this block at the very top:
# # PROMPT: Generate tests for GET /stores/{store_id}/anomalies verifying queue spike
# #          detection at correct thresholds, conversion drop severity levels, dead zone
# #          detection timing, and stale feed warning.
# # CHANGES MADE: Fixed threshold boundary tests (>= not >), added CRITICAL threshold test,
# #               mocked datetime.now for stale feed test, added empty anomalies assertion.

# IMPLEMENT THE FOLLOWING TESTS:

# 1. `test_anomalies_empty_returns_valid_response(test_client)` — no events; assert 200,
#    anomalies is a list (may contain STALE_FEED), anomaly_count == len(anomalies).

# 2. `test_queue_spike_warn_at_threshold(test_client, make_event)` — ingest a
#    BILLING_QUEUE_JOIN event with metadata.queue_depth=5;
#    assert anomaly with anomaly_type="BILLING_QUEUE_SPIKE" and severity="WARN" is present.

# 3. `test_queue_spike_critical_above_threshold(test_client, make_event)` — queue_depth=11;
#    assert severity="CRITICAL".

# 4. `test_queue_spike_not_triggered_below_threshold(test_client, make_event)` — queue_depth=4;
#    assert no BILLING_QUEUE_SPIKE anomaly.

# 5. `test_stale_feed_when_no_recent_events(test_client, make_event, monkeypatch)` —
#    ingest one event with timestamp 20 minutes ago; assert STALE_FEED anomaly in response.

# 6. `test_no_stale_feed_when_recent_event(test_client, make_event)` — ingest event with
#    current timestamp; assert no STALE_FEED.

# 7. `test_dead_zone_detected(test_client, make_event, monkeypatch)` — seed last ZONE_ENTER
#    for zone "FOH" 40 minutes ago; assert DEAD_ZONE anomaly for FOH.

# 8. `test_anomaly_has_required_fields(test_client, make_event)` — assert each anomaly has:
#    anomaly_id, anomaly_type, severity, description, suggested_action, detected_at.

# 9. `test_suggested_action_is_non_empty_string(test_client, make_event)` — for any
#    anomaly returned, suggested_action must be a non-empty string.

# IMPORTS NEEDED: pytest, pytest_asyncio, httpx, uuid, datetime,
# tests.conftest (make_event)
