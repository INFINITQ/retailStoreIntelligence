# You are building the event emitter for a retail store CCTV analytics pipeline.

# FILE: pipeline/event_emitter.py
# PURPOSE: Construct, validate, persist, and forward structured analytics events.
# Writes events to a JSONL file and optionally POSTs them in batches to the API.

# TECH: Python 3.11, pydantic==2.10.3, httpx==0.28.1, uuid, json, datetime, pathlib, typing

# EVENT SCHEMA (every event must match this exactly):
# {
#   "event_id": "<uuid-v4-string>",
#   "store_id": "STORE_BLR_002",
#   "camera_id": "CAM_ENTRY_01",
#   "visitor_id": "VIS_<6-char-hex>",
#   "event_type": "ENTRY",          # see catalogue below
#   "timestamp": "2026-04-10T07:00:00Z",  # ISO-8601 UTC
#   "zone_id": null,                # null for ENTRY/EXIT
#   "dwell_ms": 0,
#   "is_staff": false,
#   "confidence": 0.87,
#   "metadata": {
#     "queue_depth": null,          # int; populate for BILLING_QUEUE_JOIN events
#     "sku_zone": null,             # zone label from store_layout.json
#     "session_seq": 1              # ordinal position of event in visitor session
#   }
# }

# EVENT TYPE CATALOGUE:
# ENTRY, EXIT, ZONE_ENTER, ZONE_EXIT, ZONE_DWELL, BILLING_QUEUE_JOIN,
# BILLING_QUEUE_ABANDON, REENTRY

# IMPLEMENT THE FOLLOWING:

# 1. Pydantic model `EventMetadata(BaseModel)`:
#    - queue_depth: Optional[int] = None
#    - sku_zone: Optional[str] = None
#    - session_seq: int = 1

# 2. Pydantic model `Event(BaseModel)`:
#    - event_id: str (default_factory = lambda: str(uuid.uuid4()))
#    - store_id: str
#    - camera_id: str
#    - visitor_id: str
#    - event_type: Literal["ENTRY","EXIT","ZONE_ENTER","ZONE_EXIT","ZONE_DWELL",
#                           "BILLING_QUEUE_JOIN","BILLING_QUEUE_ABANDON","REENTRY"]
#    - timestamp: str  # ISO-8601 UTC string
#    - zone_id: Optional[str] = None
#    - dwell_ms: int = 0
#    - is_staff: bool = False
#    - confidence: float
#    - metadata: EventMetadata = EventMetadata()

#    Add validator: confidence must be clamped to [0.0, 1.0].
#    Add validator: dwell_ms must be >= 0.

# 3. `class EventEmitter:`

#    `__init__(self, store_id: str, output_path: str, api_base_url: str,
#              post_to_api: bool = True, batch_size: int = 50):`
#    - Create output_path parent dirs if needed (pathlib.Path.mkdir parents=True, exist_ok=True).
#    - Open the JSONL file for append.
#    - `self._buffer: list[dict]` — in-memory queue before flushing.
#    - `self._session_seq: dict[str, int]` — maps visitor_id → current session_seq counter.
#    - `self._total_emitted: int = 0`

#    `_next_seq(self, visitor_id: str) -> int:`
#    - Increment and return session_seq for this visitor_id.

#    `emit(self, *, store_id: str, camera_id: str, visitor_id: str, event_type: str,
#          timestamp: datetime, zone_id: str | None = None, dwell_ms: int = 0,
#          is_staff: bool = False, confidence: float, queue_depth: int | None = None,
#          sku_zone: str | None = None) -> dict:`
#    - Construct Event using Pydantic.
#    - timestamp formatted as .strftime("%Y-%m-%dT%H:%M:%SZ")
#    - Append serialized event to self._buffer.
#    - Write to JSONL file immediately (one JSON line per event, flush after each write).
#    - If len(buffer) >= batch_size: call flush_to_api().
#    - Return the event dict.

#    `flush_to_api(self) -> tuple[int, int]:`
#    - If post_to_api is False or buffer is empty, return (0, 0).
#    - POST buffer to f"{api_base_url}/events/ingest" using httpx (sync, timeout=10s).
#    - Body: {"events": [list of event dicts]}.
#    - On success (2xx): clear buffer, return (accepted, rejected) from response JSON.
#    - On error: log warning, keep buffer, return (0, len(buffer)).

#    `close(self) -> None:`
#    - flush_to_api() for remaining buffer.
#    - Close JSONL file.

#    `get_stats(self) -> dict:`
#    - Returns {"total_emitted": int, "buffer_size": int}.

# IMPORTS NEEDED:
#   pydantic (BaseModel, field_validator, Literal), uuid, json, datetime,
#   pathlib (Path), httpx, typing (Optional), os

# VISITOR ID FORMAT: generate_visitor_id() helper function at module level:
#   Returns "VIS_" + uuid.uuid4().hex[:6].upper()
