# You are writing the first Alembic migration for a retail store CCTV analytics API.

# FILE: migrations/versions/001_initial_schema.py
# PURPOSE: Creates all four database tables in a single migration: events, visitor_sessions,
# pos_transactions, anomaly_log. Includes all indexes.

# TECH: Python 3.11, alembic==1.14.0, sqlalchemy

# IMPLEMENT a standard Alembic migration file with:

# revision = "001_initial"
# down_revision = None
# branch_labels = None
# depends_on = None

# `def upgrade() -> None:`
# Create tables in this order (respecting FK dependencies):

# 1. visitor_sessions:
#    - id: INTEGER, PK, autoincrement
#    - session_id: VARCHAR(36), NOT NULL, UNIQUE
#    - store_id: VARCHAR(50), NOT NULL
#    - visitor_id: VARCHAR(20), NOT NULL
#    - entry_timestamp: TIMESTAMP WITH TIME ZONE
#    - exit_timestamp: TIMESTAMP WITH TIME ZONE
#    - is_reentry: BOOLEAN, DEFAULT FALSE, NOT NULL
#    - is_converted: BOOLEAN, DEFAULT FALSE, NOT NULL
#    - is_staff: BOOLEAN, DEFAULT FALSE, NOT NULL
#    - zones_visited: JSON
#    - total_dwell_ms: INTEGER, DEFAULT 0
#    - created_at: TIMESTAMP WITH TIME ZONE, server_default=func.now()
#    - updated_at: TIMESTAMP WITH TIME ZONE, server_default=func.now()
#    Index: ix_sessions_store_entry ON (store_id, entry_timestamp)
#    Index: ix_sessions_visitor ON (visitor_id, store_id)

# 2. events:
#    - id: INTEGER, PK, autoincrement
#    - event_id: VARCHAR(36), NOT NULL, UNIQUE
#    - store_id: VARCHAR(50), NOT NULL
#    - camera_id: VARCHAR(50), NOT NULL
#    - visitor_id: VARCHAR(20), NOT NULL
#    - event_type: VARCHAR(30), NOT NULL
#    - timestamp: TIMESTAMP WITH TIME ZONE, NOT NULL
#    - zone_id: VARCHAR(50)
#    - dwell_ms: INTEGER, DEFAULT 0
#    - is_staff: BOOLEAN, DEFAULT FALSE, NOT NULL
#    - confidence: FLOAT, NOT NULL
#    - metadata: JSON
#    - created_at: TIMESTAMP WITH TIME ZONE, server_default=func.now()
#    Indexes: ix_events_store_time ON (store_id, timestamp),
#             ix_events_store_type_time ON (store_id, event_type, timestamp),
#             ix_events_visitor ON (visitor_id)

# 3. pos_transactions:
#    - id: INTEGER, PK, autoincrement
#    - store_id: VARCHAR(50), NOT NULL
#    - transaction_id: VARCHAR(100), NOT NULL, UNIQUE
#    - timestamp: TIMESTAMP WITH TIME ZONE, NOT NULL
#    - basket_value_inr: FLOAT
#    - visitor_session_id: VARCHAR(36), FK to visitor_sessions.session_id, nullable
#    - created_at: TIMESTAMP WITH TIME ZONE, server_default=func.now()
#    Index: ix_pos_store_time ON (store_id, timestamp)

# 4. anomaly_log:
#    - id: INTEGER, PK, autoincrement
#    - store_id: VARCHAR(50), NOT NULL
#    - anomaly_type: VARCHAR(50), NOT NULL
#    - severity: VARCHAR(10), NOT NULL
#    - details: JSON
#    - detected_at: TIMESTAMP WITH TIME ZONE, NOT NULL
#    - resolved_at: TIMESTAMP WITH TIME ZONE
#    - created_at: TIMESTAMP WITH TIME ZONE, server_default=func.now()
#    Index: ix_anomaly_store_time ON (store_id, detected_at)

# `def downgrade() -> None:`
# Drop tables in reverse order: anomaly_log, pos_transactions, events, visitor_sessions.

# IMPORTS NEEDED: alembic.op (as op), sqlalchemy (Column, Integer, String, Boolean,
# Float, DateTime, JSON, ForeignKey, func, text), sqlalchemy.sql (func)
