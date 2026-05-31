# Write a Bash script at path pipeline/run.sh for a retail store CCTV analytics pipeline project.

# PURPOSE: Single-command entry point to run the full detection pipeline against CCTV clips
# and optionally feed results to the API.

# IMPLEMENT:
# 1. Shebang: #!/usr/bin/env bash
# 2. set -euo pipefail
# 3. Print a usage function that explains: run.sh <clips_dir> [output_dir] [api_url]
#    Exit with code 1 if clips_dir argument is missing.
# 4. Accept positional arguments:
#    - CLIPS_DIR=$1
#    - OUTPUT_DIR=${2:-"./data/events"}
#    - API_URL=${3:-"http://localhost:8000"}
# 5. Set STORE_ID="STORE_BLR_002"
# 6. Print a header banner showing the three parameters.
# 7. Create output directory if it doesn't exist: mkdir -p "$OUTPUT_DIR"
# 8. Activate a Python virtual environment if ./venv/bin/activate exists; otherwise proceed
#    with system Python (print a notice).
# 9. Install requirements if a --install flag is passed as $4 (optional feature):
#    pip install -r requirements.txt
#    pip install torch==2.5.1+cpu torchvision==0.20.1+cpu --index-url https://download.pytorch.org/whl/cpu
#    pip install -r requirements-pipeline.txt
# 10. Run the detection pipeline:
#     python pipeline/detect.py \
#       --clips-dir "$CLIPS_DIR" \
#       --output-dir "$OUTPUT_DIR" \
#       --api-url "$API_URL" \
#       --store-id "$STORE_ID" \
#       --layout "data/store_layout.json" \
#       --mapping "data/store_mapping.json" \
#       --pos-data "data/pos_transactions.csv"
# 11. On success: print "Pipeline complete. Events written to $OUTPUT_DIR"
# 12. Print the path to the generated JSONL file.
# 13. chmod +x instruction in a comment at the top: # Run: chmod +x pipeline/run.sh && ./pipeline/run.sh <clips_dir>
