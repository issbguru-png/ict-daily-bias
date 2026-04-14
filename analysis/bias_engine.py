"""Master bias engine — based on ICT Daily Bias Trick article.

Rules (from https://innercircletrader.net/tutorials/ict-daily-bias-trick/):

Bullish bias:
  1. Price shifts structure to buy-side on the daily chart (closes above a prior swing high)
  2. Structure must NOT have shifted back to sell-side after that
  3. Bias remains bullish until daily structure shifts to sell-side

Bearish bias (mirror):
  1. Price shifts structure to sell-side on the daily chart (closes below a prior swing low)
  2. Structure must NOT have shifted back to buy-side after that
  3. Bias remains bearish until daily structure shifts to buy-side
"""
from __future__ import annotations

import pandas as pd
from datetime import datetime, timezone

from config import DAILY_SWING_LOOKBACK
from analysis.swing_points import detect_swing_highs, detect_swing_lows


def determine_bias(symbol: str, daily_df: pd.DataFrame,
                   h1_df: pd.DataFrame, m15_df: pd.DataFrame) -> dict:
    """Determine daily bias using ICT Daily Bias Trick methodology.

    Simple rule: track the most recent daily structure shift.
    - Latest shift was to buy-side → Bullish
    - Latest shift was to sell-side → Bearish
    - No shift detected → Neutral
    """
    if daily_df.empty or len(daily_df) < 10:
        return _empty_result(symbol, "Insufficient daily data")

    current_price = float(daily_df.iloc[-1]["close"])

    # Detect all swing points on the daily chart
    swing_highs = detect_swing_highs(daily_df, lookback=DAILY_SWING_LOOKBACK)
    swing_lows = detect_swing_lows(daily_df, lookback=DAILY_SWING_LOOKBACK)

    # Find the most recent structure shift
    shift = _find_last_structure_shift(daily_df, swing_highs, swing_lows)

    # Check if structure is still preserved (not invalidated by a later opposing shift)
    still_preserved = _is_structure_preserved(daily_df, shift, swing_highs, swing_lows)

    # Determine bias based on the shift
    if shift["direction"] == "bullish" and still_preserved:
        bias = "Bullish"
        detail = f"Structure shifted to buy-side ({shift['detail']})"
    elif shift["direction"] == "bearish" and still_preserved:
        bias = "Bearish"
        detail = f"Structure shifted to sell-side ({shift['detail']})"
    elif shift["direction"] in ("bullish", "bearish") and not still_preserved:
        bias = "Neutral"
        detail = f"Last shift was {shift['direction']} but structure has since been invalidated"
    else:
        bias = "Neutral"
        detail = "No clear structure shift detected"

    # Confidence = how recent the shift is (more recent = higher confidence)
    confidence = _calculate_confidence(shift, daily_df, still_preserved)

    # Prev day high/low for reference
    pdh = float(daily_df.iloc[-2]["high"]) if len(daily_df) >= 2 else None
    pdl = float(daily_df.iloc[-2]["low"]) if len(daily_df) >= 2 else None

    # Build factors dict (single factor now: structure shift)
    factors = {
        "structure_shift": {
            "signal": shift["direction"] if still_preserved and shift["direction"] != "none" else "neutral",
            "weight": 1.0,
            "score": 1.0 if bias == "Bullish" else -1.0 if bias == "Bearish" else 0.0,
            "detail": detail,
        }
    }

    return {
        "symbol": symbol,
        "bias": bias,
        "confidence": round(confidence, 1),
        "score": 1.0 if bias == "Bullish" else -1.0 if bias == "Bearish" else 0.0,
        "factors": factors,
        "key_levels": {
            "pdh": pdh,
            "pdl": pdl,
            "current_price": current_price,
            "last_swing_high": swing_highs[-1]["price"] if swing_highs else None,
            "last_swing_low": swing_lows[-1]["price"] if swing_lows else None,
            "shift_level": shift.get("level"),
            "order_blocks": [],
            "fvgs": [],
            "dol_target": None,
        },
        "structure": bias.lower() if bias != "Neutral" else "ranging",
        "structure_break": {
            "type": f"MSS_{shift['direction']}" if shift["direction"] != "none" else None,
            "detail": detail,
        },
        "asian_session": {"manipulation": "neutral", "detail": "Not used in simplified method"},
        "swing_highs": [{"price": s["price"], "time": str(s["time"])} for s in swing_highs[-10:]],
        "swing_lows": [{"price": s["price"], "time": str(s["time"])} for s in swing_lows[-10:]],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _find_last_structure_shift(daily_df: pd.DataFrame,
                                swing_highs: list,
                                swing_lows: list) -> dict:
    """Find the most recent structure shift on the daily chart.

    A bullish shift = a candle closed above a previous swing high.
    A bearish shift = a candle closed below a previous swing low.

    Returns the most recent shift with direction, time, index, and level.
    """
    closes = daily_df["close"].values
    times = daily_df["datetime"].values

    last_shift = {"direction": "none", "index": -1, "time": None, "level": None, "detail": ""}

    # Walk through each candle; check if it broke any prior swing high or swing low
    for i in range(len(daily_df)):
        candle_close = closes[i]

        # Check bullish shift: did this candle close above a swing high that formed BEFORE it?
        for sh in swing_highs:
            if sh["index"] < i and candle_close > sh["price"]:
                # This is a bullish shift — but only count the first time it broke this level
                # Only record if more recent than current last_shift
                if i > last_shift["index"]:
                    last_shift = {
                        "direction": "bullish",
                        "index": i,
                        "time": times[i],
                        "level": sh["price"],
                        "detail": f"close {candle_close:.5f} broke swing high {sh['price']:.5f}",
                    }
                break  # move to next candle

        # Check bearish shift: did this candle close below a swing low that formed BEFORE it?
        for sl in swing_lows:
            if sl["index"] < i and candle_close < sl["price"]:
                if i > last_shift["index"]:
                    last_shift = {
                        "direction": "bearish",
                        "index": i,
                        "time": times[i],
                        "level": sl["price"],
                        "detail": f"close {candle_close:.5f} broke swing low {sl['price']:.5f}",
                    }
                break

    return last_shift


def _is_structure_preserved(daily_df: pd.DataFrame, shift: dict,
                             swing_highs: list, swing_lows: list) -> bool:
    """Check that structure has NOT shifted back to the opposite direction after the shift.

    Per the article: 'Preserve Structure — Price must not shift structure to sell-side
    during pullback' (and mirror for bearish).
    """
    if shift["direction"] == "none" or shift["index"] < 0:
        return False

    closes = daily_df["close"].values
    shift_idx = shift["index"]

    if shift["direction"] == "bullish":
        # After the bullish shift, check if any subsequent candle closed below a swing low
        # that formed AFTER the shift (= bearish invalidation)
        for i in range(shift_idx + 1, len(daily_df)):
            candle_close = closes[i]
            for sl in swing_lows:
                if sl["index"] > shift_idx and sl["index"] < i and candle_close < sl["price"]:
                    return False  # Structure was invalidated
        return True

    elif shift["direction"] == "bearish":
        for i in range(shift_idx + 1, len(daily_df)):
            candle_close = closes[i]
            for sh in swing_highs:
                if sh["index"] > shift_idx and sh["index"] < i and candle_close > sh["price"]:
                    return False
        return True

    return False


def _calculate_confidence(shift: dict, daily_df: pd.DataFrame, preserved: bool) -> float:
    """Confidence scoring:

    - Structure shift detected and preserved → base 70%
    - More recent shift = higher confidence (decay with age)
    - No shift or invalidated → low confidence
    """
    if shift["direction"] == "none":
        return 0.0

    if not preserved:
        return 20.0  # A shift happened but was invalidated — low confidence

    # How many days since the shift?
    candles_since_shift = len(daily_df) - 1 - shift["index"]

    # Base confidence 80% for a fresh shift, decay down to 50% after 30 days
    if candles_since_shift <= 1:
        return 90.0
    elif candles_since_shift <= 5:
        return 85.0
    elif candles_since_shift <= 10:
        return 75.0
    elif candles_since_shift <= 20:
        return 65.0
    elif candles_since_shift <= 30:
        return 55.0
    else:
        return 45.0


def _empty_result(symbol: str, reason: str) -> dict:
    return {
        "symbol": symbol,
        "bias": "Neutral",
        "confidence": 0,
        "score": 0,
        "factors": {
            "structure_shift": {"signal": "neutral", "weight": 1.0, "score": 0.0, "detail": reason}
        },
        "key_levels": {},
        "structure": "unknown",
        "structure_break": {"type": None, "detail": reason},
        "asian_session": {"manipulation": "neutral", "detail": reason},
        "swing_highs": [],
        "swing_lows": [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
