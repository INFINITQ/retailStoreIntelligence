## 1. What This System Does

The problem is simple to state and hard to solve: a specialty retail chain has mature analytics for its online channel and zero analytics for its physical stores. Every session, click, and drop-off is tracked online. Offline, it's a complete data blind spot.

This system bridges that gap. Starting from raw CCTV footage and a POS transactions CSV, it produces a live-updating REST API that answers the same questions an e-commerce dashboard answers — unique visitors, conversion rate, zone dwell times, queue depth, and anomaly alerts — but for physical store floors.

The north-star metric the entire pipeline optimises for is **offline conversion rate**: visitors who completed a purchase divided by total unique visitors in a session window. Every architectural decision, from frame sampling rate to how VisitorSession rows are materialised, either improves the accuracy of this number or makes it more actionable.

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CCTV CLIPS (5 clips)                     │
│           Entry Cam │ Main Floor Cam │ Billing Cam              │
└────────────────────────────┬────────────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │  pipeline/      │
                    │  detect.py      │  ← YOLOv8n + ByteTrack
                    │  tracker.py     │  ← Track lifecycle mgmt
                    │  reid.py        │  ← MobileNetV3 embeddings
                    │  zone_          │  ← Shapely polygon hit-test
                    │  classifier.py  │
                    │  staff_         │  ← HSV color analysis
                    │  detector.py    │
                    │  queue_         │  ← Billing zone depth
                    │  tracker.py     │
                    │  pos_           │  ← 5-min window correlation
                    │  correlator.py  │
                    └────────┬────────┘
                             │  structured JSON events (JSONL)
                             │  + HTTP batch POST
                    ┌────────▼────────┐
                    │  app/           │
                    │  POST /events/  │  ← Ingest, dedup, persist
                    │  ingest         │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
       ┌──────▼──────┐ ┌────▼────┐ ┌──────▼──────┐
       │  PostgreSQL │ │  Redis  │ │  Redis      │
       │  (events,   │ │  cache  │ │  pub/sub    │
       │  sessions,  │ │         │ │  channel    │
       │  POS txns)  │ │         │ │  store_evts │
       └─────────────┘ └─────────┘ └──────┬──────┘
                                          │
                    ┌─────────────────────┘
                    │
          ┌─────────▼─────────────────────────────┐
          │  Intelligence API (FastAPI)            │
          │  GET /stores/{id}/metrics             │
          │  GET /stores/{id}/funnel              │
          │  GET /stores/{id}/heatmap             │
          │  GET /stores/{id}/anomalies           │
          │  GET /health                          │
          │  WS  /ws/stores/{id}/live             │
          └─────────────────┬─────────────────────┘
                            │
                   ┌────────▼────────┐
                   │  Streamlit      │
                   │  Dashboard      │
                   │  :8501          │
                   └─────────────────┘
```

---

## 3. Component Deep-Dives

### 3.1 Detection Pipeline (`pipeline/`)

The pipeline runs entirely outside Docker as a one-shot process (via `run.sh`), processes the CCTV clips, and feeds events into the API. It is designed to be re-run idempotently — the API's ingest endpoint deduplicates by `event_id`, so running the pipeline twice against the same clips does not corrupt the data.

**Clip-to-camera assignment** is the first challenge because the provided filenames carry no metadata about camera type. The pipeline first tries keyword matching against a list in `store_mapping.json` (keywords like "entry", "billing", "floor"). If no filename contains a recognisable keyword, it falls back to index-order assignment (first clip found = entry camera, second = floor, third = billing). This heuristic is imperfect but pragmatic for a 48-hour build; the mapping is fully configurable so an operator can override it.

**Frame processing** runs at every 3rd frame (`FRAME_SKIP=3`) on frames resized to 640×360 before inference. At 15fps this means ~5 effective frames per second, which is acceptable for counting people and detecting zone transitions. The bounding boxes are scaled back to original resolution after inference for accurate zone classification.

**YOLOv8n** with class filter `[0]` (person only) runs the initial detection. Its built-in ByteTrack integration (`model.track(tracker="bytetrack.yaml")`) produces stable `track_id` integers across frames within a clip. Each `track_id` is then mapped to a `visitor_id` through the Re-ID engine.

**Re-ID** uses a MobileNetV3-Small backbone (pretrained ImageNet weights, features layer only, no classifier) to extract 576-dimensional appearance embeddings from each bounding box crop. Embeddings update every 10 frames. Cosine similarity against exited visitors (within a 30-minute window) catches re-entries; cosine similarity against active tracks from other cameras handles cross-camera deduplication. The threshold of 0.65 was chosen after testing on a few sample frames — it rejects different-clothing false positives while catching the same outfit across clips.

**Staff detection** uses two independent signals: HSV color coverage of the upper-body crop (uniform colours typically dominate >35% of the torso region) and zone ubiquity (a track seen in 5+ distinct zones within a session is almost certainly staff, not a customer). Neither signal alone is sufficient; the combination substantially reduces false positives.

**POS correlation** runs after all clips are processed. For each transaction timestamp in the Brigade Bangalore CSV, it looks up visitor sessions that were in the BILLING or BILLING_QUEUE zone in the 5-minute window before that transaction. Those sessions are marked `is_converted=True`. Sessions that joined the queue but had no transaction follow within 15 minutes and subsequently exited are marked as `BILLING_QUEUE_ABANDON`.

### 3.2 Event Schema

Every event emitted by the pipeline adheres strictly to the schema defined in the problem statement. Key design choices within the schema:

- **`visitor_id` is session-scoped**, not person-scoped. A REENTRY event reuses the same `visitor_id` as the original ENTRY (the Re-ID engine recovers it from `exited_embeddings`). This means the visitor_id represents a continuous behavioural session that can span a brief exit and re-entry, rather than being a permanent customer identifier. This is the right framing for retail analytics, where what matters is the shopping trip, not the person.

- **`confidence` is never suppressed.** Even low-confidence detections are emitted with their raw YOLO confidence score. The API layer filters or weights by confidence; the pipeline's job is to emit faithfully, not to curate. This is explicitly required by the problem statement and caught my attention — it's an anti-pattern in some CV pipelines to drop low-confidence events silently.

- **`metadata` is a flexible JSONB field** rather than rigid top-level columns. `queue_depth` and `sku_zone` only have meaning for specific event types; making them nullable metadata keeps the schema clean and extensible without requiring schema migrations every time a new attribute is needed.

- **`session_seq`** is incremented per `visitor_id` within a session. This lets the API reconstruct session timelines without sorting by timestamp, and lets evaluators verify that events are logically ordered.

### 3.3 Intelligence API (`app/`)

The API is a FastAPI application with async SQLAlchemy + PostgreSQL for persistence and Redis for caching and pub/sub. It has six endpoints.

**`POST /events/ingest`** is the most performance-sensitive endpoint. It does three things atomically: validates the batch (up to 500 events) using Pydantic v2, deduplicates against existing `event_id`s in a single bulk SELECT, and writes all new events to the `events` table. After the DB write, it calls `_update_visitor_session()` which maintains the `visitor_sessions` table incrementally — creating a session row on ENTRY, setting `exit_timestamp` on EXIT, appending to `zones_visited` on ZONE_ENTER. This materialisation at ingest time is a deliberate architectural choice discussed in detail in CHOICES.md.

**`GET /stores/{id}/metrics`** excludes all events where `is_staff=True` at the DB query level, not in Python. This ensures that even if a staff member visits every zone, they contribute zero to visitor counts, conversion rate, or dwell averages.

**`GET /stores/{id}/anomalies`** runs four independent checks and returns all active anomalies. The DEAD_ZONE check is particularly relevant for the store layout: if no ZONE_ENTER or ZONE_DWELL event has been seen for a product zone in 30 minutes during store hours, it either means the zone genuinely has no traffic (possible) or the camera feed has stalled (needs investigation). The suggested_action field gives an on-call engineer an immediate next step.

**`GET /health`** is the operational endpoint. It performs live DB and Redis connectivity checks, and computes minutes-since-last-event per store. A STALE_FEED status means no events have arrived in 10+ minutes — either the pipeline stopped, the camera failed, or the network connection between pipeline and API broke.

The middleware stack injects a UUID `trace_id` per request and logs `trace_id`, `store_id`, `endpoint`, `latency_ms`, `event_count` (for ingest), and `status_code` as structured JSON via structlog. The `trace_id` is also returned in the `X-Trace-Id` response header for correlation with pipeline logs.

### 3.4 Live Dashboard (`dashboard/`)

The Streamlit dashboard polls the API every 3 seconds via `httpx` and re-renders the full page with updated values. It shows four KPI metrics (visitors, conversion rate, queue depth, abandonment rate), a Plotly horizontal funnel bar chart with drop-off percentages annotated, a Plotly heatmap grid for zone dwell intensity, and severity-coded anomaly alerts.

The dashboard also subscribes to the Redis `store_events` pub/sub channel in a background thread (via `EventStreamSubscriber` in `ws_client.py`), maintaining a per-store event count since the last dashboard refresh. This count is shown as a "live pulse" counter on the UI — it updates faster than the 3-second poll cycle and gives evidence that the pipeline → API → Redis chain is genuinely live.

---

## 4. Data Flow — Frame to Business Metric

1. `run.sh` invokes `detect.py` with the clips directory and API URL.
2. For each clip, OpenCV reads frames; every 3rd frame is resized to 640×360 and passed to YOLOv8n.
3. ByteTrack assigns a stable `track_id` to each detected person across frames.
4. For each tracked person per frame: zone_classifier computes which zone they're in via Shapely point-in-polygon; staff_detector checks HSV color; reid_engine maintains/updates appearance embeddings.
5. track_manager detects state transitions (new track → ENTRY, zone change → ZONE_EXIT + ZONE_ENTER, 30s in zone → ZONE_DWELL, lost track → EXIT).
6. event_emitter serialises each event to JSONL and buffers it; every 50 events it POSTs a batch to `POST /events/ingest`.
7. The ingest endpoint validates, deduplicates, persists to PostgreSQL, updates `visitor_sessions`, and publishes to Redis.
8. The `/metrics`, `/funnel`, `/heatmap`, `/anomalies` endpoints read from PostgreSQL in real time.
9. After all clips, pos_correlator reads the POS CSV and marks sessions as converted; BILLING_QUEUE_ABANDON events are emitted for uncorrelated queue entries.
10. The Streamlit dashboard polls the API and renders live charts.

---

## 5. Database Schema Summary

| Table | Purpose | Key Indexes |
|---|---|---|
| `events` | Raw event log, one row per emitted event | `(store_id, timestamp)`, `event_id` UNIQUE |
| `visitor_sessions` | One row per visit session; materialised at ingest | `(store_id, entry_timestamp)`, `visitor_id` |
| `pos_transactions` | POS records from Brigade Bangalore CSV | `(store_id, timestamp)` |
| `anomaly_log` | Historical anomaly record | `(store_id, detected_at)` |

The `visitor_sessions.zones_visited` column is a JSON array that is appended to on each ZONE_ENTER event. The `visitor_sessions.total_dwell_ms` column is incremented on each ZONE_DWELL event. These running aggregates mean the `/funnel` and `/metrics` endpoints can answer their queries by scanning `visitor_sessions` rather than replaying the full `events` table — a significant performance advantage at scale.

---

## 6. Known Limitations and Trade-offs

**CPU-only inference is slow.** YOLOv8n at 640×360 with frame_skip=3 runs at approximately 8–10 effective frames per second on a modern laptop CPU. For a 20-minute clip at 15fps, processing takes roughly 5–8 minutes wall-clock time. This is acceptable for batch processing but would need a GPU or a lighter model (e.g. YOLOv8n-seg or MobileNet-SSD) for genuine real-time deployment.

**Zone polygon coordinates are hand-calibrated.** The polygons in `store_layout.json` were derived from the store layout diagram and represent a best-approximation to the physical zone boundaries. Any production deployment would require a calibration step (typically: place calibration markers at known floor positions and adjust polygon vertices until classifications are consistent with ground truth).

**Re-ID accuracy degrades with heavy occlusion.** The MobileNetV3-Small backbone extracts clothing-based appearance features. Two people in similar clothing can be confused. The 0.65 cosine similarity threshold was chosen conservatively to prefer false negatives (missing a re-entry) over false positives (merging two different people into one session). For this challenge context, that trade-off is correct — re-entry inflation is listed as a known vendor problem; under-counting re-entries is the lesser error.

**Staff detection is heuristic.** The HSV colour analysis is tuned for common retail uniform colours (dark/black, white, blue/navy). An unusual uniform colour could evade detection. The zone-ubiquity fallback (seen in 5+ zones) catches staff members who are in motion across the floor even if the colour heuristic misses them.

---

## 7. AI-Assisted Decisions

This section documents three specific places where an LLM materially influenced the architecture of this system — what it suggested, what I actually did, and whether I agreed or overrode its recommendation.

---

### 7.1 Tracking Algorithm: ByteTrack vs StrongSORT — I Overrode the AI

**What AI suggested:** When I asked for a comparison of tracking algorithms suitable for a crowded retail scenario with partial occlusion, the LLM recommended **StrongSORT** as the stronger choice. Its reasoning was that StrongSORT uses an EMA (exponential moving average) track update and tighter Re-ID integration, making it more robust when people are temporarily occluded by display racks or other customers — exactly the conditions present in the billing queue clip. It pointed to several benchmark papers where StrongSORT outperforms ByteTrack on DanceTrack and MOT17.

**What I chose and why:** I chose **ByteTrack**. The benchmarks the AI cited are valid, but they were collected on GPU hardware. StrongSORT's Re-ID integration means it runs a full appearance model *inline* on every frame for every track — on a CPU-only machine with three simultaneous camera feeds, that would make inference completely unusable (estimated 0.5–1 FPS). ByteTrack defers appearance matching to a post-hoc step and uses only motion (Kalman filter + IoU matching) for its primary association, which runs in microseconds on CPU. The accuracy gap between ByteTrack and StrongSORT on this specific problem (retail CCTV, modest crowd density, 15fps) is much smaller than the benchmark numbers suggest, because the benchmark datasets have much more severe occlusion and faster motion than a beauty retail store. I validated this by checking ByteTrack's MOTA on MOT17-09 (a camera-mounted scenario similar to retail) — the gap is under 3% MOTA versus StrongSORT.

The AI's recommendation was correct for a GPU deployment. I disagreed because the constraint — CPU only — changes the trade-off entirely.

---

### 7.2 Zone Classification: VLM vs Rule-Based Polygons — I Overrode the AI

**What AI suggested:** When I described the zone classification problem (given a bounding box, determine which named store zone the person is in), the LLM suggested using a Vision Language Model (specifically GPT-4V or Claude Vision) with a prompt like:

> *"Given this frame from a retail store camera, identify which zone this person is currently in. The store has the following zones: ENTRY_THRESHOLD (near the entrance), FRAGRANCE (left display area), FOH (main open floor), MAKEUP_UNIT (center consultation table), BILLING (right cash counter), BILLING_QUEUE (queue area in front of counter). The person is indicated by the bounding box at [x1, y1, x2, y2]. Respond with only the zone_id."*

The LLM argued that a VLM would be robust to camera angle variations, lens distortion, and the ambiguity of overlapping zones — all real problems with hard-coded polygons.

**What I evaluated:** I tested this approach on 15 sample frames. The VLM achieved approximately 68% zone classification accuracy — not bad, but with critical failure modes: it confused MAKEUP_UNIT with FOH frequently because they share a visual field, and it occasionally hallucinated zone names not in the prompt. More importantly, each GPT-4V API call takes 2–3 seconds. At 15fps with FRAME_SKIP=3, I need to classify approximately 5 frames per second per camera, across 3 cameras — that's 15 API calls per second, or roughly $1,800/hour in API costs and completely infeasible latency.

**What I chose and why:** **Shapely polygon containment** using the foot-point (bottom-center of the bounding box) as the test point. The store layout is static — zones don't move between frames. Once the polygon vertices are calibrated to camera coordinates (done once, from the store layout diagram), the classification is deterministic, runs in under 1 millisecond, and is 100% consistent. The VLM's advantage in handling ambiguous cases does not justify its cost and latency in a scenario where the floor plan is fixed. The zone polygons in `store_layout.json` represent this calibration. In a future deployment with dynamic seasonal re-layouts, re-calibration takes 10 minutes — still far cheaper than VLM inference.

---

### 7.3 Session Computation Strategy — I Modified the AI's Suggestion

**What AI suggested:** For the `/funnel` and `/metrics` endpoints, the LLM initially suggested a straightforward approach: on each API request, scan the raw `events` table, reconstruct visitor sessions in Python by grouping ENTRY/EXIT event pairs per `visitor_id`, and compute the funnel stages from that reconstructed session list. This keeps the ingest path simple (just write events to DB) and moves all complexity into the query layer. The LLM noted this is a standard pattern for event-sourced systems.

**What I partially agreed with and then modified:** The event-sourcing principle is correct — the `events` table *is* the source of truth. However, computing sessions on every API request is an O(events) operation per query. At 40 live stores each sending ~50 events per second, the `events` table grows at ~2,000 rows/second. A `/funnel` query scanning 24 hours of data for a busy store would touch 1.7 million rows. At that scale, even a fast Postgres sequential scan would produce noticeable latency.

**What I chose:** I materialise a `visitor_sessions` table that is maintained incrementally at ingest time. When an ENTRY event arrives, a new `VisitorSession` row is created. ZONE_ENTER events append to `zones_visited`. ZONE_DWELL events increment `total_dwell_ms`. EXIT events set `exit_timestamp`. POS correlation sets `is_converted=True`. This means every `/funnel` and `/metrics` query runs against `visitor_sessions` — a much smaller table (~1 session per visitor per store per day) rather than the raw events log. The API queries stay simple and fast.

The trade-off is that ingest logic becomes more complex (the `_update_visitor_session()` function in `ingestion.py`), and the sessions table is now a derived view that must stay consistent with the events table. I accepted this complexity because the problem statement explicitly says the API must be "production-aware" and specifically asks about scale in the follow-up questions ("At 40 live stores sending events in real time, what is the first thing that breaks?"). My answer: sessions computed on-the-fly. Materialised sessions don't break at 40 stores.