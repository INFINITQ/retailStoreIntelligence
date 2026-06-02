# You are building the queue depth tracker for a retail store CCTV analytics pipeline.

# FILE: pipeline/queue_tracker.py

from collections import deque
from datetime import datetime
from typing import Optional


class QueueTracker:
    def __init__(self, spike_threshold: int = 5) -> None:
        self.spike_threshold = spike_threshold
        self.current_depth: int = 0
        self.queue_members: set[int] = set()
        self.depth_history: deque = deque(maxlen=100)
        self.spike_active: bool = False

    def update(self, active_billing_track_ids: set, timestamp: datetime) -> dict:
        old_members = set(self.queue_members)
        new_depth = len(active_billing_track_ids)

        self.depth_history.append((timestamp, new_depth))
        self.current_depth = new_depth
        self.queue_members = set(active_billing_track_ids)

        newly_joined = active_billing_track_ids - old_members
        newly_left = old_members - active_billing_track_ids

        spike_started = False
        spike_ended = False

        if new_depth >= self.spike_threshold and not self.spike_active:
            self.spike_active = True
            spike_started = True
        elif new_depth < self.spike_threshold and self.spike_active:
            self.spike_active = False
            spike_ended = True

        return {
            "depth": new_depth,
            "spike_started": spike_started,
            "spike_ended": spike_ended,
            "newly_joined": newly_joined,
            "newly_left": newly_left,
        }

    def get_current_depth(self) -> int:
        return self.current_depth

    def get_rolling_avg(self, window_frames: int = 30) -> float:
        if not self.depth_history:
            return 0.0
        recent = list(self.depth_history)[-window_frames:]
        return sum(d for _, d in recent) / len(recent)

    def reset(self) -> None:
        self.queue_members = set()
        self.current_depth = 0
