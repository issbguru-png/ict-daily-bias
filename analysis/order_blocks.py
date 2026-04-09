"""Order Block detection — last opposing candle before an impulse move."""
from __future__ import annotations

import pandas as pd


def detect_order_blocks(df: pd.DataFrame, swing_highs: list[dict],
                        swing_lows: list[dict]) -> list[dict]:
    """Detect bullish and bearish order blocks with validation and mitigation tracking."""
    obs = []
    opens = df["open"].values
    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values
    times = df["datetime"].values
    n = len(df)

    # Bullish OB: last bearish candle before a swing low that led to an up move
    for sl in swing_lows:
        idx = sl["index"]
        for j in range(idx, max(idx - 5, 0) - 1, -1):
            if j < 0 or j >= n:
                continue
            if closes[j] < opens[j]:  # bearish candle
                ob_top = float(opens[j])
                ob_bottom = float(lows[j])
                ob_range = ob_top - ob_bottom
                if ob_range <= 0:
                    break
                # Validate: impulse must be >= 2x OB range
                # Find the next swing high after this swing low
                next_sh = None
                for sh in swing_highs:
                    if sh["time"] > sl["time"]:
                        next_sh = sh
                        break
                impulse = (next_sh["price"] - ob_bottom) if next_sh else (sl["price"] - ob_bottom)
                if abs(impulse) < 2 * ob_range:
                    break
                obs.append({
                    "type": "bullish",
                    "top": ob_top,
                    "bottom": ob_bottom,
                    "midpoint": float((ob_top + ob_bottom) / 2),
                    "time": times[j],
                    "index": j,
                    "mitigated": False,
                })
                break

    # Bearish OB: last bullish candle before a swing high that led to a down move
    for sh in swing_highs:
        idx = sh["index"]
        for j in range(idx, max(idx - 5, 0) - 1, -1):
            if j < 0 or j >= n:
                continue
            if closes[j] > opens[j]:  # bullish candle
                ob_top = float(highs[j])
                ob_bottom = float(closes[j])
                ob_range = ob_top - ob_bottom
                if ob_range <= 0:
                    break
                next_sl = None
                for sl in swing_lows:
                    if sl["time"] > sh["time"]:
                        next_sl = sl
                        break
                impulse = (ob_top - next_sl["price"]) if next_sl else (ob_top - sh["price"])
                if abs(impulse) < 2 * ob_range:
                    break
                obs.append({
                    "type": "bearish",
                    "top": ob_top,
                    "bottom": ob_bottom,
                    "midpoint": float((ob_top + ob_bottom) / 2),
                    "time": times[j],
                    "index": j,
                    "mitigated": False,
                })
                break

    # Check mitigation status
    for ob in obs:
        start_idx = ob["index"] + 1
        if start_idx >= n:
            continue
        if ob["type"] == "bullish":
            if closes[start_idx:].min() < ob["bottom"]:
                ob["mitigated"] = True
        else:
            if closes[start_idx:].max() > ob["top"]:
                ob["mitigated"] = True

    return obs


def get_unmitigated_obs(obs: list[dict]) -> list[dict]:
    return [ob for ob in obs if not ob["mitigated"]]
