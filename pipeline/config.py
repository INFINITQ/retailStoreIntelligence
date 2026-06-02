# You are building the configuration module for a retail store CCTV analytics pipeline called Store Intelligence.

# FILE: pipeline/config.py
# PURPOSE: Central configuration loader for the detection pipeline.

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class PipelineConfig:
    store_layout_path: str = "data/store_layout.json"
    store_mapping_path: str = "data/store_mapping.json"
    pos_csv_path: str = "data/pos_transactions.csv"
    output_dir: str = "data/events"
    api_base_url: str = "http://localhost:8000"
    confidence_threshold: float = 0.35
    reid_similarity_threshold: float = 0.65
    dwell_threshold_seconds: int = 30
    frame_skip: int = 3
    inference_width: int = 640
    inference_height: int = 360
    yolo_model: str = "yolov8n.pt"
    post_to_api: bool = True
    api_batch_size: int = 50
    pos_correlation_window_minutes: int = 5
    queue_spike_threshold: int = 5
    log_level: str = "INFO"

    def __repr__(self) -> str:  # noqa: D105
        lines = ["PipelineConfig("]
        for f in self.__dataclass_fields__:  # type: ignore[attr-defined]
            lines.append(f"  {f}={getattr(self, f)!r},")
        lines.append(")")
        return "\n".join(lines)


cfg = PipelineConfig(
    store_layout_path=os.getenv("STORE_LAYOUT_PATH", "data/store_layout.json"),
    store_mapping_path=os.getenv("STORE_MAPPING_PATH", "data/store_mapping.json"),
    pos_csv_path=os.getenv("POS_CSV_PATH", "data/pos_transactions.csv"),
    output_dir=os.getenv("OUTPUT_DIR", "data/events"),
    api_base_url=os.getenv("API_BASE_URL", "http://localhost:8000"),
    confidence_threshold=float(os.getenv("CONFIDENCE_THRESHOLD", "0.35")),
    reid_similarity_threshold=float(os.getenv("REID_SIMILARITY_THRESHOLD", "0.65")),
    dwell_threshold_seconds=int(os.getenv("DWELL_THRESHOLD_SECONDS", "30")),
    frame_skip=int(os.getenv("FRAME_SKIP", "3")),
    inference_width=int(os.getenv("INFERENCE_WIDTH", "640")),
    inference_height=int(os.getenv("INFERENCE_HEIGHT", "360")),
    yolo_model=os.getenv("YOLO_MODEL", "yolov8n.pt"),
    post_to_api=os.getenv("POST_TO_API", "true").lower() == "true",
    api_batch_size=int(os.getenv("API_BATCH_SIZE", "50")),
    pos_correlation_window_minutes=int(os.getenv("POS_CORRELATION_WINDOW_MINUTES", "5")),
    queue_spike_threshold=int(os.getenv("QUEUE_SPIKE_THRESHOLD", "5")),
    log_level=os.getenv("LOG_LEVEL", "INFO"),
)
