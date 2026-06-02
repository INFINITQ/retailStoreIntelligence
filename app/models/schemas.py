# You are writing the Pydantic v2 schemas for a retail store CCTV analytics API.

# FILE: app/models/schemas.py
# PURPOSE: All request/response Pydantic models. These are separate from the SQLAlchemy ORM
# models in db_models.py.

# TECH: Python 3.11, pydantic==2.10.3

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, field_validator, model_validator


# --- INGEST ---

class EventMetadata(BaseModel):
    queue_depth: Optional[int] = None
    sku_zone: Optional[str] = None
    session_seq: int = 1


class EventIn(BaseModel):
    event_id: str
    store_id: str
    camera_id: str
    visitor_id: str
    event_type: Literal[
        "ENTRY",
        "EXIT",
        "ZONE_ENTER",
        "ZONE_EXIT",
        "ZONE_DWELL",
        "BILLING_QUEUE_JOIN",
        "BILLING_QUEUE_ABANDON",
        "REENTRY",
    ]
    timestamp: str  # ISO-8601 UTC string e.g. "2026-04-10T07:00:00Z"
    zone_id: Optional[str] = None
    dwell_ms: int = 0
    is_staff: bool = False
    confidence: float
    metadata: EventMetadata = EventMetadata()

    @field_validator("confidence")
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        if v < 0.0 or v > 1.0:
            raise ValueError(f"confidence must be between 0.0 and 1.0, got {v}")
        return v

    @field_validator("dwell_ms")
    @classmethod
    def non_negative_dwell(cls, v: int) -> int:
        if v < 0:
            raise ValueError(f"dwell_ms must be >= 0, got {v}")
        return v

    @field_validator("timestamp")
    @classmethod
    def parse_iso_timestamp(cls, v: str) -> str:
        try:
            # Accept both "Z" suffix and "+00:00"
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"timestamp is not valid ISO-8601: {v!r}") from exc
        return v


class IngestRequest(BaseModel):
    events: List[EventIn]

    @model_validator(mode="after")
    def check_batch_size(self) -> "IngestRequest":
        if len(self.events) > 500:
            raise ValueError("Batch exceeds 500 events")
        return self


class IngestError(BaseModel):
    event_id: str
    reason: str


class IngestResponse(BaseModel):
    accepted: int
    rejected: int
    errors: List[IngestError] = []


# --- METRICS ---

class ZoneDwell(BaseModel):
    zone_id: str
    display_name: str
    avg_dwell_seconds: float
    visit_count: int


class MetricsResponse(BaseModel):
    store_id: str
    window_start: str
    window_end: str
    unique_visitors: int
    conversion_rate: float
    avg_dwell_per_zone: List[ZoneDwell]
    queue_depth: int
    abandonment_rate: float
    total_transactions: int


# --- FUNNEL ---

class FunnelStage(BaseModel):
    stage: str  # "entry" | "zone_visit" | "billing_queue" | "purchase"
    count: int
    drop_off_pct: float


class FunnelResponse(BaseModel):
    store_id: str
    window_start: str
    window_end: str
    stages: List[FunnelStage]
    total_sessions: int


# --- HEATMAP ---

class ZoneHeatmap(BaseModel):
    zone_id: str
    display_name: str
    visit_count: int
    avg_dwell_ms: float
    normalized_score: float
    data_confidence: bool


class HeatmapResponse(BaseModel):
    store_id: str
    window_start: str
    window_end: str
    zones: List[ZoneHeatmap]


# --- ANOMALIES ---

class Anomaly(BaseModel):
    anomaly_id: str
    anomaly_type: str
    severity: Literal["INFO", "WARN", "CRITICAL"]
    description: str
    suggested_action: str
    detected_at: str
    details: dict = {}


class AnomalyResponse(BaseModel):
    store_id: str
    checked_at: str
    anomalies: List[Anomaly]
    anomaly_count: int


# --- HEALTH ---

class StoreHealth(BaseModel):
    store_id: str
    last_event_timestamp: Optional[str]
    minutes_since_last_event: Optional[float]
    status: str  # "OK" | "STALE_FEED" | "NO_DATA"


class HealthResponse(BaseModel):
    status: Literal["HEALTHY", "DEGRADED", "UNHEALTHY"]
    timestamp: str
    database: str
    redis: str
    stores: List[StoreHealth]
    version: str = "1.0.0"
