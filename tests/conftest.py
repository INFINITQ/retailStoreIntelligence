# You are writing the pytest configuration and fixtures for a retail store CCTV analytics API test suite.

# FILE: tests/conftest.py
# PURPOSE: Shared pytest fixtures: in-memory SQLite test database, async test client (httpx),
# sample event factory, and POS transaction seeder.

# TECH: Python 3.11, pytest==8.3.4, pytest-asyncio==0.24.0, httpx==0.28.1,
# sqlalchemy[asyncio], aiosqlite

# IMPLEMENT:

# 1. pytest.ini settings at top of file:
#    `pytestmark = pytest.mark.asyncio`
#    Configure asyncio_mode = "auto" via:
#    ```python
#    def pytest_configure(config):
#        config.addinivalue_line("markers", "asyncio: mark test as async")
#    ```

# 2. Fixture `event_loop` (scope="session") — yields a new asyncio event loop.

# 3. Fixture `test_db` (scope="function", async):
#    - Create in-memory SQLite async engine: create_async_engine("sqlite+aiosqlite:///:memory:")
#    - Run async Base.metadata.create_all.
#    - Yield AsyncSession from async_sessionmaker.
#    - Drop all tables after test.
#    Note: import aiosqlite to ensure driver is available (add to requirements.txt if missing).

# 4. Fixture `test_client` (scope="function", async):
#    - Override app's get_db dependency to use test_db session.
#    - Use httpx.AsyncClient(app=app, base_url="http://test") as client.
#    - Yield client.

# 5. Factory function `make_event(**overrides) -> dict`:
#    Returns a valid event dict with all required fields, using sensible defaults,
#    merged with any overrides. Example defaults:
#    - event_id: str(uuid.uuid4())
#    - store_id: "STORE_BLR_002"
#    - camera_id: "CAM_ENTRY_01"
#    - visitor_id: "VIS_AABBCC"
#    - event_type: "ENTRY"
#    - timestamp: datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
#    - zone_id: None
#    - dwell_ms: 0
#    - is_staff: False
#    - confidence: 0.85
#    - metadata: {"queue_depth": None, "sku_zone": None, "session_seq": 1}

# 6. Factory function `make_session(**overrides) -> dict`:
#    Returns a dict representing a VisitorSession row.

# 7. `async def seed_pos_transaction(db, store_id, visitor_session_id=None, basket=500.0)`
#    — inserts a POSTransaction row into the test DB.

# IMPORTS NEEDED:
#   pytest, pytest_asyncio, asyncio, uuid, datetime (datetime, timezone),
#   sqlalchemy.ext.asyncio, httpx,
#   app.main (app), app.database (Base, get_db),
#   app.models.db_models (all models)
