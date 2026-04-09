"""Kill zone and session timing utilities."""

from __future__ import annotations

import pandas as pd
from datetime import time as dtime
from typing import Optional
from config import SESSIONS


def get_session_range(df_intraday: pd.DataFrame, session_name: str,
                      date: pd.Timestamp) -> Optional[dict]:
    """Extract the high/low/open/close of a given session on a given date.

    Handles the Asian session crossing midnight (19:00 prev day to 02:00).
    """
    if df_intraday.empty or session_name not in SESSIONS:
        return None

    session = SESSIONS[session_name]
    start_str = session["start"]
    end_str = session["end"]
    start_time = dtime(int(start_str[:2]), int(start_str[3:]))
    end_time = dtime(int(end_str[:2]), int(end_str[3:]))

    df = df_intraday.copy()
    # Ensure datetime is timezone-aware and convert to America/New_York
    try:
        if df["datetime"].dt.tz is None:
            df["datetime"] = df["datetime"].dt.tz_localize("UTC")
        df["datetime_est"] = df["datetime"].dt.tz_convert("America/New_York")
    except Exception:
        # Fallback: use UTC times directly (offset by -4 or -5 hours won't apply)
        df["datetime_est"] = df["datetime"]
    df["time_est"] = df["datetime_est"].dt.time
    df["date_est"] = df["datetime_est"].dt.date

    target_date = pd.Timestamp(date).date() if not isinstance(date, pd.Timestamp) else date.date()

    if start_time > end_time:
        # Session crosses midnight (e.g., Asian: 19:00 prev day to 02:00)
        from datetime import timedelta
        prev_date = target_date - timedelta(days=1)
        mask = (
            ((df["date_est"] == prev_date) & (df["time_est"] >= start_time)) |
            ((df["date_est"] == target_date) & (df["time_est"] <= end_time))
        )
    else:
        mask = (
            (df["date_est"] == target_date) &
            (df["time_est"] >= start_time) &
            (df["time_est"] <= end_time)
        )

    session_candles = df[mask]
    if session_candles.empty:
        return None

    return {
        "high": float(session_candles["high"].max()),
        "low": float(session_candles["low"].min()),
        "open": float(session_candles.iloc[0]["open"]),
        "close": float(session_candles.iloc[-1]["close"]),
        "session": session_name,
        "date": str(target_date),
    }
