# You are writing the Pydantic v2 schemas for a retail store CCTV analytics API.

# FILE: app/models/schemas.py
# PURPOSE: All request/response Pydantic models. These are separate from the SQLAlchemy ORM
# models in db_models.py.

# TECH: Python 3.11, pydantic==2.10.3

# IMPLEMENT THE FOLLOWING MODELS:

# --- INGEST ---
# 1. `class EventMetadata(BaseModel):`
#    - queue_depth: Optional[int] = None
#    - sku_zone: Optional[str] = None
#    - session_seq: int = 1

# 2. `class EventIn(BaseModel):`
#    - event_id: str
#    - store_id: str
#    - camera_id: str
#    - visitor_id: str
#    - event_type: Literal["ENTRY","EXIT","ZONE_ENTER","ZONE_EXIT","ZONE_DWELL",
#                           "BILLING_QUEUE_JOIN","BILLING_QUEUE_ABANDON","REENTRY"]
#    - timestamp: str  # ISO-8601 UTC string e.g. "2026-04-10T07:00:00Z"
#    - zone_id: Optional[str] = None
#    - dwell_ms: int = 0
#    - is_staff: bool = False
#    - confidence: float  # must be 0.0 ≤ confidence ≤ 1.0
#    - metadata: EventMetadata = EventMetadata()
#    Add @field_validator("confidence") to clamp to [0.0, 1.0].
#    Add @field_validator("dwell_ms") to reject negative values.
#    Add @field_validator("timestamp") to verify it can be parsed as ISO-8601.

# 3. `class IngestRequest(BaseModel):`
#    - events: List[EventIn]  # max 500 items
#    Add @model_validator to reject len(events) > 500.

# 4. `class IngestError(BaseModel):`
#    - event_id: str
#    - reason: str

# 5. `class IngestResponse(BaseModel):`
#    - accepted: int
#    - rejected: int
#    - errors: List[IngestError] = []

# --- METRICS ---
# 6. `class ZoneDwell(BaseModel):`
#    - zone_id: str
#    - display_name: str
#    - avg_dwell_seconds: float
#    - visit_count: int

# 7. `class MetricsResponse(BaseModel):`
#    - store_id: str
#    - window_start: str  # ISO timestamp
#    - window_end: str
#    - unique_visitors: int
#    - conversion_rate: float   # 0.0–1.0
#    - avg_dwell_per_zone: List[ZoneDwell]
#    - queue_depth: int
#    - abandonment_rate: float  # 0.0–1.0
#    - total_transactions: int

# --- FUNNEL ---
# 8. `class FunnelStage(BaseModel):`
#    - stage: str  # "entry" | "zone_visit" | "billing_queue" | "purchase"
#    - count: int
#    - drop_off_pct: float  # % lost from previous stage

# 9. `class FunnelResponse(BaseModel):`
#    - store_id: str
#    - window_start: str
#    - window_end: str
#    - stages: List[FunnelStage]
#    - total_sessions: int

# --- HEATMAP ---
# 10. `class ZoneHeatmap(BaseModel):`
#     - zone_id: str
#     - display_name: str
#     - visit_count: int
#     - avg_dwell_ms: float
#     - normalized_score: float  # 0–100
#     - data_confidence: bool    # True if >= 20 sessions

# 11. `class HeatmapResponse(BaseModel):`
#     - store_id: str
#     - window_start: str
#     - window_end: str
#     - zones: List[ZoneHeatmap]

# --- ANOMALIES ---
# 12. `class Anomaly(BaseModel):`
#     - anomaly_id: str  # uuid
#     - anomaly_type: str  # BILLING_QUEUE_SPIKE | CONVERSION_DROP | DEAD_ZONE | STALE_FEED
#     - severity: Literal["INFO", "WARN", "CRITICAL"]
#     - description: str
#     - suggested_action: str
#     - detected_at: str  # ISO timestamp
#     - details: dict = {}

# 13. `class AnomalyResponse(BaseModel):`
#     - store_id: str
#     - checked_at: str
#     - anomalies: List[Anomaly]
#     - anomaly_count: int

# --- HEALTH ---
# 14. `class StoreHealth(BaseModel):`
#     - store_id: str
#     - last_event_timestamp: Optional[str]
#     - minutes_since_last_event: Optional[float]
#     - status: str  # "OK" | "STALE_FEED" | "NO_DATA"

# 15. `class HealthResponse(BaseModel):`
#     - status: Literal["HEALTHY", "DEGRADED", "UNHEALTHY"]
#     - timestamp: str
#     - database: str    # "ok" | "error"
#     - redis: str       # "ok" | "error"
#     - stores: List[StoreHealth]
#     - version: str = "1.0.0"

# IMPORTS NEEDED: pydantic (BaseModel, field_validator, model_validator, Literal),
# typing (Optional, List), datetime
