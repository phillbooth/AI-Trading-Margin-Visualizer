from datetime import datetime
from pathlib import Path


try:
    import yfinance as yf
except ImportError:  # pragma: no cover - optional dependency in some local flows
    yf = None


def yfinance_support_status():
    if yf is None:
        return {"enabled": False, "reason": "yfinance_not_installed"}
    return {"enabled": True}


def utc_market_open_timestamp(date_value):
    if hasattr(date_value, "date"):
        date_value = date_value.date()
    return f"{date_value.isoformat()}T14:30:00Z"


def normalize_symbol(symbol):
    return str(symbol or "").strip().upper()


def fetch_recent_candles(symbol, period="6mo", interval="1d"):
    status = yfinance_support_status()
    if not status["enabled"]:
        raise RuntimeError(status["reason"])

    normalized = normalize_symbol(symbol)
    ticker = yf.Ticker(normalized)
    history = ticker.history(period=period, interval=interval, auto_adjust=False, actions=False)
    if history.empty:
        raise ValueError(f"No market data returned for {normalized}.")

    candles = []
    for timestamp, row in history.iterrows():
        open_value = row.get("Open")
        high_value = row.get("High")
        low_value = row.get("Low")
        close_value = row.get("Close")
        volume_value = row.get("Volume")
        values = [open_value, high_value, low_value, close_value, volume_value]
        if any(value is None for value in values):
            continue
        candles.append({
            "time": utc_market_open_timestamp(timestamp),
            "symbol": normalized,
            "open": float(open_value),
            "high": float(high_value),
            "low": float(low_value),
            "close": float(close_value),
            "volume": float(volume_value),
        })

    if not candles:
        raise ValueError(f"No usable candles returned for {normalized}.")
    return candles


def latest_price(symbol, period="10d", interval="1d"):
    candles = fetch_recent_candles(symbol, period=period, interval=interval)
    last = candles[-1]
    return {
        "symbol": last["symbol"],
        "time": last["time"],
        "price": last["close"],
        "source": "yfinance_delayed",
    }
