"""Data provider using Twelve Data API (free tier: 800 calls/day)."""

import time
import requests
import pandas as pd
from config import TWELVE_DATA_API_KEY, TWELVE_DATA_BASE_URL

# Rate limit: max 8 calls/minute on free tier
_last_call_time = 0.0
_MIN_INTERVAL = 8.0  # seconds between calls to stay under 8/min


def _rate_limit():
    global _last_call_time
    elapsed = time.time() - _last_call_time
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    _last_call_time = time.time()


def is_available() -> bool:
    return bool(TWELVE_DATA_API_KEY)


def _fetch(symbol: str, interval: str, outputsize: int) -> pd.DataFrame:
    if not TWELVE_DATA_API_KEY:
        return pd.DataFrame()
    _rate_limit()
    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": outputsize,
        "apikey": TWELVE_DATA_API_KEY,
    }
    try:
        resp = requests.get(f"{TWELVE_DATA_BASE_URL}/time_series", params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return pd.DataFrame()

    if "values" not in data:
        return pd.DataFrame()

    rows = data["values"]
    df = pd.DataFrame(rows)
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    if "volume" in df.columns:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
    df = df.dropna(subset=["open", "high", "low", "close"])
    df = df.sort_values("datetime").reset_index(drop=True)
    cols = ["datetime", "open", "high", "low", "close"]
    if "volume" in df.columns:
        cols.append("volume")
    return df[cols]


def fetch_daily(symbol: str, bars: int = 60) -> pd.DataFrame:
    return _fetch(symbol, "1day", bars)


def fetch_hourly(symbol: str, bars: int = 120) -> pd.DataFrame:
    return _fetch(symbol, "1h", bars)


def fetch_15min(symbol: str, bars: int = 200) -> pd.DataFrame:
    return _fetch(symbol, "15min", bars)
