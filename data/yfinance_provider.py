"""Data provider using yfinance (no API key required)."""

import pandas as pd
import yfinance as yf
from config import YFINANCE_SYMBOLS


def _map_symbol(symbol: str) -> str:
    mapped = YFINANCE_SYMBOLS.get(symbol)
    if not mapped:
        raise ValueError(f"No yfinance mapping for {symbol}")
    return mapped


def fetch_daily(symbol: str, days: int = 60) -> pd.DataFrame:
    ticker = _map_symbol(symbol)
    df = yf.download(ticker, period=f"{days}d", interval="1d", progress=False, auto_adjust=True)
    if df.empty:
        return pd.DataFrame()
    return _normalize(df)


def fetch_hourly(symbol: str, days: int = 5) -> pd.DataFrame:
    ticker = _map_symbol(symbol)
    df = yf.download(ticker, period=f"{days}d", interval="1h", progress=False, auto_adjust=True)
    if df.empty:
        return pd.DataFrame()
    return _normalize(df)


def fetch_15min(symbol: str, days: int = 5) -> pd.DataFrame:
    ticker = _map_symbol(symbol)
    df = yf.download(ticker, period=f"{days}d", interval="15m", progress=False, auto_adjust=True)
    if df.empty:
        return pd.DataFrame()
    return _normalize(df)


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.reset_index()
    # Handle multi-level columns from yfinance v1.2+
    if isinstance(df.columns, pd.MultiIndex):
        # Take only the first level (Price name), drop the Ticker level
        df.columns = [col[0] for col in df.columns]
    # Standardize column names to lowercase
    df.columns = [c.lower() if isinstance(c, str) else c for c in df.columns]
    # Rename date/index columns
    if "date" in df.columns:
        df = df.rename(columns={"date": "datetime"})
    elif "index" in df.columns:
        df = df.rename(columns={"index": "datetime"})
    # Handle 'price' prefix that some yfinance versions add
    col_map = {}
    for c in df.columns:
        if c.startswith("price"):
            col_map[c] = c.replace("price", "").strip()
    if col_map:
        df = df.rename(columns=col_map)
    required = ["datetime", "open", "high", "low", "close"]
    for col in required:
        if col not in df.columns:
            return pd.DataFrame()
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["open", "high", "low", "close"])
    df = df.sort_values("datetime").reset_index(drop=True)
    return df[required + (["volume"] if "volume" in df.columns else [])]
