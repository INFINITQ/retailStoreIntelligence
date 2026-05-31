# You are building the staff detector for a retail store CCTV analytics pipeline.

# FILE: pipeline/staff_detector.py
# PURPOSE: Classify whether a detected person is a staff member using two heuristics:
# (1) HSV color analysis of the upper-body crop — staff wear distinct uniform colors.
# (2) Zone ubiquity — a track seen in 5+ distinct zones within a session is likely staff.

# TECH: Python 3.11, OpenCV (cv2), numpy==1.26.4

# CONTEXT:
# - Retail staff at Purplle stores typically wear a consistent uniform (often black or a single brand color).
# - Faces are blurred in all footage — classification must rely only on clothing region.
# - The function receives a BGR crop (numpy array) of the bounding box.
# - This is a best-effort classifier; confidence < 0.6 should be treated as uncertain.

# IMPLEMENT THE FOLLOWING:

# 1. Module-level constants:
#    ```python
#    # HSV ranges for common retail uniform colors (black/dark, white/light, specific brand colors)
#    # Format: (lower_hsv, upper_hsv, label)
#    UNIFORM_COLOR_RANGES = [
#        ((0, 0, 0),   (180, 60, 60),  "dark_uniform"),      # black/dark clothing
#        ((0, 0, 200), (180, 30, 255), "white_uniform"),     # white clothing
#        ((100, 50, 50), (140, 255, 200), "blue_uniform"),   # blue/navy uniform
#    ]
#    UNIFORM_COVERAGE_THRESHOLD = 0.35  # >35% of upper body in uniform color = staff
#    ```

# 2. `class StaffDetector:`

#    `__init__(self, coverage_threshold: float = 0.35):`
#    - Store coverage_threshold.
#    - Initialise `self._track_zones: dict[int, set[str]]` to track zones per track_id.

#    `classify_by_color(self, frame_bgr: np.ndarray, bbox_xyxy: list[float]) -> tuple[bool, float]:`
#    - Crop the bounding box from frame_bgr.
#    - Take only the upper 40% of the crop as "upper body" region.
#    - Convert to HSV.
#    - For each UNIFORM_COLOR_RANGES entry, create a binary mask and compute pixel coverage %.
#    - If any single color's coverage exceeds `coverage_threshold`, return (True, coverage_pct).
#    - Otherwise return (False, max_coverage_pct_seen).

#    `update_zone_history(self, track_id: int, zone_id: str | None) -> None:`
#    - If zone_id is not None, add it to self._track_zones[track_id].

#    `classify_by_zone_ubiquity(self, track_id: int, ubiquity_threshold: int = 5) -> bool:`
#    - Return True if track_id has been seen in >= ubiquity_threshold distinct zones.

#    `is_staff(self, frame_bgr: np.ndarray, bbox_xyxy: list[float], track_id: int) -> tuple[bool, float]:`
#    - Calls classify_by_color first.
#    - If color says True, return (True, confidence).
#    - Also check classify_by_zone_ubiquity as a secondary signal.
#    - If both signals agree: staff. If only one: set confidence = 0.55 (uncertain).
#    - Return (is_staff_bool, confidence_float).

#    `reset_track(self, track_id: int) -> None:`
#    - Remove track_id from self._track_zones.

# IMPORTS NEEDED: cv2, numpy as np, typing (Optional)

# EDGE CASES:
# - Bbox outside frame bounds: clip the crop to frame dimensions before processing.
# - Empty crop (zero-area bbox): return (False, 0.0).
# - Grayscale or single-channel frame: convert to BGR first.
