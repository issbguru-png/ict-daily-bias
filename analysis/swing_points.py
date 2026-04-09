"""N-bar swing high/low detection algorithm."""
from __future__ import annotations

import pandas as pd


def detect_swing_highs(df: pd.DataFrame, lookback: int = 3) -> list[dict]:
    """Detect swing highs: candle high > highs of N candles on each side."""
    swings = []
    highs = df["high"].values
    n = len(highs)
    for i in range(lookback, n - lookback):
        candle_high = highs[i]
        left = highs[i - lookback:i]
        right = highs[i + 1:i + 1 + lookback]
        if candle_high > left.max() and candle_high > right.max():
            swings.append({
                "index": i,
                "price": float(candle_high),
                "time": df.iloc[i]["datetime"],
            })
    return swings


def detect_swing_lows(df: pd.DataFrame, lookback: int = 3) -> list[dict]:
    """Detect swing lows: candle low < lows of N candles on each side."""
    swings = []
    lows = df["low"].values
    n = len(lows)
    for i in range(lookback, n - lookback):
        candle_low = lows[i]
        left = lows[i - lookback:i]
        right = lows[i + 1:i + 1 + lookback]
        if candle_low < left.min() and candle_low < right.min():
            swings.append({
                "index": i,
                "price": float(candle_low),
                "time": df.iloc[i]["datetime"],
            })
    return swings
