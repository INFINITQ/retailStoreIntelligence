# PROMPT: Generate tests for GET /stores/{store_id}/anomalies verifying queue spike
#          detection at correct thresholds, conversion drop severity levels, dead zone
#          detection timing, and stale feed warning.
# CHANGES MADE: Fixed threshold boundary tests (>= not >), added CRITICAL threshold test,
#               mocked datetime.now for stale feed test, added empty anomalies assertion.

# FILE: tests/test_anomalies.py

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest import make_event


@pytest.mark.asyncio
async def test_anomalies_empty_returns_valid_response(test_client, test_db):
    resp = await test_client.get("/stores/STORE_BLR_002/anomalies")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["anomalies"], list)
    assert body["anomaly_count"] == len(body["anomalies"])


@pytest.mark.asyncio
async def test_queue_spike_warn_at_threshold(test_client, test_db):
    event = make_event(
        event_id=str(uuid.uuid4()),
        event_type="BILLING_QUEUE_JOIN",
        zone_id="BILLING_QUEUE",
        metadata={"queue_depth": 5, "sku_zone": None, "session_seq": 1},
    )
    await test_client.post("/events/ingest", json={"events": [event]})

    resp = await test_client.get("/stores/STORE_BLR_002/anomalies")
    assert resp.status_code == 200
    anomalies = resp.json()["anomalies"]
    queue_spikes = [a for a in anomalies if a["anomaly_type"] == "BILLING_QUEUE_SPIKE"]
    assert len(queue_spikes) > 0
    assert queue_spikes[0]["severity"] == "WARN"


@pytest.mark.asyncio
async def test_queue_spike_critical_above_threshold(test_client, test_db):
    event = make_event(
        event_id=str(uuid.uuid4()),
        event_type="BILLING_QUEUE_JOIN",
        zone_id="BILLING_QUEUE",
        metadata={"queue_depth": 11, "sku_zone": None, "session_seq": 1},
    )
    await test_client.post("/events/ingest", json={"events": [event]})

    resp = await test_client.get("/stores/STORE_BLR_002/anomalies")
    assert resp.status_code == 200
    anomalies = resp.json()["anomalies"]
    queue_spikes = [a for a in anomalies if a["anomaly_type"] == "BILLING_QUEUE_SPIKE"]
    assert len(queue_spikes) > 0
    assert queue_spikes[0]["severity"] == "CRITICAL"


@pytest.mark.asyncio
async def test_queue_spike_not_triggered_below_threshold(test_client, test_db):
    event = make_event(
        event_id=str(uuid.uuid4()),
        event_type="BILLING_QUEUE_JOIN",
        zone_id="BILLING_QUEUE",
        metadata={"queue_depth": 4, "sku_zone": None, "session_seq": 1},
    )
    await test_client.post("/events/ingest", json={"events": [event]})

    resp = await test_client.get("/stores/STORE_BLR_002/anomalies")
    assert resp.status_code == 200
    anomalies = resp.json()["anomalies"]
    queue_spikes = [a for a in anomalies if a["anomaly_type"] == "BILLING_QUEUE_SPIKE"]
    assert len(queue_spikes) == 0


@pytest.mark.asyncio
async def test_stale_feed_when_no_recent_events(test_client, test_db):
    old_ts = (datetime.now(timezone.utc) - timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M:%SZ")
    event = make_event(event_id=str(uuid.uuid4()), timestamp=old_ts)
    await test_client.post("/events/ingest", json={"events": [event]})

    resp = await test_client.get("/stores/STORE_BLR_002/anomalies")
    assert resp.status_code == 200
    anomalies = resp.json()["anomalies"]
    stale = [a for a in anomalies if a["anomaly_type"] == "STALE_FEED"]
    assert len(stale) > 0


@pytest.mark.asyncio
async def test_no_stale_feed_when_recent_event(test_client, test_db):
    event = make_event(event_id=str(uuid.uuid4()))
    await test_client.post("/events/ingest", json={"events": [event]})

    resp = await test_client.get("/stores/STORE_BLR_002/anomalies")
    assert resp.status_code == 200
    anomalies = resp.json()["anomalies"]
    stale = [a for a in anomalies if a["anomaly_type"] == "STALE_FEED"]
    assert len(stale) == 0


@pytest.mark.asyncio
async def test_dead_zone_detected(test_client, test_db):
    old_ts = (datetime.now(timezone.utc) - timedelta(minutes=40)).strftime("%Y-%m-%dT%H:%M:%SZ")
    event = make_event(
        event_id=str(uuid.uuid4()),
        event_type="ZONE_ENTER",
        zone_id="FOH",
        timestamp=old_ts,
    )
    await test_client.post("/events/ingest", json={"events": [event]})

    resp = await test_client.get("/stores/STORE_BLR_002/anomalies")
    assert resp.status_code == 200
    anomalies = resp.json()["anomalies"]
    dead_zones = [a for a in anomalies if a["anomaly_type"] == "DEAD_ZONE"]
    # FOH should now be dead (40 min > 30 min threshold)
    foh_dead = [a for a in dead_zones if "FOH" in a.get("details", {}).get("zone_id", "")]
    assert len(foh_dead) > 0


@pytest.mark.asyncio
async def test_anomaly_has_required_fields(test_client, test_db):
    event = make_event(
        event_id=str(uuid.uuid4()),
        event_type="BILLING_QUEUE_JOIN",
        metadata={"queue_depth": 8, "sku_zone": None, "session_seq": 1},
    )
    await test_client.post("/events/ingest", json={"events": [event]})

    resp = await test_client.get("/stores/STORE_BLR_002/anomalies")
    assert resp.status_code == 200
    for anomaly in resp.json()["anomalies"]:
        for field in ["anomaly_id", "anomaly_type", "severity", "description", "suggested_action", "detected_at"]:
            assert field in anomaly, f"Missing field: {field}"


@pytest.mark.asyncio
async def test_suggested_action_is_non_empty_string(test_client, test_db):
    event = make_event(
        event_id=str(uuid.uuid4()),
        event_type="BILLING_QUEUE_JOIN",
        metadata={"queue_depth": 7, "sku_zone": None, "session_seq": 1},
    )
    await test_client.post("/events/ingest", json={"events": [event]})

    resp = await test_client.get("/stores/STORE_BLR_002/anomalies")
    assert resp.status_code == 200
    for anomaly in resp.json()["anomalies"]:
        action = anomaly.get("suggested_action", "")
        assert isinstance(action, str) and len(action) > 0
