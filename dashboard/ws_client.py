# You are writing a WebSocket + polling API client helper for a Streamlit retail analytics dashboard.

# FILE: dashboard/ws_client.py

import json
import threading
import time
from typing import Optional

import httpx


class APIClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = httpx.Client(timeout=5.0, follow_redirects=True)

    def _get(self, url: str) -> Optional[dict]:
        try:
            resp = self.session.get(url)
            if resp.is_success:
                return resp.json()
            return None
        except Exception as exc:
            print(f"[APIClient] GET {url} failed: {exc}")
            return None

    def get_metrics(self, store_id: str, window_hours: int = 24) -> Optional[dict]:
        return self._get(f"{self.base_url}/stores/{store_id}/metrics?window_hours={window_hours}")

    def get_funnel(self, store_id: str, window_hours: int = 24) -> Optional[dict]:
        return self._get(f"{self.base_url}/stores/{store_id}/funnel?window_hours={window_hours}")

    def get_heatmap(self, store_id: str, window_hours: int = 24) -> Optional[dict]:
        return self._get(f"{self.base_url}/stores/{store_id}/heatmap?window_hours={window_hours}")

    def get_anomalies(self, store_id: str) -> Optional[dict]:
        return self._get(f"{self.base_url}/stores/{store_id}/anomalies")

    def get_health(self) -> Optional[dict]:
        return self._get(f"{self.base_url}/health")

    def close(self) -> None:
        self.session.close()


class EventStreamSubscriber:
    """Subscribe to Redis 'store_events' pub/sub in a background thread."""

    def __init__(self, redis_url: str) -> None:
        self.redis_url = redis_url
        self._event_counts: dict[str, int] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=5.0)

    def get_event_count(self, store_id: str) -> int:
        with self._lock:
            return self._event_counts.get(store_id, 0)

    def reset_count(self, store_id: str) -> None:
        with self._lock:
            self._event_counts[store_id] = 0

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                import redis  # imported here so module is importable without Redis

                client = redis.Redis.from_url(self.redis_url, decode_responses=True)
                pubsub = client.pubsub()
                pubsub.subscribe("store_events")

                for message in pubsub.listen():
                    if self._stop_event.is_set():
                        break
                    if message.get("type") != "message":
                        continue
                    try:
                        data = json.loads(message["data"])
                        sid = data.get("store_id", "unknown")
                        with self._lock:
                            self._event_counts[sid] = self._event_counts.get(sid, 0) + 1
                    except (json.JSONDecodeError, KeyError):
                        pass

            except Exception as exc:
                if not self._stop_event.is_set():
                    print(f"[EventStreamSubscriber] Redis error: {exc} — retrying in 5s")
                    time.sleep(5)
