# You are building the zone classifier for a retail store CCTV analytics pipeline.

# FILE: pipeline/zone_classifier.py
# PURPOSE: Given a camera ID and a bounding-box foot-point (bottom-center of bbox in pixel coords), determine which zone the person is in. Also detect entry/exit line crossings. Uses shapely for polygon containment.

# TECH: Python 3.11, shapely==2.0.6, json, typing

# CONTEXT:
# - store_layout.json defines zones. Each zone has a `cameras` dict mapping camera_id → `{"polygon": [[x,y], ...]}`.
# - Polygons are in pixel coordinates for 1920×1080 resolution.
# - The entry camera (CAM_ENTRY_01) has an `entry_line` in its camera config: `{"direction": "horizontal", "y_threshold": 820, "entry_direction": "bottom_to_top"}`.
# - Zones with `is_entry_exit: true` are the ENTRY_THRESHOLD zone — used for crossing detection, not dwell.
# - Zones with `is_billing: true` are billing/queue zones.

# IMPLEMENT THE FOLLOWING FUNCTIONS:

# 1. `class ZoneClassifier:`

#    `__init__(self, layout_path: str):`
#    - Load and parse store_layout.json.
#    - Build a dict `self.camera_zones: dict[str, list[tuple[str, Polygon]]]` mapping
#      camera_id → list of (zone_id, shapely.Polygon). Sort so billing zones come last
#      (least priority for general classification).
#    - Build a dict `self.zone_meta: dict[str, dict]` mapping zone_id → zone metadata
#      (is_billing, is_entry_exit, sku_zone, display_name).
#    - Build a dict `self.entry_lines: dict[str, dict]` mapping camera_id → entry_line config
#      (only for cameras that have entry_line defined).

#    `classify_zone(self, camera_id: str, foot_x: float, foot_y: float) -> str | None:`
#    - Compute which zone polygon contains the point (foot_x, foot_y) for the given camera_id.
#    - Returns the zone_id of the first matching polygon (check non-entry-exit zones first).
#    - Returns None if no zone matches.

#    `check_entry_crossing(self, camera_id: str, prev_foot_y: float, curr_foot_y: float) -> str | None:`
#    - Only valid for cameras with `entry_line` defined (CAM_ENTRY_01).
#    - Reads y_threshold from the entry_line config.
#    - entry_direction = "bottom_to_top" means: prev_foot_y > y_threshold AND curr_foot_y <= y_threshold → "ENTRY".
#    - Reverse crossing → "EXIT".
#    - Returns "ENTRY", "EXIT", or None.

#    `get_zone_meta(self, zone_id: str) -> dict:`
#    - Returns the metadata dict for a zone. Returns empty dict if not found.

#    `get_billing_zones(self, camera_id: str) -> list[str]:`
#    - Returns list of zone_ids visible from camera_id that have is_billing=True.

#    `get_zones_for_camera(self, camera_id: str) -> list[str]:`
#    - Returns all zone_ids visible from the given camera.

# 2. Standalone helper:
#    `get_foot_point(bbox_xyxy: list[float]) -> tuple[float, float]:`
#    - bbox_xyxy = [x1, y1, x2, y2]
#    - Returns bottom-center: ((x1+x2)/2, y2)

# IMPORTS NEEDED: json, shapely.geometry (Point, Polygon), typing (Optional)

# ERROR HANDLING: If a polygon has fewer than 3 points, skip it with a warning print.
# If layout_path doesn't exist, raise FileNotFoundError with a helpful message.
