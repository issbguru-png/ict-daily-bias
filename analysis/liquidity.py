"""Liquidity pool identification and sweep detection."""
from __future__ import annotations

import pandas as pd
import numpy as np


def identify_liquidity_pools(df: pd.DataFrame, swing_highs: list[dict],
                             swing_lows: list[dict],
                             tolerance_pct: float = 0.001) -> list[dict]:
    """Identify liquidity pools: PDH/PDL, equal highs/lows, swing levels."""
    pools = []
    n = len(df)
    if n < 2:
        return pools

    # Previous Day High / Low (use second-to-last candle for daily data)
    prev = df.iloc[-2]
    pools.append({"type": "buy_side", "level": float(prev["high"]), "label": "PDH"})
    pools.append({"type": "sell_side", "level": float(prev["low"]), "label": "PDL"})

    # Equal Highs (swing highs within tolerance)
    for i, sh1 in enumerate(swing_highs):
        for sh2 in swing_highs[i + 1:]:
            if sh1["price"] > 0 and abs(sh1["price"] - sh2["price"]) / sh1["price"] < tolerance_pct:
                pools.append({
                    "type": "buy_side",
                    "level": max(sh1["price"], sh2["price"]),
                    "label": "EQH",
                })

    # Equal Lows
    for i, sl1 in enumerate(swing_lows):
        for sl2 in swing_lows[i + 1:]:
            if sl1["price"] > 0 and abs(sl1["price"] - sl2["price"]) / sl1["price"] < tolerance_pct:
                pools.append({
                    "type": "sell_side",
                    "level": min(sl1["price"], sl2["price"]),
                    "label": "EQL",
                })

    # All swing highs = buy-side liquidity, swing lows = sell-side
    for sh in swing_highs:
        pools.append({"type": "buy_side", "level": sh["price"], "label": "Swing High"})
    for sl in swing_lows:
        pools.append({"type": "sell_side", "level": sl["price"], "label": "Swing Low"})

    # Deduplicate pools that are very close
    pools = _deduplicate(pools, tolerance_pct)
    return pools


def _deduplicate(pools: list[dict], tol: float) -> list[dict]:
    if not pools:
        return pools
    result = []
    seen = set()
    for p in pools:
        key = (p["type"], round(p["level"], 5))
        if key not in seen:
            seen.add(key)
            result.append(p)
    return result


def detect_liquidity_sweeps(df: pd.DataFrame, pools: list[dict],
                            lookback_candles: int = 5) -> list[dict]:
    """Detect liquidity sweeps: wick beyond level, close inside."""
    sweeps = []
    if df.empty or not pools:
        return sweeps

    recent = df.tail(lookback_candles)
    for pool in pools:
        level = pool["level"]
        for _, candle in recent.iterrows():
            if pool["type"] == "buy_side":
                # Sweep = wick above level, close below
                if candle["high"] > level and candle["close"] < level:
                    sweeps.append({
                        "pool": pool,
                        "sweep_type": "buy_side_swept",
                        "candle_time": candle["datetime"],
                        "implication": "bearish",
                    })
            else:  # sell_side
                # Sweep = wick below level, close above
                if candle["low"] < level and candle["close"] > level:
                    sweeps.append({
                        "pool": pool,
                        "sweep_type": "sell_side_swept",
                        "candle_time": candle["datetime"],
                        "implication": "bullish",
                    })

    # Sort by time, keep most recent
    sweeps.sort(key=lambda s: s["candle_time"])
    return sweeps


def determine_draw_on_liquidity(current_price: float, pools: list[dict],
                                sweeps: list[dict],
                                unfilled_fvgs: list[dict]) -> dict:
    """Determine the Draw on Liquidity direction.

    Rule: internal taken → DOL is external; external taken → DOL is internal.
    """
    result = {"direction": "neutral", "target": None, "detail": "No clear DOL"}

    if sweeps:
        last_sweep = sweeps[-1]
        if last_sweep["sweep_type"] == "sell_side_swept":
            # External sell-side taken → look for buy-side targets
            buy_targets = [p for p in pools if p["type"] == "buy_side" and p["level"] > current_price]
            if buy_targets:
                nearest = min(buy_targets, key=lambda p: p["level"] - current_price)
                result = {
                    "direction": "bullish",
                    "target": nearest,
                    "detail": f"Sell-side swept, DOL is {nearest['label']} at {nearest['level']:.5f}",
                }
        elif last_sweep["sweep_type"] == "buy_side_swept":
            sell_targets = [p for p in pools if p["type"] == "sell_side" and p["level"] < current_price]
            if sell_targets:
                nearest = max(sell_targets, key=lambda p: p["level"])
                result = {
                    "direction": "bearish",
                    "target": nearest,
                    "detail": f"Buy-side swept, DOL is {nearest['label']} at {nearest['level']:.5f}",
                }
    else:
        # No recent sweep — DOL is nearest unswept external liquidity
        buy_above = [p for p in pools if p["type"] == "buy_side" and p["level"] > current_price]
        sell_below = [p for p in pools if p["type"] == "sell_side" and p["level"] < current_price]
        dist_buy = min((p["level"] - current_price for p in buy_above), default=float("inf"))
        dist_sell = min((current_price - p["level"] for p in sell_below), default=float("inf"))
        if dist_buy < dist_sell and buy_above:
            nearest = min(buy_above, key=lambda p: p["level"] - current_price)
            result = {"direction": "bullish", "target": nearest,
                      "detail": f"Nearest DOL: {nearest['label']} at {nearest['level']:.5f}"}
        elif sell_below:
            nearest = max(sell_below, key=lambda p: p["level"])
            result = {"direction": "bearish", "target": nearest,
                      "detail": f"Nearest DOL: {nearest['label']} at {nearest['level']:.5f}"}

    return result
