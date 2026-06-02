# You are writing the ingestion service for a retail store CCTV analytics API.

# FILE: app/services/ingestion.py
# PURPOSE: Core business logic for POST /events/ingest. Validates, deduplicates (idempotent
# by event_id), persists events to DB, updates VisitorSession table, and publishes to Redis
# pub/sub for the live dashboard.

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List

import redis.asyncio as aioredis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.db_models import Event, VisitorSession
from app.models.schemas import EventIn, IngestError


@dataclass
class IngestResult:
    accepted: int = 0
    rejected: int = 0
    errors: list = field(default_factory=list)


async def ingest_event_batch(db: AsyncSession, events: List[EventIn]) -> IngestResult:
    result = IngestResult()

    # Bulk-fetch existing event_ids for deduplication
    event_ids = [e.event_id for e in events]
    existing_rows = await db.execute(
        select(Event.event_id).where(Event.event_id.in_(event_ids))
    )
    existing_ids: set = {row[0] for row in existing_rows}

    new_event_orms: list[Event] = []
    valid_new_events: list[EventIn] = []

    for event in events:
        # Idempotent: already exists → count as accepted, skip insertion
        if event.event_id in existing_ids:
            result.accepted += 1
            continue

        # Validate confidence bounds (belt-and-suspenders)
        if not (0.0 <= event.confidence <= 1.0):
            result.rejected += 1
            result.errors.append(
                IngestError(
                    event_id=event.event_id,
                    reason=f"confidence={event.confidence} out of [0, 1]",
                )
            )
            continue

        # Build ORM row
        event_orm = Event(
            event_id=event.event_id,
            store_id=event.store_id,
            camera_id=event.camera_id,
            visitor_id=event.visitor_id,
            event_type=event.event_type,
            timestamp=datetime.fromisoformat(event.timestamp.replace("Z", "+00:00")),
            zone_id=event.zone_id,
            dwell_ms=event.dwell_ms,
            is_staff=event.is_staff,
            confidence=event.confidence,
            metadata_json=event.metadata.model_dump(),
        )
        db.add(event_orm)
        new_event_orms.append(event_orm)
        valid_new_events.append(event)
        result.accepted += 1

    # Write all new rows at once
    await db.flush()

    # Update visitor sessions for each valid new event
    for event in valid_new_events:
        await _update_visitor_session(db, event)

    await db.commit()

    # Publish to Redis — fire and forget
    if valid_new_events:
        events_as_dicts = [e.model_dump() for e in valid_new_events]
        await _publish_events(events_as_dicts)

    return result


async def _update_visitor_session(db: AsyncSession, event: EventIn) -> None:
    """Upsert VisitorSession state based on event type."""
    ts = datetime.fromisoformat(event.timestamp.replace("Z", "+00:00"))

    if event.event_type in ("ENTRY", "REENTRY"):
        # Find existing open session for this visitor+store
        existing = await db.execute(
            select(VisitorSession).where(
                VisitorSession.visitor_id == event.visitor_id,
                VisitorSession.store_id == event.store_id,
                VisitorSession.exit_timestamp.is_(None),
            )
        )
        existing_session = existing.scalars().first()

        if existing_session is None:
            new_session = VisitorSession(
                session_id=str(uuid.uuid4()),
                store_id=event.store_id,
                visitor_id=event.visitor_id,
                entry_timestamp=ts,
                is_reentry=(event.event_type == "REENTRY"),
                is_staff=event.is_staff,
                zones_visited=[],
                total_dwell_ms=0,
            )
            db.add(new_session)

    elif event.event_type == "EXIT":
        # Close the most recent open session
        open_session = await db.execute(
            select(VisitorSession).where(
                VisitorSession.visitor_id == event.visitor_id,
                VisitorSession.store_id == event.store_id,
                VisitorSession.exit_timestamp.is_(None),
            )
        )
        session_row = open_session.scalars().first()
        if session_row is not None:
            session_row.exit_timestamp = ts

    elif event.event_type == "ZONE_ENTER" and event.zone_id:
        # Append zone to the open session's zones_visited list
        open_session = await db.execute(
            select(VisitorSession).where(
                VisitorSession.visitor_id == event.visitor_id,
                VisitorSession.store_id == event.store_id,
                VisitorSession.exit_timestamp.is_(None),
            )
        )
        session_row = open_session.scalars().first()
        if session_row is not None:
            visited = list(session_row.zones_visited or [])
            if event.zone_id not in visited:
                visited.append(event.zone_id)
            session_row.zones_visited = visited

    elif event.event_type == "ZONE_DWELL" and event.dwell_ms > 0:
        # Add dwell time to the open session
        open_session = await db.execute(
            select(VisitorSession).where(
                VisitorSession.visitor_id == event.visitor_id,
                VisitorSession.store_id == event.store_id,
                VisitorSession.exit_timestamp.is_(None),
            )
        )
        session_row = open_session.scalars().first()
        if session_row is not None:
            session_row.total_dwell_ms = (session_row.total_dwell_ms or 0) + event.dwell_ms


async def _publish_events(events: list[dict]) -> None:
    """Publish events to Redis pub/sub. Failure is non-fatal."""
    try:
        client = aioredis.from_url(settings.redis_url, decode_responses=True)
        async with client:
            for evt in events:
                await client.publish("store_events", json.dumps(evt))
    except Exception as exc:  # noqa: BLE001
        # Redis failure must not block ingest
        import logging
        logging.getLogger(__name__).warning("Redis publish failed: %s", exc)