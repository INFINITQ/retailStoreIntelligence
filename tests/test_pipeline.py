# You are writing unit tests for the retail store CCTV analytics detection pipeline modules.

# FILE: tests/test_pipeline.py

# Add this block at the very top of the file:
# # PROMPT: Generate comprehensive unit tests for pipeline/zone_classifier.py,
# #          pipeline/staff_detector.py, pipeline/reid.py, pipeline/event_emitter.py,
# #          pipeline/queue_tracker.py, and pipeline/pos_correlator.py.
# #          Tests should cover happy paths, edge cases, and boundary conditions.
# # CHANGES MADE: Added cross-camera dedup test, adjusted cosine threshold test values,
# #               fixed async fixtures, added POS date parsing edge cases.

# TECH: Python 3.11, pytest==8.3.4, numpy, cv2, shapely

# IMPLEMENT THE FOLLOWING TEST FUNCTIONS:

# --- ZoneClassifier tests ---
# 1. `test_zone_classifier_loads_layout()` — loads store_layout.json from data/; asserts at
#    least one zone is loaded, no exception raised.
# 2. `test_classify_zone_billing()` — point (960, 600) on CAM_BILLING_01 should return "BILLING".
# 3. `test_classify_zone_returns_none_outside_all_polygons()` — point (0, 0) on CAM_BILLING_01
#    should return None.
# 4. `test_entry_crossing_detection_entry()` — prev_y=900, curr_y=700, threshold=820 → "ENTRY".
# 5. `test_entry_crossing_detection_exit()` — prev_y=700, curr_y=900 → "EXIT".
# 6. `test_entry_crossing_no_crossing()` — prev_y=500, curr_y=600 → None.
# 7. `test_get_foot_point()` — bbox [100,50,300,400] → (200, 400).

# --- StaffDetector tests ---
# 8. `test_staff_detector_dark_clothing()` — create a 100×50 BGR numpy array of dark pixels
#    (0,0,20 HSV region); assert is_staff returns True with confidence > 0.5.
# 9. `test_staff_detector_bright_clothing_not_staff()` — bright coloured pixels → is_staff=False.
# 10. `test_zone_ubiquity_threshold()` — update 5 different zones for track_id 1;
#     assert classify_by_zone_ubiquity(1, threshold=5) == True.
# 11. `test_empty_crop_returns_false()` — bbox [50,50,50,50] (zero area) → (False, 0.0).

# --- ReIDEngine tests ---
# 12. `test_reid_cosine_identical_embeddings()` — cosine_similarity(v, v) == 1.0.
# 13. `test_reid_cosine_orthogonal_embeddings()` — cos_sim([1,0,0],[0,1,0]) ≈ 0.0.
# 14. `test_register_and_match_reentry()` — register exit for visitor_id "VIS_AA",
#     create near-identical embedding for new track, assert match_reentry returns "VIS_AA".
# 15. `test_no_match_below_threshold()` — similar but orthogonal embeddings → returns None.
# 16. `test_extract_embedding_tiny_bbox_returns_none()` — 10×10 crop → returns None.

# --- EventEmitter tests ---
# 17. `test_emit_writes_to_jsonl(tmp_path)` — emit one ENTRY event; read JSONL file;
#     assert event_id, event_type, timestamp fields present.
# 18. `test_emit_increments_session_seq()` — emit 3 events for same visitor_id;
#     assert session_seq values are 1, 2, 3.
# 19. `test_event_confidence_clamping()` — confidence=1.5 should be clamped to 1.0.
# 20. `test_event_invalid_event_type_raises()` — event_type="INVALID" → ValidationError.

# --- QueueTracker tests ---
# 21. `test_queue_depth_updates_correctly()` — update with {1,2,3} track_ids → depth=3.
# 22. `test_spike_detected_at_threshold()` — update with set of 5 track_ids (threshold=5);
#     assert result["spike_started"] == True.
# 23. `test_newly_joined_set()` — first update with {1}; second with {1,2}; newly_joined={2}.
# 24. `test_rolling_average()` — call update 5 times with varying depths; assert get_rolling_avg() != 0.

# --- POSCorrelator tests ---
# 25. `test_parse_pos_timestamp_ist_to_utc()` — "10-04-2026" + "14:00:00" → UTC = "08:30:00".
# 26. `test_find_converted_sessions_within_window()` — create a billing interval at T,
#     a transaction at T+3min; assert visitor_id in converted set.
# 27. `test_find_converted_sessions_outside_window()` — billing interval at T,
#     transaction at T+10min → not converted.

# IMPORTS NEEDED: pytest, numpy as np, cv2, datetime (datetime, timezone), uuid,
# shapely.geometry, pathlib,
# pipeline.zone_classifier (ZoneClassifier, get_foot_point),
# pipeline.staff_detector (StaffDetector), pipeline.reid (ReIDEngine),
# pipeline.event_emitter (EventEmitter), pipeline.queue_tracker (QueueTracker),
# pipeline.pos_correlator (POSCorrelator, parse_pos_timestamp)
