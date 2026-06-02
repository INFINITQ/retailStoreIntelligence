#!/usr/bin/env bash
# Run: chmod +x pipeline/run.sh && ./pipeline/run.sh <clips_dir>

set -euo pipefail

usage() {
  echo "Usage: $0 <clips_dir> [output_dir] [api_url] [--install]"
  echo ""
  echo "  clips_dir   Directory containing CCTV clip files (*.mp4, *.avi, *.mov)"
  echo "  output_dir  Directory to write JSONL events (default: ./data/events)"
  echo "  api_url     Store Intelligence API URL (default: http://localhost:8000)"
  echo "  --install   Optional: install all Python requirements first"
  echo ""
  echo "Examples:"
  echo "  ./pipeline/run.sh /path/to/clips"
  echo "  ./pipeline/run.sh /path/to/clips ./data/events http://localhost:8000 --install"
  exit 1
}

# Require at least one argument
if [ $# -lt 1 ]; then
  usage
fi

CLIPS_DIR="$1"
OUTPUT_DIR="${2:-./data/events}"
API_URL="${3:-http://localhost:8000}"
INSTALL_FLAG="${4:-}"
STORE_ID="STORE_BLR_002"

echo "=============================================="
echo "  Store Intelligence Detection Pipeline"
echo "=============================================="
echo "  Clips dir   : $CLIPS_DIR"
echo "  Output dir  : $OUTPUT_DIR"
echo "  API URL     : $API_URL"
echo "  Store ID    : $STORE_ID"
echo "=============================================="

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Activate virtual environment if available
if [ -f "./venv/bin/activate" ]; then
  echo "[INFO] Activating virtual environment..."
  # shellcheck disable=SC1091
  source ./venv/bin/activate
else
  echo "[NOTICE] No ./venv found — using system Python."
fi

# Install dependencies if requested
if [ "$INSTALL_FLAG" = "--install" ]; then
  echo "[INFO] Installing requirements..."
  pip install -r requirements.txt
  pip install torch==2.5.1+cpu torchvision==0.20.1+cpu \
    --index-url https://download.pytorch.org/whl/cpu
  pip install -r requirements-pipeline.txt
  echo "[INFO] Requirements installed."
fi

# Run detection pipeline
echo "[INFO] Starting detection pipeline..."
python pipeline/detect.py \
  --clips-dir "$CLIPS_DIR" \
  --output-dir "$OUTPUT_DIR" \
  --api-url "$API_URL" \
  --store-id "$STORE_ID" \
  --layout "data/store_layout.json" \
  --mapping "data/store_mapping.json" \
  --pos-data "data/pos_transactions.csv"

echo ""
echo "=============================================="
echo "  Pipeline complete."
echo "  Events written to: $OUTPUT_DIR"
echo "  JSONL file: $OUTPUT_DIR/${STORE_ID}_events.jsonl"
echo "=============================================="
