from strategy import Strategy

from market_data import fetch_recent_candles, normalize_symbol, yfinance_support_status


def split_symbols(symbols_value):
    if not symbols_value:
        return []
    if isinstance(symbols_value, str):
        return [normalize_symbol(symbol) for symbol in symbols_value.split(",") if normalize_symbol(symbol)]
    return [normalize_symbol(symbol) for symbol in symbols_value if normalize_symbol(symbol)]


def paper_decision(prediction):
    if prediction["direction"] == "UP":
        return "BUY"
    if prediction["direction"] == "DOWN":
        return "SELL"
    return "HOLD"


def predict_symbol(symbol, period="6mo", interval="1d"):
    candles = fetch_recent_candles(symbol, period=period, interval=interval)
    strategy = Strategy()
    prediction = strategy.predict(candles)
    latest = candles[-1]
    return {
        "symbol": latest["symbol"],
        "latest_candle": latest,
        "prediction": {
            "strategy": strategy.name,
            "strategy_generation": strategy.generation,
            "direction": prediction["direction"],
            "expected_return_pct": prediction["expected_return_pct"],
            "confidence": prediction["confidence"],
            "signals": prediction["signals"],
            "reason": prediction["reason"],
            "paper_decision": paper_decision(prediction),
        },
        "history_size": len(candles),
        "source": "yfinance_delayed",
    }


def build_watchlist_predictions(symbols, period="6mo", interval="1d"):
    support = yfinance_support_status()
    if not support["enabled"]:
        return {
            "source": "yfinance_delayed",
            "status": "unavailable",
            "reason": support["reason"],
            "items": [],
        }

    items = []
    errors = []
    for symbol in split_symbols(symbols):
        try:
            items.append(predict_symbol(symbol, period=period, interval=interval))
        except Exception as error:  # pragma: no cover - network/provider dependent
            errors.append({"symbol": symbol, "error": str(error)})

    return {
        "source": "yfinance_delayed",
        "status": "ok" if items else "error",
        "symbols": split_symbols(symbols),
        "items": items,
        "errors": errors,
    }
