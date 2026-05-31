# You are building the queue depth tracker for a retail store CCTV analytics pipeline.

# FILE: pipeline/queue_tracker.py
# PURPOSE: Track the number of people simultaneously present in billing/queue zones.
# Maintain a rolling queue depth and flag spike events.

# TECH: Python 3.11, collections (deque), datetime, typing

# IMPLEMENT THE FOLLOWING:

# 1. `class QueueTracker:`

#    `__init__(self, spike_threshold: int = 5):`
#    - `self.spike_threshold = spike_threshold`
#    - `self.current_depth: int = 0`
#    - `self.queue_members: set[int]` — set of track_ids currently in billing/queue zone.
#    - `self.depth_history: deque` — deque(maxlen=100) of (timestamp, depth) tuples
#      for rolling average.
#    - `self.spike_active: bool = False`

#    `update(self, active_billing_track_ids: set[int], timestamp: datetime) -> dict:`
#    - active_billing_track_ids: set of track_ids currently in BILLING or BILLING_QUEUE zone.
#    - Compute new depth = len(active_billing_track_ids).
#    - Append (timestamp, new_depth) to depth_history.
#    - Update self.current_depth and self.queue_members.
#    - Detect spike: if new_depth >= spike_threshold and not self.spike_active → set spike_active=True.
#    - Detect spike end: if new_depth < spike_threshold and self.spike_active → set spike_active=False.
#    - Return dict: {"depth": int, "spike_started": bool, "spike_ended": bool,
#                    "newly_joined": set[int], "newly_left": set[int]}
#    - newly_joined = active_billing_track_ids - old queue_members
#    - newly_left = old queue_members - active_billing_track_ids

#    `get_current_depth(self) -> int:`
#    - Returns self.current_depth.

#    `get_rolling_avg(self, window_frames: int = 30) -> float:`
#    - Average depth over the last `window_frames` entries in depth_history.
#    - Returns 0.0 if history is empty.

#    `reset(self) -> None:`
#    - Clear queue_members, reset current_depth to 0.

# IMPORTS NEEDED: collections (deque), datetime, typing (Optional)
