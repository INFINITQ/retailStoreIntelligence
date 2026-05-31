# You are writing the ingestion service for a retail store CCTV analytics API.

# FILE: app/services/ingestion.py
# PURPOSE: Core business logic for POST /events/ingest. Validates, deduplicates (idempotent
# by event_id), persists events to DB, updates VisitorSession table, and publishes to Redis
# pub/sub for the live dashboard.

# TECH: Python 3.11, sqlalchemy.ext.asyncio, redis.asyncio, pydantic

# IMPLEMENT:

# 1. `@dataclass class IngestResult:`
#    - accepted: int = 0
#    - rejected: int = 0
#    - errors: list = field(default_factory=list)

# 2. `async def ingest_event_batch(db: AsyncSession, events: List[EventIn]) -> IngestResult:`
#    - result = IngestResult()
#    - Bulk-fetch existing event_ids from DB to detect duplicates:
#      `existing_ids = set(row[0] for row in await db.execute(
#         select(Event.event_id).where(Event.event_id.in_([e.event_id for e in events]))
#       ))`
#    - For each event in events:
#      a. If event.event_id in existing_ids: skip (idempotent), do NOT count as error.
#         Increment result.accepted (already accepted previously).
#      b. Validate event via Pydantic (already validated by FastAPI, but double-check
#         confidence bounds).
#      c. On validation error: result.rejected++; append IngestError to result.errors; continue.
#      d. Create ORM Event object from EventIn fields. metadata_json = event.metadata.model_dump().
#      e. db.add(event_orm)
#    - await db.flush() — write all at once.
#    - For each valid event: call await _update_visitor_session(db, event).
#    - await db.commit().
#    - Publish to Redis: await _publish_events(events_as_dicts) — fire and forget.
#    - Return result.

# 3. `async def _update_visitor_session(db: AsyncSession, event: EventIn) -> None:`
#    - On ENTRY or REENTRY: upsert VisitorSession with visitor_id, store_id, entry_timestamp,
#      is_reentry=(event_type=="REENTRY"), is_staff=event.is_staff.
#      session_id = str(uuid.uuid4()).
#    - On EXIT: set exit_timestamp on the open session (exit_timestamp IS NULL) for this visitor_id.
#    - On ZONE_ENTER: append zone_id to session.zones_visited JSON array.
#    - On ZONE_DWELL: add dwell_ms to session.total_dwell_ms.
#    - Use INSERT...ON CONFLICT DO NOTHING for ENTRY to avoid race conditions.
#    - Queries must be async (await db.execute()).

# 4. `async def _publish_events(events: list[dict]) -> None:`
#    - Connect to Redis using redis.asyncio.from_url(settings.redis_url).
#    - Publish JSON payload to channel "store_events" for each event.
#    - Wrap in try/except; log error but do not raise (Redis failure must not block ingest).

# IMPORTS NEEDED:
#   sqlalchemy.ext.asyncio (AsyncSession), sqlalchemy (select, insert, update),
#   sqlalchemy.dialects.postgresql (insert as pg_insert),
#   redis.asyncio, uuid, json, dataclasses (dataclass, field), datetime (datetime, timezone),
#   app.models.db_models (Event, VisitorSession),
#   app.models.schemas (EventIn, IngestError), app.config (settings)