# You are writing the events router for a FastAPI retail analytics API.

# FILE: app/routers/events.py
# PURPOSE: Defines the POST /events/ingest endpoint. Validates batch, delegates to
# ingestion service, returns structured success/error response.

# TECH: Python 3.11, fastapi, sqlalchemy.ext.asyncio

# IMPLEMENT:

# 1. `router = APIRouter(prefix="/events", tags=["events"])`

# 2. `@router.post("/ingest", response_model=IngestResponse, status_code=200)`
#    `async def ingest_events(payload: IngestRequest, db: AsyncSession = Depends(get_db)) -> IngestResponse:`
#    - Validate payload.events is not empty; if empty, raise HTTPException(400, "Empty event batch").
#    - Validate len(payload.events) <= 500; if over, raise HTTPException(400, "Batch exceeds 500 events").
#    - Call: result = await ingest_event_batch(db, payload.events)
#    - Return IngestResponse(accepted=result.accepted, rejected=result.rejected, errors=result.errors)
#    - If DB throws an OperationalError (DB unavailable): raise HTTPException(503,
#      detail={"error": "Database unavailable", "suggestion": "Retry in a few seconds"})

# IMPORTS NEEDED:
#   fastapi (APIRouter, HTTPException, Depends), sqlalchemy.ext.asyncio (AsyncSession),
#   app.database (get_db), app.models.schemas (IngestRequest, IngestResponse),
#   app.services.ingestion (ingest_event_batch)
