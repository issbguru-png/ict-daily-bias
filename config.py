"""Configuration for ICT Daily Bias Tool."""

# --- Instruments ---
INSTRUMENTS = [
    "EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF", "AUD/USD", "NZD/USD", "USD/CAD",
    "EUR/GBP", "EUR/JPY", "GBP/JPY",
    "XAU/USD", "XAG/USD",
]

# yfinance symbol mapping
YFINANCE_SYMBOLS = {
    "EUR/USD": "EURUSD=X", "GBP/USD": "GBPUSD=X", "USD/JPY": "USDJPY=X",
    "USD/CHF": "USDCHF=X", "AUD/USD": "AUDUSD=X", "NZD/USD": "NZDUSD=X",
    "USD/CAD": "USDCAD=X", "EUR/GBP": "EURGBP=X", "EUR/JPY": "EURJPY=X",
    "GBP/JPY": "GBPJPY=X", "XAU/USD": "GC=F", "XAG/USD": "SI=F",
}

# --- Twelve Data ---
TWELVE_DATA_API_KEY = ""  # Set your key here or leave empty to use yfinance only
TWELVE_DATA_BASE_URL = "https://api.twelvedata.com"

# --- Swing Detection ---
DAILY_SWING_LOOKBACK = 3
H1_SWING_LOOKBACK = 2
M15_SWING_LOOKBACK = 2

# --- Bias Thresholds ---
BULLISH_THRESHOLD = 0.25
BEARISH_THRESHOLD = -0.25

# --- Factor Weights ---
WEIGHTS = {
    "market_structure": 0.30,
    "liquidity_sweep": 0.25,
    "order_blocks": 0.15,
    "asian_manipulation": 0.15,
    "fvgs": 0.10,
    "draw_on_liquidity": 0.05,
}

# --- Session Times (EST/New York) ---
SESSIONS = {
    "asian":        {"start": "19:00", "end": "02:00"},  # prev day 7pm to 2am
    "london":       {"start": "02:00", "end": "05:00"},
    "new_york":     {"start": "08:00", "end": "11:00"},
    "london_close": {"start": "10:00", "end": "12:00"},
}

# --- Data Refresh ---
REFRESH_INTERVAL_SECONDS = 1800  # 30 minutes
SERVER_PORT = 8080
