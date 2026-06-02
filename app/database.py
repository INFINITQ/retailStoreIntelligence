# You are writing the database module for a FastAPI retail analytics API.

# FILE: app/database.py
# PURPOSE: Async SQLAlchemy engine and session factory. Provides async session dependency
# for FastAPI routes and a sync engine for Alembic migrations.

# TECH: Python 3.11, sqlalchemy[asyncio]==2.0.36, asyncpg==0.30.0, psycopg2-binary

# IMPLEMENT:

# 1. Create async engine:
#    `async_engine = create_async_engine(settings.database_url, pool_size=10,
#     max_overflow=20, pool_pre_ping=True, echo=(settings.environment=="development"))`

# 2. Create sync engine (for Alembic only):
#    `sync_engine = create_engine(settings.database_url_sync, pool_pre_ping=True)`

# 3. `AsyncSessionLocal = async_sessionmaker(async_engine, class_=AsyncSession,
#     expire_on_commit=False)`

# 4. `Base = declarative_base()`

# 5. Async dependency for FastAPI:
#    ```python
#    async def get_db() -> AsyncGenerator[AsyncSession, None]:
#        async with AsyncSessionLocal() as session:
#            try:
#                yield session
#                await session.commit()
#            except Exception:
#                await session.rollback()
#                raise
#    ```

# 6. `async def init_db() -> None:` — called on app startup; creates all tables if missing
#    (async with async_engine.begin() as conn: await conn.run_sync(Base.metadata.create_all))

# 7. `async def check_db_health() -> bool:` — try a simple SELECT 1; return True/False.
#    Used by /health endpoint.

# IMPORTS NEEDED:
#   sqlalchemy.ext.asyncio (create_async_engine, AsyncSession, async_sessionmaker),
#   sqlalchemy.orm (declarative_base), sqlalchemy (create_engine),
#   typing (AsyncGenerator), app.config (settings)

from typing import AsyncGenerator

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from app.config import settings

async_engine = create_async_engine(
    settings.database_url,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=(settings.environment == "development"),
)

sync_engine = create_engine(settings.database_url_sync, pool_pre_ping=True)

AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Create all tables if they don't exist yet (idempotent startup hook)."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def check_db_health() -> bool:
    """Try SELECT 1; return True if DB is reachable, False otherwise."""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
