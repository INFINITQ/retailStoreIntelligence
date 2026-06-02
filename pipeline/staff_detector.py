# You are building the staff detector for a retail store CCTV analytics pipeline.

# FILE: pipeline/staff_detector.py

from typing import Optional, Tuple

import cv2
import numpy as np

# HSV ranges for common retail uniform colors
UNIFORM_COLOR_RANGES = [
    ((0, 0, 0),     (180, 60, 60),   "dark_uniform"),   # black / dark clothing
    ((0, 0, 200),   (180, 30, 255),  "white_uniform"),  # white clothing
    ((100, 50, 50), (140, 255, 200), "blue_uniform"),   # blue / navy uniform
]
UNIFORM_COVERAGE_THRESHOLD = 0.35


class StaffDetector:
    def __init__(self, coverage_threshold: float = UNIFORM_COVERAGE_THRESHOLD) -> None:
        self.coverage_threshold = coverage_threshold
        self._track_zones: dict[int, set[str]] = {}

    def classify_by_color(
        self,
        frame_bgr: np.ndarray,
        bbox_xyxy: list,
    ) -> Tuple[bool, float]:
        """HSV-based upper-body colour analysis."""
        h, w = frame_bgr.shape[:2]
        x1, y1, x2, y2 = (
            int(max(0, bbox_xyxy[0])),
            int(max(0, bbox_xyxy[1])),
            int(min(w, bbox_xyxy[2])),
            int(min(h, bbox_xyxy[3])),
        )

        if x2 <= x1 or y2 <= y1:
            return False, 0.0

        crop = frame_bgr[y1:y2, x1:x2]
        if crop.size == 0:
            return False, 0.0

        # Ensure 3-channel BGR
        if len(crop.shape) == 2:
            crop = cv2.cvtColor(crop, cv2.COLOR_GRAY2BGR)

        # Upper 40% of bounding box = upper body
        upper_h = max(1, int(crop.shape[0] * 0.4))
        upper = crop[:upper_h, :]

        hsv = cv2.cvtColor(upper, cv2.COLOR_BGR2HSV)
        total_pixels = hsv.shape[0] * hsv.shape[1]
        if total_pixels == 0:
            return False, 0.0

        max_coverage = 0.0
        for lower, upper_bound, _ in UNIFORM_COLOR_RANGES:
            mask = cv2.inRange(hsv, np.array(lower), np.array(upper_bound))
            coverage = float(np.count_nonzero(mask)) / total_pixels
            if coverage > max_coverage:
                max_coverage = coverage
            if coverage >= self.coverage_threshold:
                return True, coverage

        return False, max_coverage

    def update_zone_history(self, track_id: int, zone_id: Optional[str]) -> None:
        if zone_id is not None:
            self._track_zones.setdefault(track_id, set()).add(zone_id)

    def classify_by_zone_ubiquity(
        self, track_id: int, ubiquity_threshold: int = 5
    ) -> bool:
        return len(self._track_zones.get(track_id, set())) >= ubiquity_threshold

    def is_staff(
        self,
        frame_bgr: np.ndarray,
        bbox_xyxy: list,
        track_id: int,
    ) -> Tuple[bool, float]:
        color_staff, color_conf = self.classify_by_color(frame_bgr, bbox_xyxy)
        zone_staff = self.classify_by_zone_ubiquity(track_id)

        if color_staff and zone_staff:
            return True, max(color_conf, 0.9)
        if color_staff:
            return True, color_conf
        if zone_staff:
            return True, 0.55  # uncertain signal
        return False, color_conf

    def reset_track(self, track_id: int) -> None:
        self._track_zones.pop(track_id, None)
