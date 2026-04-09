"""FastAPI application with API endpoints and dashboard serving."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config import INSTRUMENTS, REFRESH_INTERVAL_SECONDS
from data.fetcher import get_daily, get_hourly, get_15min, clear_cache
from analysis.bias_engine import determine_bias

logger = logging.getLogger("ict-bias")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Global bias results cache
_bias_results: dict = {}
_last_refresh: str = "Never"
_refresh_lock = asyncio.Lock()


def _refresh_all_bias_sync():
    """Fetch data and compute bias for all instruments (synchronous)."""
    global _bias_results, _last_refresh
    logger.info("Starting bias refresh for %d instruments...", len(INSTRUMENTS))
    results = {}
    for symbol in INSTRUMENTS:
        try:
            daily = get_daily(symbol)
            h1 = get_hourly(symbol)
            m15 = get_15min(symbol)
            result = determine_bias(symbol, daily, h1, m15)
            results[symbol] = result
            logger.info("  %s: %s (%.1f%%)", symbol, result["bias"], result["confidence"])
        except Exception as e:
            logger.error("  %s: Error - %s", symbol, e, exc_info=True)
            results[symbol] = {
                "symbol": symbol, "bias": "Error", "confidence": 0, "score": 0,
                "factors": {}, "key_levels": {}, "structure": "unknown",
                "structure_break": {"type": None, "detail": str(e)},
                "asian_session": {"manipulation": "neutral", "detail": str(e)},
                "swing_highs": [], "swing_lows": [],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
    _bias_results = results
    _last_refresh = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    logger.info("Bias refresh complete. Last refresh: %s", _last_refresh)


async def _initial_load_then_periodic():
    """Load data once on startup, then refresh periodically."""
    try:
        await asyncio.to_thread(_refresh_all_bias_sync)
    except Exception as e:
        logger.error("Initial load error: %s", e)
    while True:
        await asyncio.sleep(REFRESH_INTERVAL_SECONDS)
        try:
            async with _refresh_lock:
                await asyncio.to_thread(_refresh_all_bias_sync)
        except Exception as e:
            logger.error("Periodic refresh error: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: launch background data loading (non-blocking)."""
    logger.info("ICT Daily Bias Tool starting up...")
    task = asyncio.create_task(_initial_load_then_periodic())
    yield
    task.cancel()


import os
# Resolve paths relative to this file: api/routes.py -> go up one level to project root
_this_dir = os.path.dirname(os.path.abspath(__file__))
_base_dir = os.path.dirname(_this_dir)
_static_dir = os.path.join(_base_dir, "static")
_templates_dir = os.path.join(_base_dir, "templates")

# Fallback: if paths don't exist, try /app (Docker WORKDIR)
if not os.path.exists(_static_dir):
    _base_dir = "/app"
    _static_dir = os.path.join(_base_dir, "static")
    _templates_dir = os.path.join(_base_dir, "templates")

logger.info("Serving static from: %s (exists=%s)", _static_dir, os.path.exists(_static_dir))
logger.info("Serving templates from: %s (exists=%s)", _templates_dir, os.path.exists(_templates_dir))

app = FastAPI(title="ICT Daily Bias Tool", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=_static_dir), name="static")
templates = Jinja2Templates(directory=_templates_dir)


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/api/bias")
async def get_all_bias():
    return JSONResponse({
        "timestamp": _last_refresh,
        "instruments": list(_bias_results.values()),
    })


@app.get("/api/bias/{symbol:path}")
async def get_symbol_bias(symbol: str):
    symbol = symbol.replace("%2F", "/").upper()
    if symbol in _bias_results:
        return JSONResponse(_bias_results[symbol])
    return JSONResponse({"error": f"Symbol {symbol} not found"}, status_code=404)


@app.get("/api/chart/{symbol:path}")
async def get_chart_data(symbol: str):
    """Return OHLC data + overlay markers for charting."""
    symbol = symbol.replace("%2F", "/").upper()
    try:
        daily = get_daily(symbol)
        if daily.empty:
            return JSONResponse({"error": "No data"}, status_code=404)

        candles = []
        for _, row in daily.iterrows():
            candles.append({
                "time": int(row["datetime"].timestamp()),
                "open": round(float(row["open"]), 5),
                "high": round(float(row["high"]), 5),
                "low": round(float(row["low"]), 5),
                "close": round(float(row["close"]), 5),
            })

        bias_data = _bias_results.get(symbol, {})
        return JSONResponse({
            "symbol": symbol,
            "candles": candles,
            "key_levels": bias_data.get("key_levels", {}),
            "swing_highs": bias_data.get("swing_highs", []),
            "swing_lows": bias_data.get("swing_lows", []),
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/refresh")
async def force_refresh():
    async with _refresh_lock:
        await asyncio.to_thread(_refresh_all_bias_sync)
    return JSONResponse({"status": "refreshed", "timestamp": _last_refresh})
