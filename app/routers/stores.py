# You are writing the stores router for a FastAPI retail analytics API.

# FILE: app/routers/stores.py
# PURPOSE: Defines four analytics endpoints for a given store:
#   GET /stores/{store_id}/metrics
#   GET /stores/{store_id}/funnel
#   GET /stores/{store_id}/heatmap
#   GET /stores/{store_id}/anomalies
# Each delegates to the corresponding service module.

# TECH: Python 3.11, fastapi, sqlalchemy.ext.asyncio

# IMPLEMENT:

# 1. `router = APIRouter(prefix="/stores", tags=["stores"])`

# 2. Common dependency `get_store_or_404`:
#    - Accept store_id: str as path param.
#    - Load known store IDs from store_layout.json (read file once, cache with lru_cache).
#    - If store_id not in known stores: raise HTTPException(404, f"Store {store_id} not found").

# 3. Optional query param `window_hours: int = Query(default=24, ge=1, le=168)`
#    available on all endpoints (default: last 24 hours of data).

# 4. `@router.get("/{store_id}/metrics", response_model=MetricsResponse)`
#    `async def get_metrics(store_id: str, window_hours: int = Query(default=24),
#                           db: AsyncSession = Depends(get_db)) -> MetricsResponse:`
#    - Call: return await compute_metrics(db, store_id, window_hours)
#    - Wrap DB errors in HTTPException(503).

# 5. `@router.get("/{store_id}/funnel", response_model=FunnelResponse)`
#    `async def get_funnel(store_id: str, window_hours: int = Query(default=24),
#                          db: AsyncSession = Depends(get_db)) -> FunnelResponse:`
#    - Call: return await compute_funnel(db, store_id, window_hours)

# 6. `@router.get("/{store_id}/heatmap", response_model=HeatmapResponse)`
#    `async def get_heatmap(store_id: str, window_hours: int = Query(default=24),
#                           db: AsyncSession = Depends(get_db)) -> HeatmapResponse:`
#    - Call: return await compute_heatmap(db, store_id, window_hours)

# 7. `@router.get("/{store_id}/anomalies", response_model=AnomalyResponse)`
#    `async def get_anomalies(store_id: str,
#                             db: AsyncSession = Depends(get_db)) -> AnomalyResponse:`
#    - Call: return await compute_anomalies(db, store_id)

# IMPORTS NEEDED:
#   fastapi (APIRouter, HTTPException, Depends, Query), sqlalchemy.ext.asyncio (AsyncSession),
#   functools (lru_cache), json, app.database (get_db),
#   app.models.schemas (MetricsResponse, FunnelResponse, HeatmapResponse, AnomalyResponse),
#   app.services.metrics (compute_metrics), app.services.funnel (compute_funnel),
#   app.services.heatmap (compute_heatmap), app.services.anomalies (compute_anomalies),
#   app.config (settings)
