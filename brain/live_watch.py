from strategy import Strategy

from demo_broker import load_state, cooldown_status
from market_data import fetch_recent_candles, normalize_symbol, yfinance_support_status


def assumed_fee_pct():
    import os

    return float(os.getenv("PREDICTION_ASSUMED_FEE_PCT", "0.1"))


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


def target_exit_price(latest_close, expected_return_pct):
    return latest_close * (1 + (expected_return_pct / 100))


def estimated_trade_plan(latest_close, prediction):
    fee_pct = assumed_fee_pct()
    gross_move_pct = prediction["expected_return_pct"]
    target_price = target_exit_price(latest_close, gross_move_pct)
    round_trip_fee_pct = fee_pct * 2
    net_expected_return_pct = gross_move_pct - round_trip_fee_pct
    return {
        "assumed_fee_pct_per_side": fee_pct,
        "assumed_round_trip_fee_pct": round_trip_fee_pct,
        "entry_price": latest_close,
        "target_exit_price": target_price,
        "gross_expected_return_pct": gross_move_pct,
        "net_expected_return_pct": net_expected_return_pct,
    }


def execution_guardrails(symbol, suggested_action):
    state = load_state()
    cooldown = cooldown_status(state)
    execution_action = suggested_action
    reasons = []

    if suggested_action in {"BUY", "SELL"} and not cooldown["can_trade_now"]:
        execution_action = "WAIT_COOLDOWN"
        reasons.append(f"Trade cooldown active for another {cooldown['remaining_ms']} ms.")

    return {
        "suggested_action": suggested_action,
        "execution_action": execution_action,
        "cooldown": cooldown,
        "reasons": reasons,
    }


def predict_symbol(symbol, period="6mo", interval="1d"):
    candles = fetch_recent_candles(symbol, period=period, interval=interval)
    strategy = Strategy()
    prediction = strategy.predict(candles)
    latest = candles[-1]
    suggested_action = paper_decision(prediction)
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
            "paper_decision": suggested_action,
            "trade_plan": estimated_trade_plan(latest["close"], prediction),
            "execution_guardrails": execution_guardrails(latest["symbol"], suggested_action),
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
