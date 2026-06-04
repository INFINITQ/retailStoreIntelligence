# You are building the main detection orchestration script for a retail store CCTV analytics pipeline.

# FILE: pipeline/detect.py

import argparse
import glob
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("detect")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Store Intelligence CCTV Detection Pipeline")
    parser.add_argument("--clips-dir", required=True, help="Directory containing CCTV clip files")
    parser.add_argument("--output-dir", default="data/events", help="Output directory for JSONL events")
    parser.add_argument("--api-url", default="http://localhost:8000", help="Store Intelligence API URL")
    parser.add_argument("--store-id", default="STORE_BLR_002", help="Store ID to use in events")
    parser.add_argument("--layout", default="data/store_layout.json", help="Path to store_layout.json")
    parser.add_argument("--mapping", default="data/store_mapping.json", help="Path to store_mapping.json")
    parser.add_argument("--pos-data", default="data/pos_transactions.csv", help="Path to POS CSV")
    parser.add_argument("--no-api-post", action="store_true", help="Disable posting to API")
    parser.add_argument("--frame-skip", type=int, default=3, help="Process every Nth frame")
    parser.add_argument("--confidence", type=float, default=0.35, help="YOLO confidence threshold")
    return parser.parse_args()


def assign_clips_to_cameras(clips_dir: str, store_mapping: dict) -> dict[str, str]:
    """Match clip files to camera IDs by keyword, falling back to index order."""
    extensions = ["*.mp4", "*.avi", "*.mov", "*.MP4", "*.AVI", "*.MOV"]
    all_clips: list[str] = []
    for ext in extensions:
        all_clips.extend(glob.glob(str(Path(clips_dir) / ext)))
    all_clips = sorted(set(all_clips))

    cameras = []
    for store in store_mapping.get("stores", []):
        cameras = store.get("cameras", [])
        break

    clip_map: dict[str, str] = {}

    for cam in cameras:
        cam_id = cam["camera_id"]
        keywords = [k.lower() for k in cam.get("clip_filename_keywords", [])]
        matched = None

        for clip_path in all_clips:
            fname = Path(clip_path).name.lower()
            if any(kw in fname for kw in keywords):
                matched = clip_path
                break

        if matched is None:
            # Fall back to clip_index
            idx = cam.get("clip_index", 0)
            if idx < len(all_clips):
                matched = all_clips[idx]

        if matched:
            clip_map[cam_id] = matched
            log.info("Camera %s → %s", cam_id, matched)
        else:
            log.warning("No clip found for camera %s — skipping.", cam_id)

    return clip_map


def process_clip(
    clip_path: str,
    camera_id: str,
    store_id: str,
    clip_start_utc: str,
    model,
    zone_classifier,
    staff_detector,
    reid_engine,
    queue_tracker,
    track_manager,
    event_emitter,
    cfg,
) -> list[dict]:
    """Process a single CCTV clip and return all emitted events."""
    try:
        import cv2
        import numpy as np
        from tqdm import tqdm
    except ImportError as exc:
        log.error("Missing dependency: %s. Install requirements-pipeline.txt.", exc)
        return []

    cap = cv2.VideoCapture(clip_path)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video clip: {clip_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 15.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    try:
        clip_start = datetime.fromisoformat(clip_start_utc.replace("Z", "+00:00"))
    except Exception:
        clip_start = datetime.now(timezone.utc)

    billing_zones = zone_classifier.get_billing_zones(camera_id)
    emitted_events: list[dict] = []
    frame_num = 0

    orig_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1920
    orig_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 1080
    scale_x = orig_width / cfg.inference_width
    scale_y = orig_height / cfg.inference_height

    with tqdm(total=total_frames, unit="frame", desc=f"{camera_id}") as pbar:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_num % cfg.frame_skip != 0:
                frame_num += 1
                pbar.update(1)
                continue

            timestamp = clip_start + timedelta(seconds=frame_num / fps)

            # Resize for inference
            small = cv2.resize(frame, (cfg.inference_width, cfg.inference_height))

            try:
                results = model.track(
                    small,
                    classes=[0],
                    persist=True,
                    tracker="bytetrack.yaml",
                    verbose=False,
                    conf=cfg.confidence_threshold,
                )
            except Exception as exc:
                log.debug("YOLO error on frame %d: %s", frame_num, exc)
                frame_num += 1
                pbar.update(1)
                continue

            if results is None or not results or results[0].boxes is None:
                frame_num += 1
                pbar.update(1)
                continue

            boxes_data = results[0].boxes
            track_ids_tensor = boxes_data.id
            if track_ids_tensor is None:
                frame_num += 1
                pbar.update(1)
                continue

            xyxy = boxes_data.xyxy.cpu().numpy()
            track_ids = track_ids_tensor.cpu().numpy().astype(int)
            confs = boxes_data.conf.cpu().numpy()

            detections = []
            for bbox, tid, conf in zip(xyxy, track_ids, confs):
                # Scale back to original resolution
                scaled_bbox = [
                    bbox[0] * scale_x,
                    bbox[1] * scale_y,
                    bbox[2] * scale_x,
                    bbox[3] * scale_y,
                ]
                from pipeline.zone_classifier import get_foot_point
                foot_x, foot_y = get_foot_point(scaled_bbox)
                zone_id = zone_classifier.classify_zone(camera_id, foot_x, foot_y)
                is_staff, staff_conf = staff_detector.is_staff(frame, scaled_bbox, int(tid))
                reid_engine.update_track_embedding(int(tid), frame, scaled_bbox, frame_num)
                staff_detector.update_zone_history(int(tid), zone_id)

                detections.append({
                    "track_id": int(tid),
                    "bbox_xyxy": scaled_bbox,
                    "confidence": float(conf),
                    "zone_id": zone_id,
                    "is_staff": is_staff,
                    "visitor_id": f"VIS_{tid:06X}",
                    "foot_y": foot_y,
                })

            result = track_manager.update(detections)

            # Handle new tracks
            from pipeline.event_emittor import generate_visitor_id
            for ts in result["new_tracks"]:
                # Attempt ReID for re-entry
                matched_vid = reid_engine.match_reentry(ts.track_id, timestamp)
                if matched_vid:
                    ts.visitor_id = matched_vid
                    evt = event_emitter.emit(
                        store_id=store_id, camera_id=camera_id,
                        visitor_id=ts.visitor_id, event_type="REENTRY",
                        timestamp=timestamp, is_staff=ts.is_staff,
                        confidence=0.75,
                    )
                    emitted_events.append(evt)
                    ts.has_entered = True
                else:
                    # Cross-camera dedup
                    active_for_reid = {
                        other_id: {
                            "camera_id": other_ts.camera_id,
                            "visitor_id": other_ts.visitor_id,
                            "embedding": reid_engine.track_embeddings.get(other_id),
                        }
                        for other_id, other_ts in track_manager.get_all_active().items()
                    }
                    cross_vid = reid_engine.match_cross_camera(ts.track_id, active_for_reid, camera_id)
                    if cross_vid:
                        ts.visitor_id = cross_vid
                    else:
                        ts.visitor_id = generate_visitor_id()

                    # Emit ENTRY for entry/billing camera or any new track on floor
                    evt = event_emitter.emit(
                        store_id=store_id, camera_id=camera_id,
                        visitor_id=ts.visitor_id, event_type="ENTRY",
                        timestamp=timestamp, is_staff=ts.is_staff,
                        confidence=float(confs[0]) if len(confs) > 0 else 0.5,
                    )
                    emitted_events.append(evt)
                    ts.has_entered = True

            # Handle lost tracks
            for ts in result["lost_tracks"]:
                if ts.current_zone:
                    evt = event_emitter.emit(
                        store_id=store_id, camera_id=camera_id,
                        visitor_id=ts.visitor_id, event_type="ZONE_EXIT",
                        timestamp=timestamp, zone_id=ts.current_zone,
                        is_staff=ts.is_staff, confidence=0.5,
                    )
                    emitted_events.append(evt)
                evt = event_emitter.emit(
                    store_id=store_id, camera_id=camera_id,
                    visitor_id=ts.visitor_id, event_type="EXIT",
                    timestamp=timestamp, is_staff=ts.is_staff, confidence=0.5,
                )
                emitted_events.append(evt)
                reid_engine.register_exit(ts.visitor_id, ts.track_id, timestamp, camera_id)
                staff_detector.reset_track(ts.track_id)
                reid_engine.clear_track(ts.track_id)

            # Zone entries
            for ts, new_zone in result["zone_entries"]:
                evt = event_emitter.emit(
                    store_id=store_id, camera_id=camera_id,
                    visitor_id=ts.visitor_id, event_type="ZONE_ENTER",
                    timestamp=timestamp, zone_id=new_zone,
                    is_staff=ts.is_staff, confidence=0.8,
                )
                emitted_events.append(evt)

            # Zone exits with dwell
            for ts, old_zone, dwell_ms in result["zone_exits"]:
                evt = event_emitter.emit(
                    store_id=store_id, camera_id=camera_id,
                    visitor_id=ts.visitor_id, event_type="ZONE_EXIT",
                    timestamp=timestamp, zone_id=old_zone, dwell_ms=dwell_ms,
                    is_staff=ts.is_staff, confidence=0.8,
                )
                emitted_events.append(evt)

            # Dwell events
            for ts, zone_id, dwell_ms in result["dwell_events"]:
                evt = event_emitter.emit(
                    store_id=store_id, camera_id=camera_id,
                    visitor_id=ts.visitor_id, event_type="ZONE_DWELL",
                    timestamp=timestamp, zone_id=zone_id, dwell_ms=dwell_ms,
                    is_staff=ts.is_staff, confidence=0.85,
                )
                emitted_events.append(evt)

            # Queue tracker update
            active_billing = track_manager.get_active_billing_track_ids(billing_zones)
            queue_result = queue_tracker.update(active_billing, timestamp)
            for tid in queue_result["newly_joined"]:
                ts_q = track_manager.get_all_active().get(tid)
                if ts_q:
                    evt = event_emitter.emit(
                        store_id=store_id, camera_id=camera_id,
                        visitor_id=ts_q.visitor_id, event_type="BILLING_QUEUE_JOIN",
                        timestamp=timestamp, zone_id=ts_q.current_zone,
                        is_staff=ts_q.is_staff, confidence=0.9,
                        queue_depth=queue_result["depth"],
                    )
                    emitted_events.append(evt)

            frame_num += 1
            pbar.update(1)

    # Emit EXIT for remaining active tracks at clip end
    for ts in track_manager.clear_all():
        evt = event_emitter.emit(
            store_id=store_id, camera_id=camera_id,
            visitor_id=ts.visitor_id, event_type="EXIT",
            timestamp=timestamp, is_staff=ts.is_staff, confidence=0.5,
        )
        emitted_events.append(evt)

    cap.release()
    log.info("[%s] Processed %d frames, emitted %d events.", camera_id, frame_num, len(emitted_events))
    return emitted_events


def main() -> None:
    args = parse_args()

    with open(args.layout, "r", encoding="utf-8") as f:
        store_layout = json.load(f)
    with open(args.mapping, "r", encoding="utf-8") as f:
        store_mapping = json.load(f)

    from pipeline.config import cfg as _cfg
    from pipeline.zone_classifier import ZoneClassifier
    from pipeline.staff_detector import StaffDetector
    from pipeline.reid import ReIDEngine
    from pipeline.queue_tracker import QueueTracker
    from pipeline.event_emittor import EventEmitter, generate_visitor_id
    from pipeline.pos_correlator import POSCorrelator
    from pipeline.tracker import TrackManager

    try:
        from ultralytics import YOLO
        model = YOLO(_cfg.yolo_model)
        log.info("Loaded YOLO model: %s", _cfg.yolo_model)
    except Exception as exc:
        log.error("Could not load YOLO model: %s", exc)
        sys.exit(1)

    store_id = args.store_id
    post_to_api = not args.no_api_post

    output_path = Path(args.output_dir) / f"{store_id}_events.jsonl"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    zone_classifier = ZoneClassifier(args.layout)
    staff_detector = StaffDetector()
    reid_engine = ReIDEngine(_cfg.reid_similarity_threshold)
    queue_tracker = QueueTracker(_cfg.queue_spike_threshold)
    event_emitter = EventEmitter(
        store_id=store_id,
        output_path=str(output_path),
        api_base_url=args.api_url,
        post_to_api=post_to_api,
        batch_size=_cfg.api_batch_size,
    )

    # Override frame_skip / confidence from args
    import dataclasses
    cfg_overrides = dataclasses.replace(
        _cfg,
        frame_skip=args.frame_skip,
        confidence_threshold=args.confidence,
    )

    clip_map = assign_clips_to_cameras(args.clips_dir, store_mapping)
    if not clip_map:
        log.error("No clips could be assigned to cameras. Exiting.")
        sys.exit(1)

    all_events: list[dict] = []

    # Use the current UTC time as clip start so events fall within the
    # dashboard / API "recent window" filters.  The store_mapping's
    # clip_start_utc is only a fallback.
    live_start_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for camera_id, clip_path in clip_map.items():
        cam_start_utc = live_start_utc
        for store in store_mapping.get("stores", []):
            for cam in store.get("cameras", []):
                if cam["camera_id"] == camera_id:
                    # Prefer live_start_utc so events are always "current"
                    cam_start_utc = live_start_utc
                    break

        import cv2
        cap = cv2.VideoCapture(clip_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 15.0
        cap.release()

        track_manager = TrackManager(
            camera_id=camera_id,
            store_id=store_id,
            fps=fps,
            dwell_threshold_seconds=cfg_overrides.dwell_threshold_seconds,
        )

        try:
            events = process_clip(
                clip_path=clip_path,
                camera_id=camera_id,
                store_id=store_id,
                clip_start_utc=cam_start_utc,
                model=model,
                zone_classifier=zone_classifier,
                staff_detector=staff_detector,
                reid_engine=reid_engine,
                queue_tracker=queue_tracker,
                track_manager=track_manager,
                event_emitter=event_emitter,
                cfg=cfg_overrides,
            )
            all_events.extend(events)
        except Exception as exc:
            log.error("Error processing clip %s: %s", clip_path, exc, exc_info=True)

    # POS correlation
    correlator = POSCorrelator(args.pos_data, store_mapping, _cfg.pos_correlation_window_minutes)
    billing_timeline = correlator.build_billing_timeline(all_events)
    converted = correlator.find_converted_sessions(billing_timeline)
    abandoned = correlator.find_abandoned_sessions(billing_timeline, converted)

    log.info("POS: %d transactions, %d converted, %d abandoned", correlator.get_transaction_count(), len(converted), len(abandoned))

    for visitor_id in abandoned:
        evt = event_emitter.emit(
            store_id=store_id,
            camera_id="PIPELINE_CORRELATOR",
            visitor_id=visitor_id,
            event_type="BILLING_QUEUE_ABANDON",
            timestamp=datetime.now(timezone.utc),
            is_staff=False,
            confidence=0.7,
        )
        all_events.append(evt)

    event_emitter.close()
    stats = event_emitter.get_stats()
    log.info("Pipeline complete. Total events emitted: %d", stats["total_emitted"])
    log.info("Events written to: %s", output_path)


if __name__ == "__main__":
    main()
