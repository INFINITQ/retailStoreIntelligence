# You are writing tests for the /events/ingest endpoint of a retail store CCTV analytics API.

# FILE: tests/test_ingestion.py

# Add this block at the very top of the file:
# # PROMPT: Generate comprehensive tests for POST /events/ingest covering: happy path batch
# #          ingest, idempotency, partial success on malformed events, batch size limit,
# #          and empty batch rejection.
# # CHANGES MADE: Fixed async test client usage, added DB query verification after ingest,
# #               adjusted expected error message text.

# TECH: Python 3.11, pytest==8.3.4, pytest-asyncio==0.24.0, httpx

# USE conftest.py fixtures: test_client, make_event.

# IMPLEMENT THE FOLLOWING TESTS:

# 1. `test_ingest_single_valid_event(test_client, make_event)` — POST one valid event;
#    assert 200, accepted=1, rejected=0.

# 2. `test_ingest_batch_of_10(test_client, make_event)` — POST 10 events with unique event_ids;
#    assert accepted=10, rejected=0.

# 3. `test_ingest_idempotent(test_client, make_event)` — POST same batch twice;
#    second call must also return 200 with accepted = N (not error); verify DB has no duplicates.

# 4. `test_ingest_partial_success_malformed_event(test_client, make_event)` — batch of 3:
#    first valid, second has confidence=2.0 (invalid), third valid.
#    Assert accepted=2, rejected=1, errors has one entry.

# 5. `test_ingest_rejects_empty_batch(test_client)` — POST {"events": []};
#    assert 400 status code.

# 6. `test_ingest_rejects_batch_over_500(test_client, make_event)` — POST 501 events;
#    assert 400 status code.

# 7. `test_ingest_invalid_event_type(test_client, make_event)` — event_type="UNKNOWN";
#    assert it's in the rejected list.

# 8. `test_ingest_handles_db_unavailable()` — monkeypatch ingest_event_batch to raise
#    sqlalchemy.exc.OperationalError; assert response is 503 with structured error body.

# 9. `test_ingest_creates_visitor_session(test_client, test_db, make_event)` — POST an ENTRY
#    event; query test_db for VisitorSession with matching visitor_id; assert it exists.

# 10. `test_ingest_updates_session_on_exit(test_client, test_db, make_event)` — POST ENTRY
#     then EXIT for same visitor_id; assert session.exit_timestamp is not None.

# IMPORTS NEEDED:
#   pytest, pytest_asyncio, httpx, uuid, sqlalchemy (select), sqlalchemy.exc,
#   app.models.db_models (VisitorSession), tests.conftest (make_event)
