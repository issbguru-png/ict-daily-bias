"""Master bias engine — weighted scoring across all ICT analysis components."""
from __future__ import annotations

import pandas as pd
from datetime import datetime, timezone

from config import WEIGHTS, BULLISH_THRESHOLD, BEARISH_THRESHOLD, DAILY_SWING_LOOKBACK, H1_SWING_LOOKBACK
from analysis.swing_points import detect_swing_highs, detect_swing_lows
from analysis.market_structure import classify_structure, detect_structure_break
from analysis.fair_value_gaps import detect_fvgs, get_unfilled_fvgs
from analysis.order_blocks import detect_order_blocks, get_unmitigated_obs
from analysis.liquidity import (identify_liquidity_pools, detect_liquidity_sweeps,
                                determine_draw_on_liquidity)
from analysis.power_of_three import detect_asian_manipulation


def determine_bias(symbol: str, daily_df: pd.DataFrame,
                   h1_df: pd.DataFrame, m15_df: pd.DataFrame) -> dict:
    """Run all ICT analysis and produce a weighted bias score.

    Returns a comprehensive result dict with bias, confidence, factors, and key levels.
    """
    if daily_df.empty or len(daily_df) < 10:
        return _empty_result(symbol, "Insufficient daily data")

    current_price = float(daily_df.iloc[-1]["close"])

    # --- Run all sub-analyses ---

    # 1. Swing points on daily
    swing_highs = detect_swing_highs(daily_df, lookback=DAILY_SWING_LOOKBACK)
    swing_lows = detect_swing_lows(daily_df, lookback=DAILY_SWING_LOOKBACK)

    # 2. Market structure
    ms = classify_structure(swing_highs, swing_lows)
    structure = ms["structure"]
    structure_break = detect_structure_break(
        daily_df, structure, ms["last_swing_high"], ms["last_swing_low"]
    )

    # 3. Fair Value Gaps on daily
    all_fvgs = detect_fvgs(daily_df)
    unfilled_fvgs = get_unfilled_fvgs(all_fvgs)

    # 4. Order Blocks on daily
    all_obs = detect_order_blocks(daily_df, swing_highs, swing_lows)
    unmitigated_obs = get_unmitigated_obs(all_obs)

    # 5. Liquidity pools and sweeps
    pools = identify_liquidity_pools(daily_df, swing_highs, swing_lows)
    sweeps = detect_liquidity_sweeps(daily_df, pools, lookback_candles=5)

    # 6. Draw on Liquidity
    dol = determine_draw_on_liquidity(current_price, pools, sweeps, unfilled_fvgs)

    # 7. Asian manipulation (use today's date)
    asian_manip = {"manipulation": "neutral", "detail": "No intraday data"}
    try:
        today = pd.Timestamp.now(tz="America/New_York")
        if not h1_df.empty or not m15_df.empty:
            asian_manip = detect_asian_manipulation(h1_df, m15_df, today)
    except Exception as e:
        asian_manip = {"manipulation": "neutral", "detail": f"Session analysis unavailable: {e}"}

    # --- Score each factor ---
    factors = {}
    total_score = 0.0

    # Factor 1: Market Structure (0.30)
    w = WEIGHTS["market_structure"]
    if structure == "bullish":
        factors["market_structure"] = _factor("bullish", w, w, f"Daily structure: HH/HL ({structure})")
    elif structure == "bearish":
        factors["market_structure"] = _factor("bearish", w, -w, f"Daily structure: LH/LL ({structure})")
    else:
        factors["market_structure"] = _factor("neutral", w, 0, f"Daily structure: {structure}")

    # Adjust for MSS (structure shift overrides current structure)
    if structure_break["type"] == "MSS_bullish":
        factors["market_structure"]["signal"] = "bullish"
        factors["market_structure"]["score"] = w * 0.8  # slightly reduced since it's a shift
        factors["market_structure"]["detail"] = f"MSS to bullish: {structure_break['detail']}"
    elif structure_break["type"] == "MSS_bearish":
        factors["market_structure"]["signal"] = "bearish"
        factors["market_structure"]["score"] = -w * 0.8
        factors["market_structure"]["detail"] = f"MSS to bearish: {structure_break['detail']}"

    total_score += factors["market_structure"]["score"]

    # Factor 2: Liquidity Sweep (0.25)
    w = WEIGHTS["liquidity_sweep"]
    if sweeps:
        last_sweep = sweeps[-1]
        if last_sweep["implication"] == "bullish":
            factors["liquidity_sweep"] = _factor(
                "bullish", w, w,
                f"Sell-side swept ({last_sweep['pool']['label']} at {last_sweep['pool']['level']:.5f})"
            )
        else:
            factors["liquidity_sweep"] = _factor(
                "bearish", w, -w,
                f"Buy-side swept ({last_sweep['pool']['label']} at {last_sweep['pool']['level']:.5f})"
            )
    else:
        factors["liquidity_sweep"] = _factor("neutral", w, 0, "No recent liquidity sweep")
    total_score += factors["liquidity_sweep"]["score"]

    # Factor 3: Order Blocks (0.15)
    w = WEIGHTS["order_blocks"]
    bull_obs_below = [ob for ob in unmitigated_obs
                      if ob["type"] == "bullish" and ob["top"] <= current_price]
    bear_obs_above = [ob for ob in unmitigated_obs
                      if ob["type"] == "bearish" and ob["bottom"] >= current_price]
    if bull_obs_below and not bear_obs_above:
        nearest = max(bull_obs_below, key=lambda x: x["top"])
        factors["order_blocks"] = _factor(
            "bullish", w, w,
            f"Unmitigated bullish OB at {nearest['top']:.5f}-{nearest['bottom']:.5f}"
        )
    elif bear_obs_above and not bull_obs_below:
        nearest = min(bear_obs_above, key=lambda x: x["bottom"])
        factors["order_blocks"] = _factor(
            "bearish", w, -w,
            f"Unmitigated bearish OB at {nearest['top']:.5f}-{nearest['bottom']:.5f}"
        )
    elif bull_obs_below and bear_obs_above:
        # Both exist — check which is closer
        bull_dist = current_price - max(bull_obs_below, key=lambda x: x["top"])["top"]
        bear_dist = min(bear_obs_above, key=lambda x: x["bottom"])["bottom"] - current_price
        if bull_dist < bear_dist:
            factors["order_blocks"] = _factor("bullish", w, w * 0.5, "Closer to bullish OB")
        else:
            factors["order_blocks"] = _factor("bearish", w, -w * 0.5, "Closer to bearish OB")
    else:
        factors["order_blocks"] = _factor("neutral", w, 0, "No relevant unmitigated OBs")
    total_score += factors["order_blocks"]["score"]

    # Factor 4: Asian Manipulation (0.15)
    w = WEIGHTS["asian_manipulation"]
    if asian_manip["manipulation"] == "bullish":
        factors["asian_manipulation"] = _factor("bullish", w, w, asian_manip["detail"])
    elif asian_manip["manipulation"] == "bearish":
        factors["asian_manipulation"] = _factor("bearish", w, -w, asian_manip["detail"])
    else:
        factors["asian_manipulation"] = _factor("neutral", w, 0, asian_manip["detail"])
    total_score += factors["asian_manipulation"]["score"]

    # Factor 5: Fair Value Gaps (0.10)
    w = WEIGHTS["fvgs"]
    bull_fvgs_below = [f for f in unfilled_fvgs
                       if f["type"] == "bullish" and f["top"] <= current_price]
    bear_fvgs_above = [f for f in unfilled_fvgs
                       if f["type"] == "bearish" and f["bottom"] >= current_price]
    if bull_fvgs_below and not bear_fvgs_above:
        factors["fvgs"] = _factor("bullish", w, w,
                                  f"{len(bull_fvgs_below)} unfilled bullish FVG(s) below price")
    elif bear_fvgs_above and not bull_fvgs_below:
        factors["fvgs"] = _factor("bearish", w, -w,
                                  f"{len(bear_fvgs_above)} unfilled bearish FVG(s) above price")
    else:
        factors["fvgs"] = _factor("neutral", w, 0, "Mixed or no relevant FVGs")
    total_score += factors["fvgs"]["score"]

    # Factor 6: Draw on Liquidity (0.05)
    w = WEIGHTS["draw_on_liquidity"]
    if dol["direction"] == "bullish":
        factors["draw_on_liquidity"] = _factor("bullish", w, w, dol["detail"])
    elif dol["direction"] == "bearish":
        factors["draw_on_liquidity"] = _factor("bearish", w, -w, dol["detail"])
    else:
        factors["draw_on_liquidity"] = _factor("neutral", w, 0, dol["detail"])
    total_score += factors["draw_on_liquidity"]["score"]

    # --- Determine final bias ---
    if total_score >= BULLISH_THRESHOLD:
        bias = "Bullish"
    elif total_score <= BEARISH_THRESHOLD:
        bias = "Bearish"
    else:
        bias = "Neutral"

    confidence = min(abs(total_score) * 100, 100)

    # Key levels for the dashboard
    pdh = float(daily_df.iloc[-2]["high"]) if len(daily_df) >= 2 else None
    pdl = float(daily_df.iloc[-2]["low"]) if len(daily_df) >= 2 else None

    return {
        "symbol": symbol,
        "bias": bias,
        "confidence": round(confidence, 1),
        "score": round(total_score, 4),
        "factors": factors,
        "key_levels": {
            "pdh": pdh,
            "pdl": pdl,
            "current_price": current_price,
            "order_blocks": [_serialize_ob(ob) for ob in unmitigated_obs[-5:]],
            "fvgs": [_serialize_fvg(f) for f in unfilled_fvgs[-5:]],
            "dol_target": dol.get("target"),
        },
        "structure": structure,
        "structure_break": structure_break,
        "asian_session": asian_manip,
        "swing_highs": [{"price": s["price"], "time": str(s["time"])} for s in swing_highs[-10:]],
        "swing_lows": [{"price": s["price"], "time": str(s["time"])} for s in swing_lows[-10:]],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _factor(signal: str, weight: float, score: float, detail: str) -> dict:
    return {"signal": signal, "weight": weight, "score": round(score, 4), "detail": detail}


def _serialize_ob(ob: dict) -> dict:
    return {
        "type": ob["type"], "top": ob["top"], "bottom": ob["bottom"],
        "time": str(ob["time"]),
    }


def _serialize_fvg(fvg: dict) -> dict:
    return {
        "type": fvg["type"], "top": fvg["top"], "bottom": fvg["bottom"],
        "time": str(fvg["time"]),
    }


def _empty_result(symbol: str, reason: str) -> dict:
    return {
        "symbol": symbol,
        "bias": "Neutral",
        "confidence": 0,
        "score": 0,
        "factors": {},
        "key_levels": {},
        "structure": "unknown",
        "structure_break": {"type": None, "detail": reason},
        "asian_session": {"manipulation": "neutral", "detail": reason},
        "swing_highs": [],
        "swing_lows": [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
