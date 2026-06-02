# You are writing the first Alembic migration for a retail store CCTV analytics API.

# FILE: migrations/versions/001_initial_schema.py

"""Initial schema — creates all four tables.

Revision ID: 001_initial
Revises: None
Create Date: 2026-04-10
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import func

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. visitor_sessions
    op.create_table(
        "visitor_sessions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(36), nullable=False, unique=True),
        sa.Column("store_id", sa.String(50), nullable=False),
        sa.Column("visitor_id", sa.String(20), nullable=False),
        sa.Column("entry_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exit_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_reentry", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("is_converted", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("is_staff", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("zones_visited", sa.JSON, nullable=True),
        sa.Column("total_dwell_ms", sa.Integer, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=func.now(),
        ),
    )
    op.create_index("ix_sessions_store_entry", "visitor_sessions", ["store_id", "entry_timestamp"])
    op.create_index("ix_sessions_visitor", "visitor_sessions", ["visitor_id", "store_id"])

    # 2. events
    op.create_table(
        "events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.String(36), nullable=False, unique=True),
        sa.Column("store_id", sa.String(50), nullable=False),
        sa.Column("camera_id", sa.String(50), nullable=False),
        sa.Column("visitor_id", sa.String(20), nullable=False),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("zone_id", sa.String(50), nullable=True),
        sa.Column("dwell_ms", sa.Integer, server_default="0"),
        sa.Column("is_staff", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("metadata", sa.JSON, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=func.now(),
        ),
    )
    op.create_index("ix_events_store_time", "events", ["store_id", "timestamp"])
    op.create_index("ix_events_store_type_time", "events", ["store_id", "event_type", "timestamp"])
    op.create_index("ix_events_visitor", "events", ["visitor_id"])
    op.create_index("ix_events_event_id", "events", ["event_id"])

    # 3. pos_transactions
    op.create_table(
        "pos_transactions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("store_id", sa.String(50), nullable=False),
        sa.Column("transaction_id", sa.String(100), nullable=False, unique=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("basket_value_inr", sa.Float, nullable=True),
        sa.Column(
            "visitor_session_id",
            sa.String(36),
            sa.ForeignKey("visitor_sessions.session_id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=func.now(),
        ),
    )
    op.create_index("ix_pos_store_time", "pos_transactions", ["store_id", "timestamp"])

    # 4. anomaly_log
    op.create_table(
        "anomaly_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("store_id", sa.String(50), nullable=False),
        sa.Column("anomaly_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("details", sa.JSON, nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=func.now(),
        ),
    )
    op.create_index("ix_anomaly_store_time", "anomaly_log", ["store_id", "detected_at"])


def downgrade() -> None:
    op.drop_table("anomaly_log")
    op.drop_table("pos_transactions")
    op.drop_table("events")
    op.drop_table("visitor_sessions")
