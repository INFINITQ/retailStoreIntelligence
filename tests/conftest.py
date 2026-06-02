# You are writing the pytest configuration and fixtures for a retail store CCTV analytics API test suite.

# FILE: tests/conftest.py

import asyncio
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app
from app.models.db_models import AnomalyLog, Event, POSTransaction, VisitorSession


def pytest_configure(config):
    config.addinivalue_line("markers", "asyncio: mark test as async")


pytestmark = pytest.mark.asyncio

# ─── Event loop ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ─── In-memory SQLite DB ─────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="function")
async def test_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


# ─── Test client with overridden DB ──────────────────────────────────────────

@pytest_asyncio.fixture(scope="function")
async def test_client(test_db):
    async def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


# ─── Event factory ────────────────────────────────────────────────────────────

def make_event(**overrides) -> dict:
    base = {
        "event_id": str(uuid.uuid4()),
        "store_id": "STORE_BLR_002",
        "camera_id": "CAM_ENTRY_01",
        "visitor_id": "VIS_AABBCC",
        "event_type": "ENTRY",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "zone_id": None,
        "dwell_ms": 0,
        "is_staff": False,
        "confidence": 0.85,
        "metadata": {"queue_depth": None, "sku_zone": None, "session_seq": 1},
    }
    base.update(overrides)
    return base


# ─── Session factory ─────────────────────────────────────────────────────────

def make_session(**overrides) -> dict:
    base = {
        "session_id": str(uuid.uuid4()),
        "store_id": "STORE_BLR_002",
        "visitor_id": "VIS_AABBCC",
        "entry_timestamp": datetime.now(timezone.utc),
        "exit_timestamp": None,
        "is_reentry": False,
        "is_converted": False,
        "is_staff": False,
        "zones_visited": [],
        "total_dwell_ms": 0,
    }
    base.update(overrides)
    return base


# ─── POS transaction seeder ───────────────────────────────────────────────────

async def seed_pos_transaction(
    db: AsyncSession,
    store_id: str = "STORE_BLR_002",
    visitor_session_id: str = None,
    basket: float = 500.0,
) -> POSTransaction:
    txn = POSTransaction(
        store_id=store_id,
        transaction_id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc),
        basket_value_inr=basket,
        visitor_session_id=visitor_session_id,
    )
    db.add(txn)
    await db.commit()
    await db.refresh(txn)
    return txn
