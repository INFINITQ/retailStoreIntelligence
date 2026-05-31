# You are building the Re-ID (re-identification) engine for a retail CCTV analytics pipeline.

# FILE: pipeline/reid.py
# PURPOSE: Extract lightweight appearance embeddings from person bounding-box crops using
# MobileNetV3-Small (CPU-optimised). Match embeddings using cosine similarity to:
# (a) detect re-entry of the same physical person after an EXIT event, and
# (b) deduplicate the same person across overlapping cameras.

# TECH: Python 3.11, torch (CPU), torchvision==0.20.1, numpy==1.26.4, scipy==1.14.1

# CONTEXT:
# - All faces are blurred; the model must rely entirely on clothing appearance and body shape.
# - This runs on CPU — the model must be lightweight. Use MobileNetV3-Small pretrained on ImageNet.
# - Embeddings are extracted from the penultimate layer (before the final classifier), giving a
#   576-dim feature vector.
# - Embeddings are cached per track_id and updated every 10 frames.
# - Cosine similarity >= reid_similarity_threshold (default 0.65) = same person.
# - Re-entry window: only compare against exits in the last 30 minutes.
# - Cross-camera dedup window: only compare against active tracks from other cameras.

# IMPLEMENT THE FOLLOWING:

# 1. Module-level:
#    - Transform pipeline for pre-processing:
#      `TRANSFORM = transforms.Compose([transforms.Resize((128, 64)), transforms.ToTensor(),
#       transforms.Normalize(mean=[0.485,0.456,0.406], std=[0.229,0.224,0.225])])`

# 2. `class ReIDEngine:`

#    `__init__(self, similarity_threshold: float = 0.65):`
#    - Load `torchvision.models.mobilenet_v3_small(weights="IMAGENET1K_V1")`.
#    - Remove the final classifier layer: keep only the `features` + `avgpool` layers.
#    - Set model to eval(), wrap in `torch.no_grad()` context.
#    - `self.similarity_threshold = similarity_threshold`
#    - `self.track_embeddings: dict[int, np.ndarray]` — cache per active track_id.
#    - `self.exited_embeddings: dict[str, dict]` — maps visitor_id →
#      {"embedding": np.ndarray, "exit_time": datetime, "camera_id": str}

#    `extract_embedding(self, frame_bgr: np.ndarray, bbox_xyxy: list[float]) -> np.ndarray | None:`
#    - Crop bbox from frame_bgr; skip if crop area < 400 px².
#    - Convert BGR→RGB, apply TRANSFORM, run through model.
#    - L2-normalise the output vector. Return as 1-D numpy array.
#    - Return None on any error.

#    `update_track_embedding(self, track_id: int, frame_bgr: np.ndarray,
#                             bbox_xyxy: list[float], frame_num: int) -> None:`
#    - Only run extraction if frame_num % 10 == 0 (update every 10 frames).
#    - Store result in self.track_embeddings[track_id].

#    `cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:`
#    - scipy.spatial.distance.cosine gives distance; return 1 - distance.
#    - Return 0.0 if either vector is None or all-zero.

#    `match_reentry(self, track_id: int, current_time: datetime,
#                    reentry_window_minutes: int = 30) -> str | None:`
#    - Get embedding for track_id from self.track_embeddings (return None if not cached).
#    - Compare against all entries in self.exited_embeddings where exit_time is within window.
#    - Return visitor_id of the best match if similarity >= threshold, else None.

#    `match_cross_camera(self, track_id: int, active_tracks: dict,
#                         own_camera_id: str) -> str | None:`
#    - active_tracks: dict[track_id → {"camera_id": str, "visitor_id": str, "embedding": np.ndarray}]
#    - Find active tracks from cameras other than own_camera_id.
#    - Return visitor_id of best-matching active track if similarity >= threshold, else None.

#    `register_exit(self, visitor_id: str, track_id: int, exit_time: datetime,
#                    camera_id: str) -> None:`
#    - Move embedding from track_embeddings to exited_embeddings.
#    - Prune exited_embeddings entries older than 60 minutes.

#    `clear_track(self, track_id: int) -> None:`
#    - Remove track_id from self.track_embeddings.

# IMPORTS NEEDED:
#   torch, torchvision.models, torchvision.transforms as transforms,
#   numpy as np, cv2, scipy.spatial.distance, datetime, typing (Optional)

# ERROR HANDLING: All model inference in try/except; return None on failure.
# Print a warning if track_embeddings grows beyond 200 entries (memory leak guard).
