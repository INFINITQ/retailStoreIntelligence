# You are writing the stores router for a FastAPI retail analytics API.

# FILE: app/routers/stores.py

import json
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.schemas import AnomalyResponse, FunnelResponse, HeatmapResponse, MetricsResponse
from app.services.anomalies import compute_anomalies
from app.services.funnel import compute_funnel
from app.services.heatmap import compute_heatmap
from app.services.metrics import compute_metrics

router = APIRouter(prefix="/stores", tags=["stores"])


@lru_cache(maxsize=1)
def _load_known_store_ids() -> set[str]:
    try:
        with open(settings.store_layout_path, "r", encoding="utf-8") as f:
            layout = json.load(f)
        store_id = layout.get("store_id")
        if store_id:
            return {store_id}
    except Exception:
        pass

    # Fallback: read from store_mapping.json
    try:
        with open(settings.store_mapping_path, "r", encoding="utf-8") as f:
            mapping = json.load(f)
        return {s["api_store_id"] for s in mapping.get("stores", [])}
    except Exception:
        return set()


def _get_store_or_404(store_id: str) -> str:
    known = _load_known_store_ids()
    if store_id not in known:
        raise HTTPException(status_code=404, detail=f"Store {store_id} not found")
    return store_id


@router.get("/{store_id}/metrics", response_model=MetricsResponse)
async def get_metrics(
    store_id: str,
    window_hours: int = Query(default=24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
) -> MetricsResponse:
    _get_store_or_404(store_id)
    try:
        return await compute_metrics(db, store_id, window_hours)
    except OperationalError:
        raise HTTPException(status_code=503, detail={"error": "Database unavailable"})


@router.get("/{store_id}/funnel", response_model=FunnelResponse)
async def get_funnel(
    store_id: str,
    window_hours: int = Query(default=24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
) -> FunnelResponse:
    _get_store_or_404(store_id)
    try:
        return await compute_funnel(db, store_id, window_hours)
    except OperationalError:
        raise HTTPException(status_code=503, detail={"error": "Database unavailable"})


@router.get("/{store_id}/heatmap", response_model=HeatmapResponse)
async def get_heatmap(
    store_id: str,
    window_hours: int = Query(default=24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
) -> HeatmapResponse:
    _get_store_or_404(store_id)
    try:
        return await compute_heatmap(db, store_id, window_hours)
    except OperationalError:
        raise HTTPException(status_code=503, detail={"error": "Database unavailable"})


@router.get("/{store_id}/anomalies", response_model=AnomalyResponse)
async def get_anomalies(
    store_id: str,
    db: AsyncSession = Depends(get_db),
) -> AnomalyResponse:
    _get_store_or_404(store_id)
    try:
        return await compute_anomalies(db, store_id)
    except OperationalError:
        raise HTTPException(status_code=503, detail={"error": "Database unavailable"})
