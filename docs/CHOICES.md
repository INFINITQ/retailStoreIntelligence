Below are my choices, which tell what I choices I made and why:

# Tech Stack — Decisions, Alternatives, and Reasoning

| Layer | Chosen | Alternatives Considered | Decision Rationale |
|---------|---------|-------------------------|-------------------|
| Person Detection | **YOLOv8m (Ultralytics)** | YOLOv9, RT-DETR, MediaPipe | YOLOv8m provides the best accuracy/speed tradeoff at 1080p/15fps. The Ultralytics library offers easy access to COCO-pretrained weights, and the **m** variant handles partial occlusions better than **n** without requiring significant GPU resources. |
| Multi-Object Tracking | **ByteTrack** | DeepSORT, StrongSORT, OC-SORT | ByteTrack performs exceptionally well in crowded and occluded scenes, which closely matches the retail billing queue use case. It avoids the overhead of appearance models while maintaining lower latency. |
| Cross-Camera Re-ID | **OSNet-x0.75 (torchreid)** | Color Histogram Matching, FairMOT, Raw Bounding Box Trajectory | Since faces are blurred, face-based Re-ID is not viable. OSNet-x0.75 generates lightweight body/clothing embeddings, enabling reliable duplicate detection and re-entry tracking through cosine similarity matching. |
| Staff Classification | **HSV Color Clustering + Zone Pattern Analysis** | VLM (GPT-4V), Supervised Image Classifier | Beauty retail staff typically wear consistent uniform colors. HSV thresholding on upper-body crops provides a fast, explainable, and low-cost solution compared to per-frame VLM inference. |
| API Framework | **FastAPI + Pydantic v2** | Flask, Django REST Framework | FastAPI is asynchronous by design, automatically generates OpenAPI documentation, and aligns with the challenge requirements. Pydantic v2 delivers significantly faster validation than v1. |
| Primary Database | **PostgreSQL 16** | SQLite, ClickHouse | Supports concurrent writes from multiple camera feeds, efficient time-range analytics, JSONB metadata storage, and production-grade reliability. |
| Caching & Pub/Sub | **Redis 7** | Memcached, RabbitMQ | Redis provides low-latency caching with TTL support and built-in Pub/Sub capabilities for real-time dashboard updates. Memcached lacks Pub/Sub, while RabbitMQ would introduce unnecessary complexity. |
| Structured Logging | **structlog** | Python logging, loguru | Produces structured JSON logs containing fields such as `trace_id`, `store_id`, and `latency_ms`, matching system observability requirements. |
| Dashboard | **Streamlit + WebSocket Client** | React + Recharts, Grafana | Enables rapid development of a real-time dashboard entirely in Python. Streamlit's live-update capabilities eliminate the need for a separate frontend build pipeline. |
| Testing | **pytest + httpx + pytest-asyncio + pytest-cov** | unittest | Industry-standard testing stack with strong support for asynchronous endpoint testing and coverage reporting. |
| Database Migrations | **Alembic** | Manual SQL Scripts, Tortoise ORM | Production-ready schema migration management that integrates naturally with SQLAlchemy and PostgreSQL. |
| Containerization | **Docker Compose (4 Services)** | Kubernetes, Bare Docker Run | Meets challenge requirements while keeping deployment simple. Services include: `api`, `postgres`, `redis`, and `dashboard`. |


store-intelligence/
│
├── pipeline/                          ← Everything that touches video
│   ├── detect.py                      # Orchestrator: loads clips, runs YOLOv8 inference frame-by-frame, feeds ByteTrack, calls all sub-modules, writes events to JSONL
│   ├── tracker.py                     # Wraps ByteTrack; manages per-camera track lifecycle; assigns stable track_id per camera
│   ├── reid.py                        # OSNet-x0.75 embedding extractor; cosine similarity matching across cameras and after EXIT gaps for re-entry detection
│   ├── zone_classifier.py             # Loads store_layout.json; maps bounding-box centroid/feet-point to zone polygon using shapely; returns zone_id
│   ├── staff_detector.py              # HSV color analysis on upper-body crop; flags known uniform colors; also uses zone frequency heuristic (staff appear in all zones uniformly)
│   ├── event_emitter.py               # Builds and validates event dicts against Pydantic schema; handles ENTRY/EXIT/ZONE_ENTER/ZONE_EXIT/ZONE_DWELL/BILLING_QUEUE_JOIN/BILLING_QUEUE_ABANDON/REENTRY event types; writes to output JSONL and optionally POSTs to API
│   ├── pos_correlator.py              # Reads pos_transactions.csv; for each transaction timestamp, looks up visitors in billing zone in the preceding 5-minute window; marks them as converted; feeds BILLING_QUEUE_ABANDON logic
│   ├── queue_tracker.py               # Counts bounding boxes simultaneously in billing zone per frame; emits queue_depth to metadata; detects queue spike events
│   ├── config.py                      # Pipeline config: clip paths, camera-to-store mapping, confidence thresholds, Re-ID similarity threshold, zone polygon source
│   └── run.sh                         # Single bash script: runs detect.py over all 5 clips → produces events.jsonl → optionally replays into API via POST /events/ingest
│
├── app/                               ← FastAPI service
│   ├── main.py                        # FastAPI app factory; registers routers; adds middleware (trace_id injection, structured logging, error handler); mounts WebSocket endpoint for dashboard
│   ├── config.py                      # Pydantic-settings: DATABASE_URL, REDIS_URL, env vars; single source of truth
│   ├── database.py                    # Async SQLAlchemy engine + session factory; dependency injection helper get_db()
│   │
│   ├── models/
│   │   ├── db_models.py               # SQLAlchemy ORM tables: Event, VisitorSession, POSTransaction, StoreConfig, AnomalyLog
│   │   └── schemas.py                 # Pydantic v2 models: EventIn, EventOut, MetricsResponse, FunnelResponse, HeatmapResponse, AnomalyResponse, HealthResponse
│   │
│   ├── routers/
│   │   ├── events.py                  # POST /events/ingest — validates batch, deduplicates by event_id, writes to DB, publishes to Redis channel; returns partial-success response
│   │   ├── stores.py                  # GET /stores/{id}/metrics, /funnel, /heatmap, /anomalies — delegates to service layer
│   │   └── health.py                  # GET /health — checks DB connectivity, Redis ping, last event timestamp per store, emits STALE_FEED if >10min lag
│   │
│   ├── services/
│   │   ├── ingestion.py               # Core ingest logic: idempotency check, schema validation, session stitching (links events to VisitorSession), POS correlation write-back
│   │   ├── metrics.py                 # Computes unique visitors (deduped by visitor_id), conversion_rate, avg_dwell_per_zone, queue_depth, abandonment_rate — excludes is_staff=true events
│   │   ├── funnel.py                  # Session-level funnel: Entry → Zone Visit → Billing Queue → Purchase; drop-off % per stage; re-entry deduplication (one visitor_id = one funnel unit)
│   │   ├── heatmap.py                 # Zone visit frequency + avg dwell aggregated by zone; normalises to 0–100; sets data_confidence=false if <20 sessions in window
│   │   └── anomalies.py              # Detects: BILLING_QUEUE_SPIKE (queue_depth > threshold), CONVERSION_DROP (today vs 7-day avg), DEAD_ZONE (no zone visits in 30 min); returns severity + suggested_action
│   │
│   └── middleware/
│       └── logging.py                 # Injects trace_id (UUID) per request; logs trace_id, store_id, endpoint, latency_ms, event_count, status_code via structlog
│
├── dashboard/
│   ├── app.py                         # Streamlit app: subscribes to Redis pub/sub; shows live visitor count, queue depth, conversion rate, zone heatmap — updates every 2 seconds
│   └── ws_client.py                   # WebSocket helper that connects to /ws/stores/{id}/live and feeds Streamlit session state
│
├── tests/
│   ├── conftest.py                    # pytest fixtures: test DB (SQLite in-memory for speed), test client (httpx AsyncClient), sample event factory, sample POS data loader
│   ├── test_pipeline.py               # Unit tests for zone_classifier, staff_detector, reid cosine logic, event schema validation; includes AI PROMPT block header at top
│   ├── test_ingestion.py              # Tests: happy path ingest, idempotency (same payload twice = same DB state), partial success on malformed batch, batch size limit (500)
│   ├── test_metrics.py                # Tests: correct unique visitor count, conversion rate math, staff exclusion, zero-purchase store returns 0.0 not null
│   ├── test_funnel.py                 # Tests: re-entry does not inflate funnel count, session dedup, multi-camera visitor counted once, all stages present
│   ├── test_anomalies.py              # Tests: queue spike triggers CRITICAL, conversion drop triggers WARN, dead zone triggers INFO, severity thresholds
│   └── test_edge_cases.py             # Tests: empty store period (no events), all-staff clip (zero customer metrics), zero purchases, STALE_FEED health warning
│
├── data/
│   ├── store_layout.json              # Zone polygon definitions per camera per store; derived from layout image — zones: ENTRY_EXIT, FRAGRANCE, FOH, MAKEUP_UNIT, BILLING, plus brand strip sub-zones
│   ├── store_mapping.json             # Maps real store IDs (ST1008) to API-format IDs (STORE_BLR_002); camera-to-clip filename mapping
│   ├── pos_transactions.csv           # The Brigade Bangalore CSV you have, reformatted to match the POS schema the pipeline expects
│
├── docs/
│   ├── DESIGN.md                      # Plain-English architecture walkthrough; system diagram; section "AI-Assisted Decisions" covering 2–3 places LLM shaped design; data flow from frame → event → metric
│   └── CHOICES.md                     # Three decisions: (1) YOLOv8m+ByteTrack vs alternatives, (2) event schema rationale (why visitor_id is session-scoped, not person-scoped), (3) PostgreSQL vs SQLite for API storage; each with options considered, AI suggestion, and your final call
│
├── migrations/
│   ├── env.py                         # Alembic env file pointing to database.py engine
│   └── versions/
│       └── 001_initial_schema.py      # Creates all five DB tables in one migration
│
├── docker-compose.yml                 # Defines 4 services: api (port 8000), postgres (5432), redis (6379), dashboard (8501); sets up healthchecks and inter-service depends_on
├── Dockerfile                         # Multi-stage: builder installs torch + ultralytics + torchreid; runtime image strips build deps; both pipeline and API share this image via CMD override
├── .env.example                       # Template for DATABASE_URL, REDIS_URL, LOG_LEVEL, CONFIDENCE_THRESHOLD, REID_SIMILARITY_THRESHOLD
├── requirements.txt                   # API deps: fastapi, uvicorn, sqlalchemy, asyncpg, redis, pydantic-settings, structlog, prometheus-fastapi-instrumentator, alembic
├── requirements-pipeline.txt          # Pipeline deps: ultralytics, torch, torchreid, opencv-python, shapely, numpy, httpx (for posting events to API)
└── README.md                          # Setup in exactly 5 commands; how to run detection against clips; how to feed output into API; local dashboard URL; known edge case behaviour
