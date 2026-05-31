# ─────────────────────────────────────────────
# Stage 1 — shared base (system deps only)
# ─────────────────────────────────────────────
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ─────────────────────────────────────────────
# Stage 2 — API + Dashboard (lightweight)
# ─────────────────────────────────────────────
FROM base AS api

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/       ./app/
COPY data/      ./data/
COPY dashboard/ ./dashboard/
COPY migrations/ ./migrations/
COPY alembic.ini .

EXPOSE 8000 8501

# Run migrations then start API
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2"]

# ─────────────────────────────────────────────
# Stage 3 — Pipeline (heavy: adds Torch + CV)
# ─────────────────────────────────────────────
FROM api AS pipeline

COPY requirements-pipeline.txt .

# Install CPU-only PyTorch explicitly before other pipeline deps
RUN pip install --no-cache-dir \
    torch==2.5.1+cpu \
    torchvision==0.20.1+cpu \
    --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir -r requirements-pipeline.txt

# Download YOLOv8n weights at build time so runtime has no network dependency
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"

COPY pipeline/ ./pipeline/

CMD ["python", "pipeline/detect.py", "--help"]
