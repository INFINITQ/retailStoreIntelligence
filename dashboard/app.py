# You are writing a Streamlit live dashboard for a retail store CCTV analytics system.

# FILE: dashboard/app.py
# PURPOSE: Real-time store metrics dashboard. Polls the Store Intelligence API every 3 seconds
# and displays: visitor count, conversion rate, queue depth, abandonment rate, conversion funnel
# chart, zone heatmap grid, and active anomalies with severity colour coding.

# TECH: Python 3.11, streamlit==1.41.0, plotly==5.24.1, httpx==0.28.1, pandas==2.2.3

# API ENDPOINTS CONSUMED:
# - GET {API_BASE_URL}/stores/{store_id}/metrics?window_hours=24
# - GET {API_BASE_URL}/stores/{store_id}/funnel?window_hours=24
# - GET {API_BASE_URL}/stores/{store_id}/heatmap?window_hours=24
# - GET {API_BASE_URL}/stores/{store_id}/anomalies
# - GET {API_BASE_URL}/health

# IMPLEMENT:

# 1. Config from env: API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000"),
#    REFRESH_SECONDS = int(os.getenv("DASHBOARD_REFRESH_SECONDS", "3")),
#    DEFAULT_STORE = "STORE_BLR_002"

# 2. `fetch_data(endpoint: str) -> dict | None:`
#    - Use httpx.get with timeout=5.0. Return JSON dict or None on error.

# 3. `st.set_page_config(page_title="Store Intelligence", layout="wide", page_icon="🛍️")`

# 4. Sidebar: st.title("Store Intelligence"), store selector (st.selectbox with ["STORE_BLR_002"]),
#    window_hours slider (1–48, default 24), last_refreshed timestamp.

# 5. Main layout — four columns for top KPIs:
#    - Col 1: Unique Visitors (st.metric)
#    - Col 2: Conversion Rate % (st.metric with delta from previous fetch)
#    - Col 3: Queue Depth (st.metric, red if spike_threshold >= 5)
#    - Col 4: Abandonment Rate % (st.metric)

# 6. Second row — two columns:
#    - Left (60%): Conversion Funnel — Plotly horizontal bar chart, stages on Y axis,
#      counts on X, drop-off % as text annotations. Use plotly.graph_objects.Bar.
#    - Right (40%): Active Anomalies — for each anomaly, show an st.error() (CRITICAL),
#      st.warning() (WARN), or st.info() (INFO) with anomaly_type + suggested_action.
#      If no anomalies: st.success("No active anomalies").

# 7. Third row — Zone Heatmap: plotly heatmap (go.Heatmap) with zone names on X axis,
#    single row, normalized_score as colour intensity (0=white, 100=deep purple/brand colour).
#    Show avg_dwell_ms as hover text. Low-confidence zones shown with hatching or asterisk label.

# 8. System Health row: if /health shows DEGRADED or UNHEALTHY, show st.error() at top of page.

# 9. Auto-refresh loop at bottom:
#    ```python
#    time.sleep(REFRESH_SECONDS)
#    st.rerun()
#    ```

# 10. Handle API unavailable gracefully: show st.warning("API unavailable — retrying...") 
#     rather than crashing.

# IMPORTS NEEDED: streamlit as st, httpx, plotly.graph_objects as go, pandas as pd,
# os, time, datetime, json
