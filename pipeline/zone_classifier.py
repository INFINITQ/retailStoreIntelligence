# You are building the zone classifier for a retail store CCTV analytics pipeline.

# FILE: pipeline/zone_classifier.py

import json
from typing import Optional

from shapely.geometry import Point, Polygon


def get_foot_point(bbox_xyxy: list) -> tuple:
    """Return bottom-center of a bounding box: ((x1+x2)/2, y2)."""
    x1, y1, x2, y2 = bbox_xyxy
    return ((x1 + x2) / 2, y2)


class ZoneClassifier:
    def __init__(self, layout_path: str) -> None:
        try:
            with open(layout_path, "r", encoding="utf-8") as f:
                layout = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(
                f"store_layout.json not found at {layout_path!r}. "
                "Did you set --layout correctly?"
            )

        self.zone_meta: dict[str, dict] = {}
        self.camera_zones: dict[str, list[tuple[str, Polygon]]] = {}
        self.entry_lines: dict[str, dict] = {}

        for zone in layout.get("zones", []):
            zid = zone["zone_id"]
            self.zone_meta[zid] = {
                "is_billing": zone.get("is_billing", False),
                "is_entry_exit": zone.get("is_entry_exit", False),
                "sku_zone": zone.get("sku_zone"),
                "display_name": zone.get("display_name", zid),
            }

            for cam_id, cam_data in zone.get("cameras", {}).items():
                coords = cam_data.get("polygon", [])
                if len(coords) < 3:
                    print(f"[ZoneClassifier] Warning: zone {zid} cam {cam_id} has <3 polygon points — skipped.")
                    continue
                poly = Polygon(coords)
                self.camera_zones.setdefault(cam_id, []).append((zid, poly))

        # Sort so non-entry-exit, non-billing zones come first (higher priority)
        for cam_id in self.camera_zones:
            self.camera_zones[cam_id].sort(
                key=lambda item: (
                    self.zone_meta.get(item[0], {}).get("is_billing", False),
                    self.zone_meta.get(item[0], {}).get("is_entry_exit", False),
                )
            )

        # Load entry lines from cameras section
        for cam in layout.get("cameras", []):
            if "entry_line" in cam:
                self.entry_lines[cam["camera_id"]] = cam["entry_line"]

    def classify_zone(self, camera_id: str, foot_x: float, foot_y: float) -> Optional[str]:
        """Return zone_id for the point, or None if not in any zone."""
        pt = Point(foot_x, foot_y)
        for zone_id, poly in self.camera_zones.get(camera_id, []):
            if self.zone_meta.get(zone_id, {}).get("is_entry_exit", False):
                continue  # skip entry/exit threshold for general classification
            if poly.contains(pt):
                return zone_id
        return None

    def check_entry_crossing(
        self, camera_id: str, prev_foot_y: float, curr_foot_y: float
    ) -> Optional[str]:
        """Detect direction crossing of the entry threshold line."""
        entry_cfg = self.entry_lines.get(camera_id)
        if entry_cfg is None:
            return None

        y_thresh = entry_cfg["y_threshold"]
        direction = entry_cfg.get("entry_direction", "bottom_to_top")

        if direction == "bottom_to_top":
            if prev_foot_y > y_thresh and curr_foot_y <= y_thresh:
                return "ENTRY"
            if prev_foot_y <= y_thresh and curr_foot_y > y_thresh:
                return "EXIT"
        else:
            if prev_foot_y < y_thresh and curr_foot_y >= y_thresh:
                return "ENTRY"
            if prev_foot_y >= y_thresh and curr_foot_y < y_thresh:
                return "EXIT"

        return None

    def get_zone_meta(self, zone_id: str) -> dict:
        return self.zone_meta.get(zone_id, {})

    def get_billing_zones(self, camera_id: str) -> list[str]:
        return [
            zone_id
            for zone_id, _ in self.camera_zones.get(camera_id, [])
            if self.zone_meta.get(zone_id, {}).get("is_billing", False)
        ]

    def get_zones_for_camera(self, camera_id: str) -> list[str]:
        return [zone_id for zone_id, _ in self.camera_zones.get(camera_id, [])]
