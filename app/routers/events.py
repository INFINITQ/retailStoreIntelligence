# You are writing the events router for a FastAPI retail analytics API.

# FILE: app/routers/events.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.schemas import IngestRequest, IngestResponse
from app.services.ingestion import ingest_event_batch

router = APIRouter(prefix="/events", tags=["events"])


@router.post("/ingest", response_model=IngestResponse, status_code=200)
async def ingest_events(
    payload: IngestRequest, db: AsyncSession = Depends(get_db)
) -> IngestResponse:
    if not payload.events:
        raise HTTPException(status_code=400, detail="Empty event batch")
    if len(payload.events) > 500:
        raise HTTPException(status_code=400, detail="Batch exceeds 500 events")

    try:
        result = await ingest_event_batch(db, payload.events)
    except OperationalError:
        raise HTTPException(
            status_code=503,
            detail={"error": "Database unavailable", "suggestion": "Retry in a few seconds"},
        )

    return IngestResponse(
        accepted=result.accepted,
        rejected=result.rejected,
        errors=result.errors,
    )
