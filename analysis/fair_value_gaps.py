"""Fair Value Gap (FVG) detection — 3-candle imbalance pattern."""
from __future__ import annotations

import pandas as pd


def detect_fvgs(df: pd.DataFrame) -> list[dict]:
    """Detect bullish and bearish FVGs and track fill status."""
    fvgs = []
    n = len(df)
    if n < 3:
        return fvgs

    opens = df["open"].values
    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values
    times = df["datetime"].values

    for i in range(2, n):
        c1_high = highs[i - 2]
        c1_low = lows[i - 2]
        c3_high = highs[i]
        c3_low = lows[i]

        # Bullish FVG: gap between c1 high and c3 low (c3 low > c1 high)
        if c3_low > c1_high:
            fvgs.append({
                "type": "bullish",
                "top": float(c3_low),
                "bottom": float(c1_high),
                "midpoint": float((c3_low + c1_high) / 2),
                "time": times[i - 1],  # impulse candle time
                "index": i - 1,
                "filled": False,
            })

        # Bearish FVG: gap between c3 high and c1 low (c3 high < c1 low)
        if c3_high < c1_low:
            fvgs.append({
                "type": "bearish",
                "top": float(c1_low),
                "bottom": float(c3_high),
                "midpoint": float((c1_low + c3_high) / 2),
                "time": times[i - 1],
                "index": i - 1,
                "filled": False,
            })

    # Check fill status
    for fvg in fvgs:
        start_idx = fvg["index"] + 2  # candles after the FVG formed
        if start_idx >= n:
            continue
        subsequent_lows = lows[start_idx:]
        subsequent_highs = highs[start_idx:]
        if fvg["type"] == "bullish" and len(subsequent_lows) > 0:
            if subsequent_lows.min() <= fvg["bottom"]:
                fvg["filled"] = True
        elif fvg["type"] == "bearish" and len(subsequent_highs) > 0:
            if subsequent_highs.max() >= fvg["top"]:
                fvg["filled"] = True

    return fvgs


def get_unfilled_fvgs(fvgs: list[dict]) -> list[dict]:
    """Return only unfilled FVGs."""
    return [f for f in fvgs if not f["filled"]]
