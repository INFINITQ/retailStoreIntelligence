# PROMPT: Generate tests for GET /stores/{store_id}/funnel verifying session-level funnel
#          stages, drop-off percentages, re-entry deduplication, and zero-session edge case.
# CHANGES MADE: Added re-entry dedup assertion, fixed session seeding for billing_queue
#               stage, corrected drop-off calculation tolerance.

# FILE: tests/test_funnel.py

import uuid

import pytest

from tests.conftest import make_event


@pytest.mark.asyncio
async def test_funnel_empty_store(test_client, test_db):
    resp = await test_client.get("/stores/STORE_BLR_002/funnel")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_sessions"] == 0
    for stage in body["stages"]:
        assert stage["count"] == 0


@pytest.mark.asyncio
async def test_funnel_entry_stage_count(test_client, test_db):
    events = [
        make_event(event_id=str(uuid.uuid4()), visitor_id=f"VIS_{i:06X}")
        for i in range(5)
    ]
    await test_client.post("/events/ingest", json={"events": events})

    resp = await test_client.get("/stores/STORE_BLR_002/funnel")
    assert resp.status_code == 200
    stages = {s["stage"]: s for s in resp.json()["stages"]}
    assert stages["entry"]["count"] == 5


@pytest.mark.asyncio
async def test_funnel_zone_visit_stage(test_client, test_db):
    # 3 visitors with zone visit, 2 without
    for i in range(3):
        vid = f"VIS_{i:06X}"
        entry = make_event(event_id=str(uuid.uuid4()), visitor_id=vid, event_type="ENTRY")
        zone = make_event(
            event_id=str(uuid.uuid4()), visitor_id=vid,
            event_type="ZONE_ENTER", zone_id="FOH",
        )
        await test_client.post("/events/ingest", json={"events": [entry, zone]})

    for i in range(3, 5):
        entry = make_event(event_id=str(uuid.uuid4()), visitor_id=f"VIS_{i:06X}", event_type="ENTRY")
        await test_client.post("/events/ingest", json={"events": [entry]})

    resp = await test_client.get("/stores/STORE_BLR_002/funnel")
    assert resp.status_code == 200
    stages = {s["stage"]: s for s in resp.json()["stages"]}
    assert stages["zone_visit"]["count"] == 3
    assert stages["zone_visit"]["drop_off_pct"] == pytest.approx(40.0, abs=1.0)


@pytest.mark.asyncio
async def test_funnel_billing_queue_stage(test_client, test_db):
    for i in range(5):
        entry = make_event(event_id=str(uuid.uuid4()), visitor_id=f"VIS_{i:06X}")
        await test_client.post("/events/ingest", json={"events": [entry]})

    # 2 visitors have billing queue join
    for i in range(2):
        bq = make_event(
            event_id=str(uuid.uuid4()), visitor_id=f"VIS_{i:06X}",
            event_type="BILLING_QUEUE_JOIN", zone_id="BILLING_QUEUE",
        )
        await test_client.post("/events/ingest", json={"events": [bq]})

    resp = await test_client.get("/stores/STORE_BLR_002/funnel")
    assert resp.status_code == 200
    stages = {s["stage"]: s for s in resp.json()["stages"]}
    assert stages["billing_queue"]["count"] == 2


@pytest.mark.asyncio
async def test_funnel_purchase_stage(test_client, test_db):
    from sqlalchemy import select
    from app.models.db_models import VisitorSession

    for i in range(4):
        entry = make_event(event_id=str(uuid.uuid4()), visitor_id=f"VIS_{i:06X}")
        await test_client.post("/events/ingest", json={"events": [entry]})

    # Mark 2 as converted
    result = await test_db.execute(select(VisitorSession).limit(2))
    for s in result.scalars().all():
        s.is_converted = True
    await test_db.commit()

    resp = await test_client.get("/stores/STORE_BLR_002/funnel")
    assert resp.status_code == 200
    stages = {s["stage"]: s for s in resp.json()["stages"]}
    assert stages["purchase"]["count"] == 2


@pytest.mark.asyncio
async def test_funnel_reentry_does_not_double_count(test_client, test_db):
    vid = "VIS_RENTRY"
    entry = make_event(event_id=str(uuid.uuid4()), visitor_id=vid, event_type="ENTRY")
    exit_evt = make_event(event_id=str(uuid.uuid4()), visitor_id=vid, event_type="EXIT")
    reentry = make_event(event_id=str(uuid.uuid4()), visitor_id=vid, event_type="REENTRY")

    await test_client.post("/events/ingest", json={"events": [entry, exit_evt, reentry]})

    resp = await test_client.get("/stores/STORE_BLR_002/funnel")
    assert resp.status_code == 200
    stages = {s["stage"]: s for s in resp.json()["stages"]}
    # Visitor counted once, not twice
    assert stages["entry"]["count"] == 1


@pytest.mark.asyncio
async def test_funnel_stages_list_has_four_stages(test_client, test_db):
    entry = make_event(event_id=str(uuid.uuid4()))
    await test_client.post("/events/ingest", json={"events": [entry]})

    resp = await test_client.get("/stores/STORE_BLR_002/funnel")
    assert resp.status_code == 200
    stages = resp.json()["stages"]
    assert len(stages) == 4
    stage_names = [s["stage"] for s in stages]
    assert stage_names == ["entry", "zone_visit", "billing_queue", "purchase"]


@pytest.mark.asyncio
async def test_funnel_drop_off_never_negative(test_client, test_db):
    # Seed billing queue count > zone visit (data inconsistency edge case)
    for i in range(3):
        bq = make_event(
            event_id=str(uuid.uuid4()), visitor_id=f"VIS_{i:06X}",
            event_type="BILLING_QUEUE_JOIN", zone_id="BILLING_QUEUE",
        )
        entry = make_event(event_id=str(uuid.uuid4()), visitor_id=f"VIS_{i:06X}")
        await test_client.post("/events/ingest", json={"events": [entry, bq]})

    resp = await test_client.get("/stores/STORE_BLR_002/funnel")
    assert resp.status_code == 200
    for stage in resp.json()["stages"]:
        assert stage["drop_off_pct"] >= 0.0
