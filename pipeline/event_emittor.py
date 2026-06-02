# You are building the event emitter for a retail store CCTV analytics pipeline.

# FILE: pipeline/event_emitter.py

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from pydantic import BaseModel, Literal, field_validator


def generate_visitor_id() -> str:
    """Returns 'VIS_' + 6-char uppercase hex."""
    return "VIS_" + uuid.uuid4().hex[:6].upper()


class EventMetadata(BaseModel):
    queue_depth: Optional[int] = None
    sku_zone: Optional[str] = None
    session_seq: int = 1


class Event(BaseModel):
    event_id: str = ""
    store_id: str
    camera_id: str
    visitor_id: str
    event_type: Literal[
        "ENTRY", "EXIT", "ZONE_ENTER", "ZONE_EXIT", "ZONE_DWELL",
        "BILLING_QUEUE_JOIN", "BILLING_QUEUE_ABANDON", "REENTRY"
    ]
    timestamp: str
    zone_id: Optional[str] = None
    dwell_ms: int = 0
    is_staff: bool = False
    confidence: float
    metadata: EventMetadata = EventMetadata()

    def model_post_init(self, __context) -> None:
        if not self.event_id:
            object.__setattr__(self, "event_id", str(uuid.uuid4()))

    @field_validator("confidence")
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, v))

    @field_validator("dwell_ms")
    @classmethod
    def non_negative_dwell(cls, v: int) -> int:
        return max(0, v)


class EventEmitter:
    def __init__(
        self,
        store_id: str,
        output_path: str,
        api_base_url: str,
        post_to_api: bool = True,
        batch_size: int = 50,
    ) -> None:
        self.store_id = store_id
        self.api_base_url = api_base_url.rstrip("/")
        self.post_to_api = post_to_api
        self.batch_size = batch_size
        self._buffer: list[dict] = []
        self._session_seq: dict[str, int] = {}
        self._total_emitted: int = 0

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(str(out), "a", encoding="utf-8")  # noqa: WPS515

    def _next_seq(self, visitor_id: str) -> int:
        self._session_seq[visitor_id] = self._session_seq.get(visitor_id, 0) + 1
        return self._session_seq[visitor_id]

    def emit(
        self,
        *,
        store_id: str,
        camera_id: str,
        visitor_id: str,
        event_type: str,
        timestamp: datetime,
        zone_id: Optional[str] = None,
        dwell_ms: int = 0,
        is_staff: bool = False,
        confidence: float,
        queue_depth: Optional[int] = None,
        sku_zone: Optional[str] = None,
    ) -> dict:
        seq = self._next_seq(visitor_id)
        event = Event(
            event_id=str(uuid.uuid4()),
            store_id=store_id,
            camera_id=camera_id,
            visitor_id=visitor_id,
            event_type=event_type,
            timestamp=timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
            zone_id=zone_id,
            dwell_ms=dwell_ms,
            is_staff=is_staff,
            confidence=confidence,
            metadata=EventMetadata(
                queue_depth=queue_depth,
                sku_zone=sku_zone,
                session_seq=seq,
            ),
        )
        event_dict = event.model_dump()
        self._buffer.append(event_dict)
        self._total_emitted += 1

        # Write to JSONL immediately
        self._file.write(json.dumps(event_dict) + "\n")
        self._file.flush()

        if len(self._buffer) >= self.batch_size:
            self.flush_to_api()

        return event_dict

    def flush_to_api(self) -> tuple[int, int]:
        if not self.post_to_api or not self._buffer:
            return (0, 0)

        payload = {"events": self._buffer}
        try:
            resp = httpx.post(
                f"{self.api_base_url}/events/ingest",
                json=payload,
                timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json()
            accepted = data.get("accepted", len(self._buffer))
            rejected = data.get("rejected", 0)
            self._buffer.clear()
            return (accepted, rejected)
        except Exception as exc:
            print(f"[EventEmitter] Warning: API flush failed: {exc}")
            return (0, len(self._buffer))

    def close(self) -> None:
        self.flush_to_api()
        self._file.close()

    def get_stats(self) -> dict:
        return {"total_emitted": self._total_emitted, "buffer_size": len(self._buffer)}
