# You are building the Re-ID engine for a retail CCTV analytics pipeline.

# FILE: pipeline/reid.py

from datetime import datetime, timedelta, timezone
from typing import Optional

import cv2
import numpy as np

try:
    import torch
    import torchvision.models as tv_models
    import torchvision.transforms as transforms
    from scipy.spatial.distance import cosine as _cosine_dist

    TRANSFORM = transforms.Compose([
        transforms.ToPILImage(),
        transforms.Resize((128, 64)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False


class ReIDEngine:
    def __init__(self, similarity_threshold: float = 0.65) -> None:
        self.similarity_threshold = similarity_threshold
        self.track_embeddings: dict[int, np.ndarray] = {}
        self.exited_embeddings: dict[str, dict] = {}

        self._model = None
        if _TORCH_AVAILABLE:
            try:
                model = tv_models.mobilenet_v3_small(weights="IMAGENET1K_V1")
                # Keep only features + avgpool (drop classifier)
                model.classifier = torch.nn.Identity()
                model.eval()
                self._model = model
            except Exception as exc:
                print(f"[ReID] Model load failed: {exc}. Running without ReID.")

    def extract_embedding(
        self, frame_bgr: np.ndarray, bbox_xyxy: list
    ) -> Optional[np.ndarray]:
        if not _TORCH_AVAILABLE or self._model is None:
            return None
        try:
            h, w = frame_bgr.shape[:2]
            x1, y1, x2, y2 = (
                int(max(0, bbox_xyxy[0])),
                int(max(0, bbox_xyxy[1])),
                int(min(w, bbox_xyxy[2])),
                int(min(h, bbox_xyxy[3])),
            )
            if (x2 - x1) * (y2 - y1) < 400:
                return None
            crop = frame_bgr[y1:y2, x1:x2]
            if crop.size == 0:
                return None
            rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            tensor = TRANSFORM(rgb).unsqueeze(0)  # type: ignore[attr-defined]
            with torch.no_grad():
                feat = self._model(tensor).squeeze().numpy()
            norm = np.linalg.norm(feat)
            if norm == 0:
                return None
            return feat / norm
        except Exception:
            return None

    def update_track_embedding(
        self, track_id: int, frame_bgr: np.ndarray, bbox_xyxy: list, frame_num: int
    ) -> None:
        if frame_num % 10 != 0:
            return
        emb = self.extract_embedding(frame_bgr, bbox_xyxy)
        if emb is not None:
            self.track_embeddings[track_id] = emb

        if len(self.track_embeddings) > 200:
            print("[ReID] WARNING: track_embeddings > 200 entries — possible memory leak.")

    def cosine_similarity(self, a: Optional[np.ndarray], b: Optional[np.ndarray]) -> float:
        if a is None or b is None:
            return 0.0
        if not a.any() or not b.any():
            return 0.0
        try:
            if not _TORCH_AVAILABLE:
                # Pure numpy fallback
                dot = np.dot(a, b)
                return float(dot / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))
            return float(1.0 - _cosine_dist(a, b))
        except Exception:
            return 0.0

    def match_reentry(
        self,
        track_id: int,
        current_time: datetime,
        reentry_window_minutes: int = 30,
    ) -> Optional[str]:
        emb = self.track_embeddings.get(track_id)
        if emb is None:
            return None

        cutoff = current_time - timedelta(minutes=reentry_window_minutes)
        best_score = 0.0
        best_vid: Optional[str] = None

        for visitor_id, data in self.exited_embeddings.items():
            exit_time = data["exit_time"]
            if exit_time.tzinfo is None:
                exit_time = exit_time.replace(tzinfo=timezone.utc)
            if exit_time < cutoff:
                continue
            score = self.cosine_similarity(emb, data["embedding"])
            if score >= self.similarity_threshold and score > best_score:
                best_score = score
                best_vid = visitor_id

        return best_vid

    def match_cross_camera(
        self,
        track_id: int,
        active_tracks: dict,
        own_camera_id: str,
    ) -> Optional[str]:
        emb = self.track_embeddings.get(track_id)
        if emb is None:
            return None

        best_score = 0.0
        best_vid: Optional[str] = None

        for other_tid, info in active_tracks.items():
            if info.get("camera_id") == own_camera_id:
                continue
            other_emb = info.get("embedding")
            score = self.cosine_similarity(emb, other_emb)
            if score >= self.similarity_threshold and score > best_score:
                best_score = score
                best_vid = info.get("visitor_id")

        return best_vid

    def register_exit(
        self, visitor_id: str, track_id: int, exit_time: datetime, camera_id: str
    ) -> None:
        emb = self.track_embeddings.pop(track_id, None)
        if emb is not None:
            self.exited_embeddings[visitor_id] = {
                "embedding": emb,
                "exit_time": exit_time,
                "camera_id": camera_id,
            }

        # Prune entries older than 60 minutes
        cutoff = exit_time - timedelta(minutes=60)
        to_delete = [
            vid
            for vid, data in self.exited_embeddings.items()
            if data["exit_time"] < cutoff
        ]
        for vid in to_delete:
            del self.exited_embeddings[vid]

    def clear_track(self, track_id: int) -> None:
        self.track_embeddings.pop(track_id, None)
