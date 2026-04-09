"""Power of Three: Asian session manipulation detection.

Accumulation (Asian range) -> Manipulation (sweep) -> Distribution (directional move).
"""
from __future__ import annotations

import pandas as pd
from analysis.sessions import get_session_range


def detect_asian_manipulation(df_1h: pd.DataFrame, df_15m: pd.DataFrame,
                              date: pd.Timestamp) -> dict:
    """Detect if Asian session high/low was swept during London kill zone.

    Returns: {manipulation: bullish/bearish/neutral, detail: str}
    """
    result = {"manipulation": "neutral", "detail": "No Asian sweep detected"}

    # Get Asian session range
    asian = get_session_range(df_1h, "asian", date)
    if not asian:
        # Try with 15m data
        asian = get_session_range(df_15m, "asian", date)
    if not asian:
        return result

    # Check London session for sweeps of Asian levels
    london = get_session_range(df_15m, "london", date)
    if not london:
        london = get_session_range(df_1h, "london", date)

    # Also check NY session
    ny = get_session_range(df_15m, "new_york", date)
    if not ny:
        ny = get_session_range(df_1h, "new_york", date)

    asian_high = asian["high"]
    asian_low = asian["low"]

    asian_high_swept = False
    asian_low_swept = False

    # Check London candles for sweeps
    if london:
        if london["high"] > asian_high:
            asian_high_swept = True
        if london["low"] < asian_low:
            asian_low_swept = True

    # Also check early NY if London didn't sweep
    if ny and not (asian_high_swept or asian_low_swept):
        if ny["high"] > asian_high:
            asian_high_swept = True
        if ny["low"] < asian_low:
            asian_low_swept = True

    if asian_low_swept and not asian_high_swept:
        result = {
            "manipulation": "bullish",
            "detail": f"Asian low ({asian_low:.5f}) swept — expect bullish distribution",
        }
    elif asian_high_swept and not asian_low_swept:
        result = {
            "manipulation": "bearish",
            "detail": f"Asian high ({asian_high:.5f}) swept — expect bearish distribution",
        }
    elif asian_high_swept and asian_low_swept:
        # Both swept — determine direction from where price ended up
        ref_session = london or ny
        if ref_session:
            if ref_session["close"] > asian["close"]:
                result = {"manipulation": "bullish",
                          "detail": "Both Asian levels swept, price closed bullish"}
            else:
                result = {"manipulation": "bearish",
                          "detail": "Both Asian levels swept, price closed bearish"}

    return result
