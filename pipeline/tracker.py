# You are building the track lifecycle manager for a retail store CCTV analytics pipeline.

# FILE: pipeline/tracker.py

import copy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np


@dataclass
class TrackState:
    track_id: int
    visitor_id: str
    camera_id: str
    store_id: str
    current_zone: Optional[str] = None
    zone_entry_frame: Optional[int] = None
    last_dwell_emit_frame: Optional[int] = None
    entry_frame: int = 0
    is_staff: bool = False
    embedding: Optional[np.ndarray] = field(default=None, repr=False)
    session_seq: int = 0
    last_seen_frame: int = 0
    has_entered: bool = False
    zones_visited: list = field(default_factory=list)
    prev_foot_y: Optional[float] = None  # for entry/exit crossing


class TrackManager:
    def __init__(
        self,
        camera_id: str,
        store_id: str,
        fps: float,
        dwell_threshold_seconds: int = 30,
        lost_track_frames: int = 90,
    ) -> None:
        self.camera_id = camera_id
        self.store_id = store_id
        self.fps = fps
        self.dwell_threshold_frames = int(dwell_threshold_seconds * fps)
        self.lost_track_frames = lost_track_frames
        self.active_tracks: dict[int, TrackState] = {}
        self.frame_counter: int = 0

    def update(self, detections: list[dict]) -> dict:
        """
        detections: list of {
            "track_id": int, "bbox_xyxy": list[float],
            "confidence": float, "zone_id": str|None,
            "is_staff": bool, "visitor_id": str,
            "foot_y": float
        }
        """
        current_ids = {d["track_id"] for d in detections}

        new_tracks: list[TrackState] = []
        updated_tracks: list[TrackState] = []
        zone_entries: list[tuple[TrackState, str]] = []
        zone_exits: list[tuple[TrackState, str, int]] = []  # (track, zone_id, dwell_ms)
        dwell_events: list[tuple[TrackState, str, int]] = []

        for det in detections:
            tid = det["track_id"]
            zone_id = det.get("zone_id")
            is_new = tid not in self.active_tracks

            if is_new:
                ts = TrackState(
                    track_id=tid,
                    visitor_id=det.get("visitor_id", f"VIS_{tid:06X}"),
                    camera_id=self.camera_id,
                    store_id=self.store_id,
                    entry_frame=self.frame_counter,
                    last_seen_frame=self.frame_counter,
                    is_staff=det.get("is_staff", False),
                    current_zone=zone_id,
                    zone_entry_frame=self.frame_counter if zone_id else None,
                    prev_foot_y=det.get("foot_y"),
                )
                self.active_tracks[tid] = ts
                new_tracks.append(ts)
            else:
                ts = self.active_tracks[tid]
                prev_zone = ts.current_zone
                ts.last_seen_frame = self.frame_counter
                ts.is_staff = det.get("is_staff", ts.is_staff)
                ts.prev_foot_y = det.get("foot_y", ts.prev_foot_y)

                # Zone transition
                if zone_id != prev_zone:
                    # Zone exit from previous zone
                    if prev_zone is not None and ts.zone_entry_frame is not None:
                        dwell_ms = int(
                            (self.frame_counter - ts.zone_entry_frame) / max(self.fps, 1) * 1000
                        )
                        zone_exits.append((ts, prev_zone, dwell_ms))
                    # Zone entry into new zone
                    if zone_id is not None:
                        zone_entries.append((ts, zone_id))
                        ts.zone_entry_frame = self.frame_counter
                        ts.last_dwell_emit_frame = self.frame_counter
                        if zone_id not in ts.zones_visited:
                            ts.zones_visited.append(zone_id)
                    else:
                        ts.zone_entry_frame = None
                    ts.current_zone = zone_id
                else:
                    # Same zone — check dwell emit
                    if zone_id and ts.zone_entry_frame is not None:
                        frames_in_zone = self.frame_counter - ts.zone_entry_frame
                        last_emit = ts.last_dwell_emit_frame or ts.zone_entry_frame
                        frames_since_last = self.frame_counter - last_emit
                        if (
                            frames_in_zone >= self.dwell_threshold_frames
                            and frames_since_last >= self.dwell_threshold_frames
                        ):
                            dwell_ms = int(
                                self.dwell_threshold_frames / max(self.fps, 1) * 1000
                            )
                            dwell_events.append((ts, zone_id, dwell_ms))
                            ts.last_dwell_emit_frame = self.frame_counter

                updated_tracks.append(ts)

        # Lost tracks — not seen for > lost_track_frames
        lost_tracks: list[TrackState] = []
        for tid, ts in list(self.active_tracks.items()):
            if tid not in current_ids:
                frames_absent = self.frame_counter - ts.last_seen_frame
                if frames_absent > self.lost_track_frames:
                    lost_tracks.append(ts)
                    del self.active_tracks[tid]

        self.frame_counter += 1

        return {
            "new_tracks": new_tracks,
            "updated_tracks": updated_tracks,
            "lost_tracks": lost_tracks,
            "zone_entries": zone_entries,
            "zone_exits": zone_exits,
            "dwell_events": dwell_events,
        }

    def get_active_billing_track_ids(self, billing_zone_ids: list[str]) -> set[int]:
        return {
            tid
            for tid, ts in self.active_tracks.items()
            if ts.current_zone in billing_zone_ids
        }

    def get_all_active(self) -> dict[int, TrackState]:
        return copy.copy(self.active_tracks)

    def remove_track(self, track_id: int) -> Optional[TrackState]:
        return self.active_tracks.pop(track_id, None)

    def clear_all(self) -> list[TrackState]:
        remaining = list(self.active_tracks.values())
        self.active_tracks.clear()
        return remaining
