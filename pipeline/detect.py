# You are building the main detection orchestration script for a retail store CCTV analytics pipeline.

# FILE: pipeline/detect.py
# PURPOSE: Entry-point script. Loads CCTV video clips, runs YOLOv8n person detection with
# ByteTrack, coordinates all sub-modules (zone classifier, staff detector, Re-ID, queue tracker,
# track manager, event emitter), and produces a complete structured event stream per clip.
# Also runs POS correlation and emits BILLING_QUEUE_ABANDON events after all clips are processed.

# TECH: Python 3.11, ultralytics==8.3.50, OpenCV (cv2), numpy==1.26.4, argparse, pathlib, tqdm

# KEY DESIGN DECISIONS:
# - CPU-only: process every Nth frame (frame_skip, default 3) to maintain reasonable speed.
# - Resize frames to 640×360 before YOLO inference; scale bounding boxes back to original.
# - Use YOLO's built-in ByteTrack via model.track(tracker="bytetrack.yaml").
# - Camera type assignment: match clip filenames against keyword lists in store_mapping.json.
#   If no keyword match, assign clips in index order (0=entry, 1=floor, 2=billing).
# - If fewer clips than cameras: skip missing cameras; log a warning.
# - Clip start time: read from store_mapping.json camera config (clip_start_utc).
#   Frame timestamp = clip_start_utc + timedelta(seconds=(frame_num * frame_skip / fps)).

# IMPLEMENT THE FOLLOWING:

# 1. `parse_args() -> argparse.Namespace:`
#    Arguments: --clips-dir (str, required), --output-dir (str, default="data/events"),
#    --api-url (str, default="http://localhost:8000"),
#    --store-id (str, default="STORE_BLR_002"),
#    --layout (str, default="data/store_layout.json"),
#    --mapping (str, default="data/store_mapping.json"),
#    --pos-data (str, default="data/pos_transactions.csv"),
#    --no-api-post (store_true flag to disable API posting),
#    --frame-skip (int, default=3),
#    --confidence (float, default=0.35)

# 2. `assign_clips_to_cameras(clips_dir: str, store_mapping: dict) -> dict[str, str]:`
#    - Glob for *.mp4, *.avi, *.mov files in clips_dir.
#    - For each camera in the store_mapping, try to match a clip by checking if any
#      clip_filename_keyword appears in the clip filename (case-insensitive).
#    - If no keyword match, fall back to clip_index ordering.
#    - Returns dict: {camera_id: clip_path}. Logs assignments.

# 3. `process_clip(clip_path: str, camera_id: str, store_id: str, clip_start_utc: str,
#                   model, zone_classifier, staff_detector, reid_engine, queue_tracker,
#                   track_manager, event_emitter, cfg) -> list[dict]:`
#    - Opens clip with cv2.VideoCapture. Verify it opened; raise RuntimeError if not.
#    - fps = cap.get(cv2.CAP_PROP_FPS). total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)).
#    - Parse clip_start_utc with datetime.fromisoformat().replace(tzinfo=timezone.utc).
#    - billing_zones = zone_classifier.get_billing_zones(camera_id).
#    - Loop with tqdm progress bar (unit="frame"):
#      a. Read frame; break on failure.
#      b. Skip if frame_num % cfg.frame_skip != 0. Increment frame_num; continue.
#      c. Calculate timestamp = clip_start_utc + timedelta(seconds=frame_num * cfg.frame_skip / fps).
#      d. Resize frame: small = cv2.resize(frame, (cfg.inference_width, cfg.inference_height)).
#      e. Run: results = model.track(small, classes=[0], persist=True,
#                                    tracker="bytetrack.yaml", verbose=False,
#                                    conf=cfg.confidence_threshold)
#      f. If results is None or results[0].boxes is None: increment frame_num; continue.
#      g. Parse results: extract boxes.xyxy.cpu().numpy(), boxes.id (track_ids, may be None),
#         boxes.conf.cpu().numpy(). If track_ids is None, skip frame.
#      h. Scale boxes from inference resolution back to original (multiply x by W/640, y by H/360).
#      i. For each detection (bbox, track_id, conf):
#         - foot_x, foot_y = get_foot_point(bbox)
#         - zone_id = zone_classifier.classify_zone(camera_id, foot_x, foot_y)
#         - is_staff, staff_conf = staff_detector.is_staff(frame, bbox, track_id)
#         - reid_engine.update_track_embedding(track_id, frame, bbox, frame_num)
#         - staff_detector.update_zone_history(track_id, zone_id)
#         - Build detection dict for track_manager.
#      j. result = track_manager.update(detections)
#      k. Handle new_tracks: for each, attempt ReID match_reentry or match_cross_camera.
#         - If reentry matched: emit REENTRY event (visitor_id = matched_id).
#         - Elif cross-camera matched: use matched visitor_id, emit no ENTRY for this camera.
#         - Else: generate new visitor_id via generate_visitor_id(); emit ENTRY event if
#           check_entry_crossing returns "ENTRY" for entry cameras, or emit ENTRY for any
#           new track on non-entry cameras (they entered via another zone).
#      l. Handle lost_tracks: emit ZONE_EXIT (if in a zone), then EXIT. Call
#         reid_engine.register_exit(). Call staff_detector.reset_track(). Call
#         reid_engine.clear_track(). Call track_manager.remove_track().
#      m. Handle zone_entries: emit ZONE_ENTER.
#      n. Handle zone_exits: emit ZONE_EXIT (with dwell_ms computed from zone duration).
#      o. Handle dwell_events: emit ZONE_DWELL.
#      p. Update queue_tracker: active_billing = track_manager.get_active_billing_track_ids(billing_zones).
#         queue_result = queue_tracker.update(active_billing, timestamp).
#         For each track_id in queue_result["newly_joined"]: emit BILLING_QUEUE_JOIN with
#         queue_depth = queue_result["depth"].
#      q. For entry/exit cameras: check entry crossing using zone_classifier.check_entry_crossing().
#         Compare with track's previous foot_y (store it in TrackState). Emit ENTRY or EXIT
#         accordingly. Update track.has_entered.
#    - After loop: call track_manager.clear_all() and emit EXIT for remaining active tracks.
#    - cap.release(). Return list of all emitted events.

# 4. `main() -> None:`
#    - Parse args. Load store_layout.json and store_mapping.json (json.load).
#    - Import cfg from pipeline.config.
#    - Initialise all modules:
#      zone_classifier = ZoneClassifier(args.layout)
#      staff_detector = StaffDetector()
#      reid_engine = ReIDEngine(cfg.reid_similarity_threshold)
#      queue_tracker = QueueTracker(cfg.queue_spike_threshold)
#      event_emitter = EventEmitter(store_id, output_path, api_url, post_to_api, batch_size)
#    - Assign clips: clip_map = assign_clips_to_cameras(args.clips_dir, store_mapping).
#    - For each camera_id, clip_path in clip_map.items():
#      - Create a fresh TrackManager(camera_id=camera_id, ...) per clip.
#      - Call process_clip(...).
#    - After all clips: load all emitted events from JSONL, run POS correlation.
#      correlator = POSCorrelator(args.pos_data, store_mapping)
#      billing_timeline = correlator.build_billing_timeline(all_events)
#      converted = correlator.find_converted_sessions(billing_timeline)
#      abandoned = correlator.find_abandoned_sessions(billing_timeline, converted)
#      For each abandoned visitor_id: emit BILLING_QUEUE_ABANDON event.
#    - event_emitter.close(). Print summary stats.

# IMPORTS NEEDED:
#   argparse, json, pathlib (Path), glob, datetime (datetime, timedelta, timezone),
#   cv2, numpy as np, tqdm (tqdm), ultralytics (YOLO),
#   pipeline.config (cfg), pipeline.zone_classifier (ZoneClassifier, get_foot_point),
#   pipeline.staff_detector (StaffDetector), pipeline.reid (ReIDEngine),
#   pipeline.queue_tracker (QueueTracker), pipeline.event_emitter (EventEmitter, generate_visitor_id),
#   pipeline.pos_correlator (POSCorrelator), pipeline.tracker (TrackManager)

# if __name__ == "__main__": guard required.

# IMPORTANT: All print/log statements should go to stdout with timestamps.
# Handle empty clips (0 detections) gracefully — do not crash; emit nothing.
# Handle missing clips gracefully — log warning, skip camera.
