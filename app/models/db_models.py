# You are writing the SQLAlchemy ORM models for a retail store CCTV analytics API.

# FILE: app/models/db_models.py
# PURPOSE: Define all database tables as SQLAlchemy ORM classes using the shared Base
# from app.database. Also create an __init__.py that imports all models (needed for
# Alembic autogenerate to detect them).

# TECH: Python 3.11, sqlalchemy==2.0.36, sqlalchemy dialects (postgresql JSONB, UUID)

# IMPLEMENT THE FOLLOWING TABLES:

# 1. `class Event(Base):`
#    __tablename__ = "events"
#    - id: Integer, primary key, autoincrement
#    - event_id: String(36), unique, not null, index  # UUID v4 string
#    - store_id: String(50), not null, index
#    - camera_id: String(50), not null
#    - visitor_id: String(20), not null, index
#    - event_type: String(30), not null, index
#    - timestamp: DateTime(timezone=True), not null, index
#    - zone_id: String(50), nullable
#    - dwell_ms: Integer, default=0
#    - is_staff: Boolean, default=False, not null
#    - confidence: Float, not null
#    - metadata_json: JSON (column named "metadata"), nullable  # JSONB in postgres
#    - created_at: DateTime(timezone=True), server_default=func.now()
#    Add index on (store_id, timestamp) named "ix_events_store_time".
#    Add index on (store_id, event_type, timestamp) named "ix_events_store_type_time".

# 2. `class VisitorSession(Base):`
#    __tablename__ = "visitor_sessions"
#    - id: Integer, primary key, autoincrement
#    - session_id: String(36), unique, not null, index  # UUID v4
#    - store_id: String(50), not null, index
#    - visitor_id: String(20), not null, index
#    - entry_timestamp: DateTime(timezone=True), nullable
#    - exit_timestamp: DateTime(timezone=True), nullable
#    - is_reentry: Boolean, default=False
#    - is_converted: Boolean, default=False
#    - is_staff: Boolean, default=False
#    - zones_visited: JSON, nullable  # list of zone_ids
#    - total_dwell_ms: Integer, default=0
#    - created_at: DateTime(timezone=True), server_default=func.now()
#    - updated_at: DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
#    Add index on (store_id, entry_timestamp) named "ix_sessions_store_entry".

# 3. `class POSTransaction(Base):`
#    __tablename__ = "pos_transactions"
#    - id: Integer, primary key, autoincrement
#    - store_id: String(50), not null, index
#    - transaction_id: String(100), unique, not null
#    - timestamp: DateTime(timezone=True), not null, index
#    - basket_value_inr: Float, nullable
#    - visitor_session_id: String(36), nullable, ForeignKey("visitor_sessions.session_id")
#    - created_at: DateTime(timezone=True), server_default=func.now()

# 4. `class AnomalyLog(Base):`
#    __tablename__ = "anomaly_log"
#    - id: Integer, primary key, autoincrement
#    - store_id: String(50), not null, index
#    - anomaly_type: String(50), not null
#    - severity: String(10), not null  # INFO / WARN / CRITICAL
#    - details: JSON, nullable
#    - detected_at: DateTime(timezone=True), not null
#    - resolved_at: DateTime(timezone=True), nullable
#    - created_at: DateTime(timezone=True), server_default=func.now()
#    Add index on (store_id, detected_at) named "ix_anomaly_store_time".

# IMPORTS NEEDED:
#   sqlalchemy (Column, Integer, String, Boolean, Float, DateTime, JSON, ForeignKey, Index),
#   sqlalchemy.sql (func), app.database (Base)

# Also write the companion file app/models/__init__.py:
#    from app.models.db_models import Event, VisitorSession, POSTransaction, AnomalyLog
#    __all__ = ["Event", "VisitorSession", "POSTransaction", "AnomalyLog"]

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
)
from sqlalchemy.sql import func

from app.database import Base


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(36), unique=True, nullable=False, index=True)
    store_id = Column(String(50), nullable=False, index=True)
    camera_id = Column(String(50), nullable=False)
    visitor_id = Column(String(20), nullable=False, index=True)
    event_type = Column(String(30), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    zone_id = Column(String(50), nullable=True)
    dwell_ms = Column(Integer, default=0)
    is_staff = Column(Boolean, default=False, nullable=False)
    confidence = Column(Float, nullable=False)
    metadata_json = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_events_store_time", "store_id", "timestamp"),
        Index("ix_events_store_type_time", "store_id", "event_type", "timestamp"),
    )


class VisitorSession(Base):
    __tablename__ = "visitor_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), unique=True, nullable=False, index=True)
    store_id = Column(String(50), nullable=False, index=True)
    visitor_id = Column(String(20), nullable=False, index=True)
    entry_timestamp = Column(DateTime(timezone=True), nullable=True)
    exit_timestamp = Column(DateTime(timezone=True), nullable=True)
    is_reentry = Column(Boolean, default=False)
    is_converted = Column(Boolean, default=False)
    is_staff = Column(Boolean, default=False)
    zones_visited = Column(JSON, nullable=True)
    total_dwell_ms = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("ix_sessions_store_entry", "store_id", "entry_timestamp"),
    )


class POSTransaction(Base):
    __tablename__ = "pos_transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    store_id = Column(String(50), nullable=False, index=True)
    transaction_id = Column(String(100), unique=True, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    basket_value_inr = Column(Float, nullable=True)
    visitor_session_id = Column(
        String(36),
        ForeignKey("visitor_sessions.session_id"),
        nullable=True,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AnomalyLog(Base):
    __tablename__ = "anomaly_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    store_id = Column(String(50), nullable=False, index=True)
    anomaly_type = Column(String(50), nullable=False)
    severity = Column(String(10), nullable=False)
    details = Column(JSON, nullable=True)
    detected_at = Column(DateTime(timezone=True), nullable=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_anomaly_store_time", "store_id", "detected_at"),
    )
