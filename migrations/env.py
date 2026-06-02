# You are writing the Alembic migration environment file.

# FILE: migrations/env.py

import logging
import os

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

# Load .env
load_dotenv()

# Alembic Config object
config = context.config

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("alembic.env")

# Override DB URL from environment
db_url = os.getenv(
    "DATABASE_URL_SYNC",
    "postgresql+psycopg2://store_user:store_pass@localhost/store_intelligence",
)
config.set_main_option("sqlalchemy.url", db_url)

# Import ORM models so Alembic autogenerate can detect them
from app.database import Base  # noqa: E402
from app.models.db_models import AnomalyLog, Event, POSTransaction, VisitorSession  # noqa: E402, F401

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in offline mode (no live DB connection)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations with a live DB connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
