# PROMPT: Generate tests for GET /stores/{store_id}/metrics verifying unique visitor count,
#          conversion rate computation, staff exclusion, zero-purchase handling, and
#          avg_dwell_per_zone output structure.
# CHANGES MADE: Added zero-visitor edge case test, fixed window_hours parameter usage,
#               corrected expected conversion_rate precision.

# FILE: tests/test_metrics.py

import uuid
from datetime import datetime, timezone

import pytest

from app.models.db_models import VisitorSession
from tests.conftest import make_event, seed_pos_transaction


@pytest.mark.asyncio
async def test_metrics_empty_store_returns_zeros(test_client, test_db):
    resp = await test_client.get("/stores/STORE_BLR_002/metrics")
    assert resp.status_code == 200
    body = resp.json()
    assert body["unique_visitors"] == 0
    assert body["conversion_rate"] == 0.0
    assert body["queue_depth"] == 0
    assert body["abandonment_rate"] == 0.0
    assert isinstance(body["avg_dwell_per_zone"], list)


@pytest.mark.asyncio
async def test_metrics_counts_unique_visitors(test_client, test_db):
    visitors = [f"VIS_{uuid.uuid4().hex[:6].upper()}" for _ in range(3)]
    events = [make_event(event_id=str(uuid.uuid4()), visitor_id=vid) for vid in visitors]
    await test_client.post("/events/ingest", json={"events": events})

    resp = await test_client.get("/stores/STORE_BLR_002/metrics")
    assert resp.status_code == 200
    assert resp.json()["unique_visitors"] == 3


@pytest.mark.asyncio
async def test_metrics_excludes_staff(test_client, test_db):
    customer1 = make_event(event_id=str(uuid.uuid4()), visitor_id="VIS_CUST01", is_staff=False)
    customer2 = make_event(event_id=str(uuid.uuid4()), visitor_id="VIS_CUST02", is_staff=False)
    staff = make_event(event_id=str(uuid.uuid4()), visitor_id="VIS_STAFF1", is_staff=True)

    await test_client.post("/events/ingest", json={"events": [customer1, customer2, staff]})

    resp = await test_client.get("/stores/STORE_BLR_002/metrics")
    assert resp.status_code == 200
    assert resp.json()["unique_visitors"] == 2


@pytest.mark.asyncio
async def test_metrics_conversion_rate(test_client, test_db):
    visitors = [f"VIS_{uuid.uuid4().hex[:6].upper()}" for _ in range(4)]
    events = [make_event(event_id=str(uuid.uuid4()), visitor_id=vid) for vid in visitors]
    await test_client.post("/events/ingest", json={"events": events})

    # Mark 2 sessions as converted directly in DB
    from sqlalchemy import select
    result = await test_db.execute(
        select(VisitorSession).where(
            VisitorSession.visitor_id.in_(visitors[:2])
        )
    )
    sessions = result.scalars().all()
    for s in sessions:
        s.is_converted = True
    await test_db.commit()

    resp = await test_client.get("/stores/STORE_BLR_002/metrics")
    assert resp.status_code == 200
    rate = resp.json()["conversion_rate"]
    assert abs(rate - 0.5) < 0.01


@pytest.mark.asyncio
async def test_metrics_zero_purchases_not_null(test_client, test_db):
    events = [make_event(event_id=str(uuid.uuid4()), visitor_id=f"VIS_{i:06X}") for i in range(5)]
    await test_client.post("/events/ingest", json={"events": events})

    resp = await test_client.get("/stores/STORE_BLR_002/metrics")
    assert resp.status_code == 200
    assert resp.json()["conversion_rate"] == 0.0
    assert resp.json()["unique_visitors"] == 5


@pytest.mark.asyncio
async def test_metrics_avg_dwell_per_zone(test_client, test_db):
    events = [
        make_event(
            event_id=str(uuid.uuid4()),
            event_type="ZONE_DWELL",
            zone_id="FOH",
            dwell_ms=30000,
            visitor_id=f"VIS_{i:06X}",
        )
        for i in range(3)
    ]
    await test_client.post("/events/ingest", json={"events": events})

    resp = await test_client.get("/stores/STORE_BLR_002/metrics")
    assert resp.status_code == 200
    dwell_zones = {z["zone_id"]: z for z in resp.json().get("avg_dwell_per_zone", [])}
    assert "FOH" in dwell_zones
    assert abs(dwell_zones["FOH"]["avg_dwell_seconds"] - 30.0) < 1.0


@pytest.mark.asyncio
async def test_metrics_unknown_store_returns_404(test_client, test_db):
    resp = await test_client.get("/stores/STORE_UNKNOWN_999/metrics")
    assert resp.status_code == 404
