# You are building the POS transaction correlator for a retail store CCTV analytics pipeline.

# FILE: pipeline/pos_correlator.py

from datetime import datetime, timedelta, timezone
from typing import Optional

import pandas as pd


IST_OFFSET = timedelta(hours=5, minutes=30)


def parse_pos_timestamp(date_str: str, time_str: str) -> datetime:
    """Parse 'DD-MM-YYYY' + 'HH:MM:SS' in IST → UTC datetime."""
    combined = f"{date_str} {time_str}"
    dt = datetime.strptime(combined, "%d-%m-%Y %H:%M:%S")
    ist_dt = dt.replace(tzinfo=timezone(IST_OFFSET))
    return ist_dt.astimezone(timezone.utc)


class POSCorrelator:
    def __init__(
        self,
        csv_path: str,
        store_mapping: dict,
        correlation_window_minutes: int = 5,
    ) -> None:
        self.correlation_window = timedelta(minutes=correlation_window_minutes)
        self.abandon_window = timedelta(minutes=15)

        # Resolve api_store_id from mapping
        api_store_id = None
        for store in store_mapping.get("stores", []):
            api_store_id = store.get("api_store_id")
            break

        # Load CSV
        try:
            df = pd.read_csv(csv_path, dtype=str)
        except FileNotFoundError:
            self.transactions = pd.DataFrame()
            return

        # Detect date/time columns flexibly
        date_col = self._find_col(df, ["order_date", "date"])
        time_col = self._find_col(df, ["order_time", "time"])
        id_col = self._find_col(df, ["order_id", "transaction_id"])
        store_col = self._find_col(df, ["store_id"])
        amount_col = self._find_col(df, ["total_amount", "basket_value_inr", "amount"])

        if date_col and time_col:
            df["transaction_timestamp"] = df.apply(
                lambda r: parse_pos_timestamp(r[date_col], r[time_col]), axis=1
            )
        else:
            self.transactions = pd.DataFrame()
            return

        # Filter to this store
        if store_col and api_store_id:
            pos_ref = None
            for store in store_mapping.get("stores", []):
                pos_ref = store.get("pos_store_id")
                break
            if pos_ref:
                df = df[df[store_col] == pos_ref]

        # Deduplicate by order_id
        if id_col:
            df = df.drop_duplicates(subset=[id_col], keep="first")

        df = df.sort_values("transaction_timestamp").reset_index(drop=True)
        self.transactions = df
        self._amount_col = amount_col
        self._id_col = id_col

    @staticmethod
    def _find_col(df: pd.DataFrame, candidates: list[str]) -> Optional[str]:
        for c in candidates:
            for col in df.columns:
                if col.lower().strip() == c.lower():
                    return col
        return None

    def build_billing_timeline(self, events: list[dict]) -> dict:
        """Build billing_intervals and queue_joins from emitted events."""
        billing_intervals = []
        queue_joins = []
        open_billing: dict[str, datetime] = {}

        # Sort by timestamp
        def _parse(ts: str) -> datetime:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))

        for evt in sorted(events, key=lambda e: e.get("timestamp", "")):
            etype = evt.get("event_type", "")
            vid = evt.get("visitor_id", "")
            ts_str = evt.get("timestamp", "")
            if not ts_str:
                continue
            ts = _parse(ts_str)

            if etype in ("BILLING_QUEUE_JOIN",):
                open_billing[vid] = ts
                queue_joins.append({"visitor_id": vid, "join_ts": ts})

            elif etype in ("EXIT", "ZONE_EXIT") and vid in open_billing:
                enter_ts = open_billing.pop(vid)
                billing_intervals.append({
                    "visitor_id": vid,
                    "enter_ts": enter_ts,
                    "exit_ts": ts,
                })

        # Close any still-open intervals (never exited)
        for vid, enter_ts in open_billing.items():
            billing_intervals.append({
                "visitor_id": vid,
                "enter_ts": enter_ts,
                "exit_ts": None,
            })

        return {"billing_intervals": billing_intervals, "queue_joins": queue_joins}

    def find_converted_sessions(self, billing_timeline: dict) -> set[str]:
        """Visitors whose billing window overlaps the 5-min pre-transaction window."""
        converted: set[str] = set()
        intervals = billing_timeline.get("billing_intervals", [])

        if self.transactions.empty:
            return converted

        for _, txn in self.transactions.iterrows():
            txn_ts: datetime = txn["transaction_timestamp"]
            window_start = txn_ts - self.correlation_window

            for interval in intervals:
                enter: datetime = interval["enter_ts"]
                exit_ts: Optional[datetime] = interval["exit_ts"]

                # Check overlap: billing window ∩ [window_start, txn_ts]
                billing_end = exit_ts if exit_ts else txn_ts
                if enter <= txn_ts and billing_end >= window_start:
                    converted.add(interval["visitor_id"])

        return converted

    def find_abandoned_sessions(
        self, billing_timeline: dict, converted_visitor_ids: set[str]
    ) -> list[str]:
        """Visitors who joined queue but didn't convert within abandon_window."""
        abandoned: list[str] = []
        intervals = billing_timeline.get("billing_intervals", [])

        for interval in intervals:
            vid = interval["visitor_id"]
            if vid in converted_visitor_ids:
                continue
            exit_ts = interval.get("exit_ts")
            if exit_ts is None:
                continue  # never left — can't confirm abandonment
            enter_ts = interval["enter_ts"]
            if (exit_ts - enter_ts) <= self.abandon_window:
                abandoned.append(vid)

        return abandoned

    def get_transaction_count(self) -> int:
        return len(self.transactions)
