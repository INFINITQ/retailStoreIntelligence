# You are writing a WebSocket + polling API client helper for a Streamlit retail analytics dashboard.

# FILE: dashboard/ws_client.py
# PURPOSE: Provides a clean client class that the Streamlit dashboard uses to fetch data from
# the Store Intelligence API. Handles connection errors gracefully. Also provides a thread-based
# Redis subscriber for near-real-time event counting without blocking Streamlit's main thread.

# TECH: Python 3.11, httpx==0.28.1, threading, queue (stdlib), json, os

# IMPLEMENT:

# 1. `class APIClient:`
#    `__init__(self, base_url: str):`
#    - self.base_url = base_url.rstrip("/")
#    - self.session = httpx.Client(timeout=5.0, follow_redirects=True)

#    `get_metrics(self, store_id: str, window_hours: int = 24) -> dict | None:`
#    `get_funnel(self, store_id: str, window_hours: int = 24) -> dict | None:`
#    `get_heatmap(self, store_id: str, window_hours: int = 24) -> dict | None:`
#    `get_anomalies(self, store_id: str) -> dict | None:`
#    `get_health(self) -> dict | None:`
#    Each method:
#    - Calls the corresponding endpoint via self.session.get(...).
#    - Returns response.json() on 2xx, None on any error (log the error).

#    `close(self) -> None:` — closes self.session.

# 2. `class EventStreamSubscriber:`
#    PURPOSE: Subscribes to Redis "store_events" pub/sub channel in a background thread.
#    Maintains a counter of events received per store_id since last reset.

#    `__init__(self, redis_url: str):`
#    - self.redis_url = redis_url
#    - self._event_counts: dict[str, int] = {}
#    - self._lock = threading.Lock()
#    - self._stop_event = threading.Event()
#    - self._thread: threading.Thread (daemon=True)

#    `start(self) -> None:` — starts background thread.
#    `stop(self) -> None:` — sets stop_event; joins thread.
#    `get_event_count(self, store_id: str) -> int:` — thread-safe read.
#    `reset_count(self, store_id: str) -> None:` — thread-safe reset to 0.

#    Background thread logic:
#    - Try to connect to Redis (redis.Redis.from_url with decode_responses=True).
#    - Subscribe to "store_events". Listen in a loop; on each message:
#      - Parse JSON; extract store_id.
#      - Increment self._event_counts[store_id].
#    - On ConnectionError: sleep 5s, retry. If stop_event set: exit.

# IMPORTS NEEDED: httpx, threading, json, os, time, typing (Optional)
# (import redis only inside the thread function so the module remains importable without Redis)
