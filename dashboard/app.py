# You are writing a Streamlit live dashboard for a retail store CCTV analytics system.

# FILE: dashboard/app.py

import json
import os
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import httpx
import plotly.graph_objects as go
import streamlit as st

# ─── Config ─────────────────────────────────────────────────────────────────
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
REFRESH_SECONDS = int(os.getenv("DASHBOARD_REFRESH_SECONDS", "3"))
DEFAULT_STORE = "STORE_BLR_002"
QUEUE_SPIKE_THRESHOLD = 5
EVENTS_JSONL_PATH = Path(os.getenv("EVENTS_JSONL_PATH", "data/events/STORE_BLR_002_events.jsonl"))


def _parse_timestamp(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def load_jsonl_events(path: Path) -> list[dict]:
    if not path.exists():
        return []

    events: list[dict] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except Exception:
        return []
    return events


def _event_window(events: list[dict], window_hours: int) -> list[dict]:
    now = datetime.utcnow()
    cutoff = now.timestamp() - (window_hours * 3600)
    filtered: list[dict] = []
    for event in events:
        ts = _parse_timestamp(str(event.get("timestamp", "")))
        if ts is None:
            continue
        if ts.timestamp() >= cutoff:
            filtered.append(event)

    # If the live window returned nothing but events exist, auto-adjust:
    # use the latest event timestamp as the reference point so historical
    # data is always visible on the dashboard.
    if not filtered and events:
        latest_ts = None
        for event in events:
            ts = _parse_timestamp(str(event.get("timestamp", "")))
            if ts is not None and (latest_ts is None or ts > latest_ts):
                latest_ts = ts
        if latest_ts is not None:
            hist_cutoff = latest_ts.timestamp() - (window_hours * 3600)
            for event in events:
                ts = _parse_timestamp(str(event.get("timestamp", "")))
                if ts is None:
                    continue
                if ts.timestamp() >= hist_cutoff:
                    filtered.append(event)

    return filtered


def compute_local_dashboard_data(events: list[dict], store_id: str, window_hours: int) -> dict:
    filtered = [e for e in _event_window(events, window_hours) if e.get("store_id") == store_id]
    if not filtered:
        return {
            "metrics": None,
            "funnel": None,
            "heatmap": None,
            "anomalies": None,
        }

    non_staff = [e for e in filtered if not e.get("is_staff", False)]
    unique_visitors = sorted({e.get("visitor_id") for e in non_staff if e.get("visitor_id")})
    visitor_ids = set(unique_visitors)

    entry_visitors = {
        e.get("visitor_id")
        for e in non_staff
        if e.get("event_type") in {"ENTRY", "REENTRY"} and e.get("visitor_id")
    }

    zone_visitors = {
        e.get("visitor_id")
        for e in non_staff
        if e.get("event_type") == "ZONE_ENTER"
        and e.get("zone_id") not in {None, "ENTRY_THRESHOLD", "BILLING", "BILLING_QUEUE"}
        and e.get("visitor_id")
    }

    queue_join_events = [e for e in non_staff if e.get("event_type") == "BILLING_QUEUE_JOIN"]
    queue_join_visitors = {e.get("visitor_id") for e in queue_join_events if e.get("visitor_id")}
    queue_abandon_visitors = {
        e.get("visitor_id") for e in non_staff if e.get("event_type") == "BILLING_QUEUE_ABANDON" and e.get("visitor_id")
    }

    latest_queue_depth = 0
    for event in reversed(queue_join_events):
        metadata = event.get("metadata") or {}
        if isinstance(metadata, dict):
            latest_queue_depth = int(metadata.get("queue_depth") or 0)
            break

    converted_visitors = {
        visitor_id
        for visitor_id in queue_join_visitors
        if visitor_id not in queue_abandon_visitors
        and any(e.get("visitor_id") == visitor_id and e.get("event_type") == "EXIT" for e in non_staff)
    }

    total_visitors = max(len(visitor_ids), 1)
    conversion_rate = len(converted_visitors) / total_visitors
    abandonment_rate = len(queue_abandon_visitors) / max(len(queue_join_visitors), 1)

    zone_counts: dict[str, int] = Counter()
    zone_dwell: dict[str, list[float]] = defaultdict(list)
    for event in non_staff:
        zone_id = event.get("zone_id")
        if not zone_id:
            continue
        if event.get("event_type") in {"ZONE_ENTER", "ZONE_DWELL", "ZONE_EXIT"}:
            zone_counts[zone_id] += 1
        if event.get("event_type") in {"ZONE_DWELL", "ZONE_EXIT"}:
            dwell_ms = event.get("dwell_ms") or 0
            zone_dwell[zone_id].append(float(dwell_ms))

    max_visits = max(zone_counts.values(), default=0)
    zones: list[dict] = []
    for zone_id, visit_count in zone_counts.items():
        dwell_values = zone_dwell.get(zone_id, [])
        avg_dwell_ms = sum(dwell_values) / len(dwell_values) if dwell_values else 0.0
        zones.append(
            {
                "zone_id": zone_id,
                "display_name": zone_id.replace("_", " ").title(),
                "visit_count": visit_count,
                "avg_dwell_ms": round(avg_dwell_ms, 2),
                "normalized_score": round((visit_count / max_visits * 100) if max_visits else 0.0, 2),
                "data_confidence": len(filtered) >= 20,
            }
        )

    zones.sort(key=lambda item: item["normalized_score"], reverse=True)

    stage_purchase = len(converted_visitors)
    stage_billing = len(queue_join_visitors)
    stage_zone = len(zone_visitors)
    stage_entry = len(entry_visitors)

    def drop_off(current: int, previous: int) -> float:
        if previous <= 0:
            return 0.0
        return max(0.0, round(((previous - current) / previous) * 100, 2))

    funnel = {
        "store_id": store_id,
        "window_start": filtered[0]["timestamp"],
        "window_end": filtered[-1]["timestamp"],
        "stages": [
            {"stage": "entry", "count": stage_entry, "drop_off_pct": 0.0},
            {"stage": "zone_visit", "count": stage_zone, "drop_off_pct": drop_off(stage_zone, stage_entry)},
            {"stage": "billing_queue", "count": stage_billing, "drop_off_pct": drop_off(stage_billing, stage_zone)},
            {"stage": "purchase", "count": stage_purchase, "drop_off_pct": drop_off(stage_purchase, stage_billing)},
        ],
        "total_sessions": stage_entry,
    }

    metrics = {
        "store_id": store_id,
        "window_start": filtered[0]["timestamp"],
        "window_end": filtered[-1]["timestamp"],
        "unique_visitors": len(visitor_ids),
        "conversion_rate": round(conversion_rate, 4),
        "avg_dwell_per_zone": [
            {
                "zone_id": zone["zone_id"],
                "display_name": zone["display_name"],
                "avg_dwell_seconds": round(zone["avg_dwell_ms"] / 1000.0, 2),
                "visit_count": zone["visit_count"],
            }
            for zone in zones
        ],
        "queue_depth": latest_queue_depth,
        "abandonment_rate": round(abandonment_rate, 4),
        "total_transactions": len(converted_visitors),
    }

    now = datetime.utcnow()
    last_event_ts = _parse_timestamp(str(filtered[-1].get("timestamp", "")))
    minutes_since_last = ((now - last_event_ts).total_seconds() / 60) if last_event_ts else None
    anomalies: list[dict] = []
    if latest_queue_depth >= QUEUE_SPIKE_THRESHOLD:
        anomalies.append(
            {
                "anomaly_id": f"local-queue-{latest_queue_depth}",
                "anomaly_type": "BILLING_QUEUE_SPIKE",
                "severity": "CRITICAL" if latest_queue_depth >= 10 else "WARN",
                "description": f"Billing queue depth is {latest_queue_depth}.",
                "suggested_action": "Review billing counter staffing.",
                "detected_at": filtered[-1]["timestamp"],
                "details": {"current_depth": latest_queue_depth},
            }
        )
    if minutes_since_last is not None and minutes_since_last >= 10:
        anomalies.append(
            {
                "anomaly_id": "local-stale-feed",
                "anomaly_type": "STALE_FEED",
                "severity": "WARN",
                "description": f"No events received in the last {minutes_since_last:.1f} minutes.",
                "suggested_action": "Check CCTV pipeline connectivity and camera feeds.",
                "detected_at": filtered[-1]["timestamp"],
                "details": {"minutes_since_last_event": round(minutes_since_last, 1)},
            }
        )

    return {
        "metrics": metrics,
        "funnel": funnel,
        "heatmap": {
            "store_id": store_id,
            "window_start": filtered[0]["timestamp"],
            "window_end": filtered[-1]["timestamp"],
            "zones": zones,
        },
        "anomalies": {
            "store_id": store_id,
            "checked_at": filtered[-1]["timestamp"],
            "anomalies": anomalies,
            "anomaly_count": len(anomalies),
        },
    }


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

source_label = "API"
if not any([metrics_data, funnel_data, heatmap_data, anomaly_data]):
    local_events = load_jsonl_events(EVENTS_JSONL_PATH)
    local_data = compute_local_dashboard_data(local_events, store_id, window_hours)
    metrics_data = metrics_data or local_data["metrics"]
    funnel_data = funnel_data or local_data["funnel"]
    heatmap_data = heatmap_data or local_data["heatmap"]
    anomaly_data = anomaly_data or local_data["anomalies"]
    if any([metrics_data, funnel_data, heatmap_data, anomaly_data]):
        source_label = f"JSONL fallback: {EVENTS_JSONL_PATH}"

# ─── Health banner ───────────────────────────────────────────────────────────
if health_data:
    status = health_data.get("status", "UNKNOWN")
    if status in ("DEGRADED", "UNHEALTHY"):
        st.error(f"⚠️ System Status: **{status}** — Check /health for details.")
elif metrics_data is None:
    st.warning("⚠️ API unavailable — retrying...")

st.title(f"📊 Store Dashboard — {store_id}")
st.caption(f"Data source: {source_label}")

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
