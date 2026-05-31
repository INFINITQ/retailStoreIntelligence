# You are building the POS transaction correlator for a retail store CCTV analytics pipeline.

# FILE: pipeline/pos_correlator.py
# PURPOSE: Load the POS transactions CSV, and for each transaction determine which visitor
# sessions were in the billing zone in the 5-minute window before the transaction timestamp.
# Those sessions are marked as "converted". Also detect BILLING_QUEUE_ABANDON events.

# TECH: Python 3.11, pandas==2.2.3, datetime, typing

# CONTEXT:
# - POS CSV columns include: order_id, order_date (DD-MM-YYYY), order_time (HH:MM:SS),
#   store_id (real ID like "ST1008"), and total_amount.
# - store_mapping.json maps "ST1008" → "STORE_BLR_002" (api_store_id).
# - A visitor session is "converted" if their visitor_id had a BILLING or BILLING_QUEUE
#   event within 5 minutes before a transaction at the same store.
# - BILLING_QUEUE_ABANDON: visitor had a BILLING_QUEUE_JOIN event but no POS transaction
#   followed within 15 minutes AND they emitted a subsequent EXIT.

# IMPLEMENT THE FOLLOWING:

# 1. `class POSCorrelator:`

#    `__init__(self, csv_path: str, store_mapping: dict,
#              correlation_window_minutes: int = 5):`
#    - Load the CSV with pandas. Handle the date format "DD-MM-YYYY".
#    - Create a `transaction_timestamp` column: combine order_date + order_time → UTC datetime.
#    - Filter to only rows matching the api_store_id derived from store_mapping.
#    - Deduplicate by order_id (keep first row per order since CSV has one row per item).
#    - `self.transactions: pd.DataFrame` — deduplicated transactions sorted by timestamp.
#    - `self.correlation_window = timedelta(minutes=correlation_window_minutes)`
#    - `self.abandon_window = timedelta(minutes=15)`

#    `build_billing_timeline(self, events: list[dict]) -> dict:`
#    - events: list of event dicts emitted by the pipeline (all types).
#    - Build and return a dict:
#      {
#        "billing_intervals": list of {"visitor_id": str, "enter_ts": datetime, "exit_ts": datetime|None},
#        "queue_joins": list of {"visitor_id": str, "join_ts": datetime}
#      }
#    - Derive billing_intervals from BILLING_QUEUE_JOIN and subsequent EXIT/ZONE_EXIT events.

#    `find_converted_sessions(self, billing_timeline: dict) -> set[str]:`
#    - For each transaction in self.transactions:
#      - Find all billing_intervals where the visitor's billing window overlaps
#        the 5 minutes before transaction_timestamp.
#      - Add those visitor_ids to the converted set.
#    - Return set of converted visitor_ids.

#    `find_abandoned_sessions(self, billing_timeline: dict,
#                              converted_visitor_ids: set[str]) -> list[str]:`
#    - For each queue_join not in converted_visitor_ids:
#      - Check if that visitor exited within abandon_window.
#      - If yes: classify as BILLING_QUEUE_ABANDON.
#    - Return list of visitor_ids who abandoned.

#    `get_transaction_count(self) -> int:`
#    - Returns len(self.transactions).

# 2. Standalone helper:
#    `parse_pos_timestamp(date_str: str, time_str: str) -> datetime:`
#    - Parse "10-04-2026" + "16:55:36" → timezone-aware UTC datetime.
#    - date_str format: DD-MM-YYYY. Assume IST (UTC+5:30), convert to UTC.

# IMPORTS NEEDED: pandas as pd, datetime (datetime, timedelta, timezone),
# typing (Optional), json, os
