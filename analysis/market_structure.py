"""Market structure classification: HH/HL/LH/LL and structure shifts."""
from __future__ import annotations

import pandas as pd


def classify_structure(swing_highs: list[dict], swing_lows: list[dict]) -> dict:
    """Classify market structure from swing points.

    Returns dict with 'structure' (bullish/bearish/ranging), 'labels' list,
    and 'last_swing_high'/'last_swing_low'.
    """
    labels = []

    # Label consecutive swing highs
    for i in range(1, len(swing_highs)):
        prev = swing_highs[i - 1]
        curr = swing_highs[i]
        label = "HH" if curr["price"] > prev["price"] else "LH"
        labels.append({"type": "high", "label": label, **curr})

    # Label consecutive swing lows
    for i in range(1, len(swing_lows)):
        prev = swing_lows[i - 1]
        curr = swing_lows[i]
        label = "HL" if curr["price"] > prev["price"] else "LL"
        labels.append({"type": "low", "label": label, **curr})

    labels.sort(key=lambda x: x["time"])

    # Determine structure from recent labels (last 4)
    recent = labels[-4:] if len(labels) >= 4 else labels
    high_labels = [l["label"] for l in recent if l["type"] == "high"]
    low_labels = [l["label"] for l in recent if l["type"] == "low"]

    bullish_highs = high_labels.count("HH") >= high_labels.count("LH")
    bullish_lows = low_labels.count("HL") >= low_labels.count("LL")
    bearish_highs = high_labels.count("LH") >= high_labels.count("HH")
    bearish_lows = low_labels.count("LL") >= low_labels.count("HL")

    if bullish_highs and bullish_lows:
        structure = "bullish"
    elif bearish_highs and bearish_lows:
        structure = "bearish"
    else:
        structure = "ranging"

    return {
        "structure": structure,
        "labels": labels,
        "last_swing_high": swing_highs[-1] if swing_highs else None,
        "last_swing_low": swing_lows[-1] if swing_lows else None,
    }


def detect_structure_break(df: pd.DataFrame, structure: str,
                           last_swing_high: dict | None,
                           last_swing_low: dict | None) -> dict:
    """Detect Break of Structure (BOS) or Market Structure Shift (MSS).

    BOS = continuation (price breaks in trend direction).
    MSS = reversal (price breaks against trend direction).
    """
    if df.empty:
        return {"type": None, "detail": "Insufficient data"}

    current_close = float(df.iloc[-1]["close"])
    result = {"type": None, "detail": "No break detected"}

    if structure == "bullish" and last_swing_high and last_swing_low:
        if current_close > last_swing_high["price"]:
            result = {"type": "BOS_bullish", "detail": f"Price closed above swing high {last_swing_high['price']:.5f}"}
        elif current_close < last_swing_low["price"]:
            result = {"type": "MSS_bearish", "detail": f"Price closed below swing low {last_swing_low['price']:.5f}"}

    elif structure == "bearish" and last_swing_high and last_swing_low:
        if current_close < last_swing_low["price"]:
            result = {"type": "BOS_bearish", "detail": f"Price closed below swing low {last_swing_low['price']:.5f}"}
        elif current_close > last_swing_high["price"]:
            result = {"type": "MSS_bullish", "detail": f"Price closed above swing high {last_swing_high['price']:.5f}"}

    return result
