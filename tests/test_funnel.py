# You are writing tests for the /stores/{id}/funnel endpoint of a retail analytics API.

# FILE: tests/test_funnel.py

# Add this block at the very top:
# # PROMPT: Generate tests for GET /stores/{store_id}/funnel verifying session-level funnel
# #          stages, drop-off percentages, re-entry deduplication, and zero-session edge case.
# # CHANGES MADE: Added re-entry dedup assertion, fixed session seeding for billing_queue
# #               stage, corrected drop-off calculation tolerance.

# IMPLEMENT THE FOLLOWING TESTS:

# 1. `test_funnel_empty_store(test_client)` — no events; assert 200, all stage counts=0,
#    total_sessions=0.

# 2. `test_funnel_entry_stage_count(test_client, make_event)` — ingest 5 ENTRY events
#    (distinct visitor_ids); assert funnel stage "entry" count=5.

# 3. `test_funnel_zone_visit_stage(test_client, make_event)` — ingest ENTRY + ZONE_ENTER
#    (zone_id="FOH") for 3 visitors, ENTRY only for 2 others;
#    assert "zone_visit" count=3, drop_off_pct≈40.0.

# 4. `test_funnel_billing_queue_stage(test_client, make_event)` — of 5 entered visitors,
#    2 have BILLING_QUEUE_JOIN events; assert "billing_queue" count=2.

# 5. `test_funnel_purchase_stage(test_client, test_db, make_event)` — 2 visitors have
#    is_converted=True in VisitorSession; assert "purchase" count=2.

# 6. `test_funnel_reentry_does_not_double_count(test_client, make_event)` —
#    ingest ENTRY + EXIT + REENTRY for same visitor_id; assert "entry" count=1 (not 2).

# 7. `test_funnel_stages_list_has_four_stages(test_client, make_event)` — assert response
#    has exactly 4 stages in order: ["entry", "zone_visit", "billing_queue", "purchase"].

# 8. `test_funnel_drop_off_never_negative(test_client, make_event)` — edge case where
#    billing_queue count > zone_visit count (data inconsistency); drop_off_pct must be >= 0.

# IMPORTS NEEDED: pytest, pytest_asyncio, httpx, uuid, datetime,
# tests.conftest (make_event)
