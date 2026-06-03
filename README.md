# Store Intelligence

Store Intelligence is a retail CCTV analytics system for a single store site. It converts video clips into structured visitor events, stores them in a relational database, computes operational metrics, and surfaces live dashboards for store health, funnel performance, zone activity, and anomalies.

The project is split into three main parts:

- `app/` contains the FastAPI backend, database models, analytics endpoints, and health checks.
- `pipeline/` contains the CCTV processing pipeline that tracks people, classifies zones, detects queue activity, correlates POS transactions, and emits events.
- `dashboard/` contains the Streamlit dashboard that reads the API and presents the store state visually.

## What This Project Does

The pipeline processes CCTV recordings and turns them into events such as `ENTRY`, `EXIT`, `ZONE_ENTER`, `ZONE_DWELL`, `BILLING_QUEUE_JOIN`, `BILLING_QUEUE_ABANDON`, and `REENTRY`. Those events are persisted through the API into Postgres. The API then computes:

- visitor metrics
- conversion funnel stages
- heatmap activity by zone
- anomaly detection signals
- health status for Postgres, Redis, and store feeds

The dashboard pulls those endpoints and renders a live operational view.

## Repository Layout

- `app/main.py` application factory, routes, WebSocket feed, Prometheus mount
- `app/routers/` REST endpoints for health, events, and store analytics
- `app/services/` business logic for ingestion, metrics, funnel, heatmap, anomalies
- `pipeline/` offline video-to-event pipeline
- `dashboard/app.py` live Streamlit dashboard
- `data/` store layout, store mapping, sample inputs, POS sample data
- `tests/` pytest suite for API and pipeline components

## Requirements

- Python 3.11
- Docker Desktop for Postgres and Redis, or local Postgres and Redis services
- On Windows, PowerShell 5.1 or later

## Environment File

Yes, you should have a `.env` file for local runs. The app and migration code load environment variables from `.env`, and the Docker Compose file also uses those values for substitution.

This repository includes `.env.example` as the template. The `.env` file added in this workspace matches that example and is safe for local development.

If you ever change the Postgres credentials, make sure the API, Docker Compose, and the database volume all agree on the same values.

## Running On Windows PowerShell

### 1. Activate the virtual environment

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks script execution, allow it for the current process only:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

### 2. Start Postgres and Redis

```powershell
docker compose up -d postgres redis
```

If you see a password authentication error on startup, the most common cause is a previously created Postgres volume with a different password. Recreate it with:

```powershell
docker compose down -v
docker compose up -d postgres redis
```

### 3. Start the API

```powershell
uvicorn app.main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

### 4. Start the dashboard

Open a second PowerShell window and run:

```powershell
streamlit run dashboard\app.py
```

The dashboard will be available at `http://localhost:8501`.

### 5. Run the test suite

```powershell
pytest
```

## How To Test The Project

### API smoke tests

After the API starts, verify the main endpoints:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/stores/STORE_BLR_002/metrics
Invoke-RestMethod http://127.0.0.1:8000/stores/STORE_BLR_002/funnel
Invoke-RestMethod http://127.0.0.1:8000/stores/STORE_BLR_002/heatmap
Invoke-RestMethod http://127.0.0.1:8000/stores/STORE_BLR_002/anomalies
```

### Automated tests

The repository already includes tests for ingestion, metrics, funnel, anomalies, and pipeline helpers. Run them with `pytest`. The tests use SQLite in memory for most API coverage, so they are quick and do not require you to point them at a live production database.

### Event ingestion test

You can manually post events to the API with a JSON payload shaped like this:

```powershell
$body = @{
	events = @(
		@{
			event_id = [guid]::NewGuid().ToString()
			store_id = 'STORE_BLR_002'
			camera_id = 'CAM_ENTRY_01'
			visitor_id = 'VIS_ABC123'
			event_type = 'ENTRY'
			timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
			zone_id = $null
			dwell_ms = 0
			is_staff = $false
			confidence = 0.9
			metadata = @{ queue_depth = $null; sku_zone = $null; session_seq = 1 }
		}
	)
} | ConvertTo-Json -Depth 6

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/events/ingest -ContentType 'application/json' -Body $body
```

## How To Use Your CCTV Recordings

The pipeline expects a folder of video clips and assigns them to store cameras using filename keywords first, then clip order as fallback. The current store mapping has three camera roles:

- `CAM_ENTRY_01`
- `CAM_FLOOR_01`
- `CAM_BILLING_01`

### Recommended clip folder setup

Put all clips into one folder, for example:

```text
D:\CCTV\store-001\
	entry_cam1.mp4
	floor_cam2.mp4
	billing_cam3.mp4
	floor_cam2_part2.mp4
	entry_cam1_part2.mp4
```

The filename keywords used by the matcher are:

- Entry camera: `entry`, `entrance`, `door`, `threshold`, `cam1`, `camera1`
- Floor camera: `floor`, `main`, `foh`, `general`, `wide`, `cam2`, `camera2`
- Billing camera: `billing`, `counter`, `cash`, `pos`, `checkout`, `cam3`, `camera3`

### Important limitation

The current configuration maps only one clip to each camera role. If you have 5 recordings and they represent 5 different camera viewpoints, you should extend `data/store_mapping.json` and `data/store_layout.json` to add the extra cameras and polygons.

If the 5 recordings are multiple segments from the same three cameras, you can use them in either of these ways:

- rename the clips so the keyword matcher picks the intended camera role
- merge same-camera segments into a single longer clip before processing

### Run the pipeline on your clips

First, verify event generation without posting to the API:

```powershell
python pipeline\detect.py --clips-dir "D:\CCTV\store-001" --output-dir data\events --api-url http://127.0.0.1:8000 --no-api-post
```

Then run it with API posting enabled:

```powershell
python pipeline\detect.py --clips-dir "D:\CCTV\store-001" --output-dir data\events --api-url http://127.0.0.1:8000
```

The pipeline writes a JSONL file named:

```text
data/events/STORE_BLR_002_events.jsonl
```

That file is the easiest place to inspect whether detections, queue events, zone events, and re-entry events look reasonable.

## End-To-End Test Flow

1. Start Postgres and Redis with Docker Compose.
2. Start the API with Uvicorn.
3. Confirm `/health` returns `HEALTHY` or at least a non-error status.
4. Run the pipeline on a small clip set with `--no-api-post` first.
5. Inspect the generated JSONL events.
6. Re-run the pipeline with API posting enabled.
7. Open the dashboard and confirm metrics and anomalies update.
8. Run `pytest` to verify the codebase behavior.

## Troubleshooting

### `password authentication failed for user "store_user"`

This usually means one of two things:

- your `.env` and Compose defaults do not match
- the Postgres volume was created earlier with a different password and needs to be recreated

Use:

```powershell
docker compose down -v
docker compose up -d postgres redis
```

### API starts but health is degraded

Check that Redis is running and that the database URL in `.env` points to the correct host and port.

### Pipeline cannot open videos

Make sure the clips are readable on disk and that OpenCV can open the container format. MP4 is the safest choice.

### Dashboard shows no data

Confirm the pipeline successfully posted events to the API, and check that the API health endpoint is healthy.

## Notes

- `pipeline/run.sh` is a Bash script and is most convenient in Git Bash or WSL. On Windows PowerShell, run `pipeline\detect.py` directly as shown above.
- The API creates tables on startup through SQLAlchemy, and Alembic migrations are available for database schema management.
- Prometheus metrics are mounted at `/metrics`.
