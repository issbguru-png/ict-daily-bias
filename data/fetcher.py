"""Unified data fetcher — tries Twelve Data first, falls back to yfinance."""

from typing import Optional, Dict, Tuple
import pandas as pd
from data import twelvedata_provider as td
from data import yfinance_provider as yf

# In-memory cache: {(symbol, interval): (timestamp, DataFrame)}
_cache: Dict[Tuple, Tuple] = {}
_CACHE_TTL = 1800  # 30 minutes


def _cache_key(symbol: str, interval: str) -> Tuple:
    return (symbol, interval)


def _from_cache(symbol: str, interval: str) -> Optional[pd.DataFrame]:
    import time
    key = _cache_key(symbol, interval)
    if key in _cache:
        ts, df = _cache[key]
        if time.time() - ts < _CACHE_TTL:
            return df
    return None


def _to_cache(symbol: str, interval: str, df: pd.DataFrame):
    import time
    _cache[_cache_key(symbol, interval)] = (time.time(), df)


def get_daily(symbol: str, bars: int = 60) -> pd.DataFrame:
    cached = _from_cache(symbol, "1day")
    if cached is not None:
        return cached
    # Use yfinance for daily to save Twelve Data quota
    df = yf.fetch_daily(symbol, bars)
    if df.empty and td.is_available():
        df = td.fetch_daily(symbol, bars)
    if not df.empty:
        _to_cache(symbol, "1day", df)
    return df


def get_hourly(symbol: str, bars: int = 120) -> pd.DataFrame:
    cached = _from_cache(symbol, "1h")
    if cached is not None:
        return cached
    # Prefer Twelve Data for intraday
    df = pd.DataFrame()
    if td.is_available():
        df = td.fetch_hourly(symbol, bars)
    if df.empty:
        df = yf.fetch_hourly(symbol)
    if not df.empty:
        _to_cache(symbol, "1h", df)
    return df


def get_15min(symbol: str, bars: int = 200) -> pd.DataFrame:
    cached = _from_cache(symbol, "15min")
    if cached is not None:
        return cached
    df = pd.DataFrame()
    if td.is_available():
        df = td.fetch_15min(symbol, bars)
    if df.empty:
        df = yf.fetch_15min(symbol)
    if not df.empty:
        _to_cache(symbol, "15min", df)
    return df


def clear_cache():
    _cache.clear()
