# You are building the configuration module for a retail store CCTV analytics pipeline called Store Intelligence.

# FILE: pipeline/config.py
# PURPOSE: Central configuration loader for the detection pipeline. Reads all settings from environment variables (via python-dotenv) with sensible defaults. Exposes a single frozen dataclass instance called `cfg` that all other pipeline modules import.

# TECH: Python 3.11, python-dotenv==1.0.1, dataclasses, os

# IMPLEMENT THE FOLLOWING:

# 1. Call `load_dotenv()` at module level to load a `.env` file if present.

# 2. Define a frozen dataclass `PipelineConfig` with these fields and types:
#    - store_layout_path: str = "data/store_layout.json"
#    - store_mapping_path: str = "data/store_mapping.json"
#    - pos_csv_path: str = "data/pos_transactions.csv"
#    - output_dir: str = "data/events"
#    - api_base_url: str = "http://localhost:8000"
#    - confidence_threshold: float = 0.35         # min YOLO detection confidence
#    - reid_similarity_threshold: float = 0.65    # cosine similarity for Re-ID match
#    - dwell_threshold_seconds: int = 30          # seconds before emitting ZONE_DWELL
#    - frame_skip: int = 3                        # process every Nth frame (CPU optimisation)
#    - inference_width: int = 640                 # resize width before YOLO inference
#    - inference_height: int = 360               # resize height before YOLO inference
#    - yolo_model: str = "yolov8n.pt"            # nano model for CPU speed
#    - post_to_api: bool = True                   # whether to POST events to API
#    - api_batch_size: int = 50                   # events per API POST batch
#    - pos_correlation_window_minutes: int = 5    # POS correlation time window
#    - queue_spike_threshold: int = 5             # queue depth to flag spike
#    - log_level: str = "INFO"

# 3. Instantiate the dataclass as a module-level singleton:
#    `cfg = PipelineConfig()`
#    where each field reads from `os.getenv(FIELD_NAME_UPPERCASE, default_value)`.
#    Cast numeric types explicitly (float(), int()) from env strings.

# 4. Add a `__repr__` that prints all config values (for startup logging).

# IMPORTS NEEDED: os, dataclasses (dataclass, field), python-dotenv (load_dotenv)

# No external dependencies beyond the standard library and python-dotenv.
