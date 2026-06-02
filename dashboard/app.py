# You are writing a Streamlit live dashboard for a retail store CCTV analytics system.

# FILE: dashboard/app.py

import os
import time
from datetime import datetime

import httpx
import plotly.graph_objects as go
import streamlit as st

# ─── Config ─────────────────────────────────────────────────────────────────
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
REFRESH_SECONDS = int(os.getenv("DASHBOARD_REFRESH_SECONDS", "3"))
DEFAULT_STORE = "STORE_BLR_002"
QUEUE_SPIKE_THRESHOLD = 5


def fetch_data(endpoint: str) -> dict | None:
    try:
        resp = httpx.get(f"{API_BASE_URL}{endpoint}", timeout=5.0)
        if resp.is_success:
            return resp.json()
    except Exception:
        pass
    return None


# ─── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Store Intelligence",
    layout="wide",
    page_icon="🛍️",
)

# ─── Custom CSS ──────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
        [data-testid="stMetricValue"] { font-size: 2rem; }
        .stApp { background-color: #0f172a; color: #f1f5f9; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🛍️ Store Intelligence")
    st.markdown("---")
    store_id = st.selectbox("Store", [DEFAULT_STORE], index=0)
    window_hours = st.slider("Window (hours)", min_value=1, max_value=48, value=24)
    st.markdown("---")
    last_refreshed = st.empty()
    last_refreshed.caption(f"Last refreshed: {datetime.now().strftime('%H:%M:%S')}")

# ─── Fetch data ───────────────────────────────────────────────────────────────
health_data = fetch_data("/health")
metrics_data = fetch_data(f"/stores/{store_id}/metrics?window_hours={window_hours}")
funnel_data = fetch_data(f"/stores/{store_id}/funnel?window_hours={window_hours}")
heatmap_data = fetch_data(f"/stores/{store_id}/heatmap?window_hours={window_hours}")
anomaly_data = fetch_data(f"/stores/{store_id}/anomalies")

# ─── Health banner ───────────────────────────────────────────────────────────
if health_data:
    status = health_data.get("status", "UNKNOWN")
    if status in ("DEGRADED", "UNHEALTHY"):
        st.error(f"⚠️ System Status: **{status}** — Check /health for details.")
elif metrics_data is None:
    st.warning("⚠️ API unavailable — retrying...")

st.title(f"📊 Store Dashboard — {store_id}")

# ─── KPI row ─────────────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)

if metrics_data:
    unique_visitors = metrics_data.get("unique_visitors", 0)
    conversion_rate = metrics_data.get("conversion_rate", 0.0)
    queue_depth = metrics_data.get("queue_depth", 0)
    abandonment_rate = metrics_data.get("abandonment_rate", 0.0)

    col1.metric("👥 Unique Visitors", unique_visitors)
    col2.metric("💳 Conversion Rate", f"{conversion_rate * 100:.1f}%")

    queue_color = "🔴" if queue_depth >= QUEUE_SPIKE_THRESHOLD else "🟢"
    col3.metric(f"{queue_color} Queue Depth", queue_depth)
    col4.metric("🚪 Abandonment Rate", f"{abandonment_rate * 100:.1f}%")
else:
    col1.metric("👥 Unique Visitors", "—")
    col2.metric("💳 Conversion Rate", "—")
    col3.metric("🟡 Queue Depth", "—")
    col4.metric("🚪 Abandonment Rate", "—")

st.markdown("---")

# ─── Second row: Funnel + Anomalies ──────────────────────────────────────────
left_col, right_col = st.columns([3, 2])

with left_col:
    st.subheader("🔽 Conversion Funnel")
    if funnel_data and funnel_data.get("stages"):
        stages = funnel_data["stages"]
        labels = [s["stage"].replace("_", " ").title() for s in stages]
        counts = [s["count"] for s in stages]
        drop_pcts = [s["drop_off_pct"] for s in stages]

        texts = [
            f"{c} visitors" + (f"<br>↓ {d:.1f}% drop-off" if i > 0 else "")
            for i, (c, d) in enumerate(zip(counts, drop_pcts))
        ]

        fig_funnel = go.Figure(
            go.Bar(
                x=counts,
                y=labels,
                orientation="h",
                marker_color=["#6366f1", "#8b5cf6", "#a78bfa", "#c4b5fd"],
                text=texts,
                textposition="inside",
                insidetextanchor="middle",
            )
        )
        fig_funnel.update_layout(
            plot_bgcolor="#1e293b",
            paper_bgcolor="#1e293b",
            font_color="#f1f5f9",
            xaxis=dict(showgrid=False, zeroline=False),
            yaxis=dict(showgrid=False),
            margin=dict(l=10, r=10, t=10, b=10),
            height=280,
        )
        st.plotly_chart(fig_funnel, use_container_width=True)
    else:
        st.info("No funnel data available.")

with right_col:
    st.subheader("🚨 Active Anomalies")
    if anomaly_data:
        anomalies = anomaly_data.get("anomalies", [])
        if not anomalies:
            st.success("✅ No active anomalies")
        else:
            for a in anomalies:
                severity = a.get("severity", "INFO")
                atype = a.get("anomaly_type", "")
                action = a.get("suggested_action", "")
                msg = f"**{atype}** — {action}"
                if severity == "CRITICAL":
                    st.error(msg)
                elif severity == "WARN":
                    st.warning(msg)
                else:
                    st.info(msg)
    else:
        st.info("Anomaly data unavailable.")

st.markdown("---")

# ─── Zone Heatmap ─────────────────────────────────────────────────────────────
st.subheader("🗺️ Zone Activity Heatmap")
if heatmap_data and heatmap_data.get("zones"):
    zones = heatmap_data["zones"]
    zone_names = [
        z["display_name"] + ("*" if not z.get("data_confidence", True) else "")
        for z in zones
    ]
    norm_scores = [[z.get("normalized_score", 0) for z in zones]]
    hover_texts = [
        [f"Avg dwell: {z.get('avg_dwell_ms', 0) / 1000:.1f}s<br>Visits: {z.get('visit_count', 0)}"
         for z in zones]
    ]

    fig_heat = go.Figure(
        go.Heatmap(
            z=norm_scores,
            x=zone_names,
            y=["Score"],
            colorscale=[[0, "#1e293b"], [0.5, "#6366f1"], [1.0, "#4f46e5"]],
            zmin=0,
            zmax=100,
            text=hover_texts,
            hovertemplate="%{x}<br>%{text}<extra></extra>",
            showscale=True,
        )
    )
    fig_heat.update_layout(
        plot_bgcolor="#1e293b",
        paper_bgcolor="#1e293b",
        font_color="#f1f5f9",
        margin=dict(l=10, r=10, t=10, b=10),
        height=160,
    )
    st.plotly_chart(fig_heat, use_container_width=True)
    st.caption("\\* Low-confidence zones (< 20 sessions in window)")
else:
    st.info("No heatmap data available.")

# ─── Auto-refresh ─────────────────────────────────────────────────────────────
time.sleep(REFRESH_SECONDS)
st.rerun()
