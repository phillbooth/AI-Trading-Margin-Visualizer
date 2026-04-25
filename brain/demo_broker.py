import json
import os
from datetime import datetime, timezone
from pathlib import Path

from market_data import latest_price, normalize_symbol


ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "run" / "demo_broker_state.json"


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def initial_cash():
    return float(os.getenv("DEMO_BROKER_INITIAL_CASH", "100"))


def leverage_cap():
    return float(os.getenv("DEMO_BROKER_MAX_LEVERAGE", "1"))


def allowed_symbols():
    raw = os.getenv("DEMO_BROKER_ALLOWED_SYMBOLS", "")
    return [normalize_symbol(symbol) for symbol in raw.split(",") if normalize_symbol(symbol)]


def default_state():
    return {
        "mode": "demo_only",
        "cash": initial_cash(),
        "currency": os.getenv("DEMO_BROKER_CURRENCY", "USD"),
        "max_leverage": leverage_cap(),
        "positions": {},
        "history": [],
        "updated_at": now_iso(),
        "notes": [
            "Paper broker only.",
            "No shorting.",
            "No leverage above 1.",
            "No FX conversion. Cash and instrument price are assumed to be in the same currency.",
        ],
    }


def load_state():
    if not STATE_PATH.exists():
        return default_state()
    return json.loads(STATE_PATH.read_text(encoding="utf-8-sig"))


def save_state(state):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = now_iso()
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return state


def positions_as_list(state):
    items = []
    for symbol, position in sorted(state["positions"].items()):
        items.append({
            "symbol": symbol,
            **position,
        })
    return items


def broker_state():
    state = load_state()
    return {
        "mode": state["mode"],
        "cash": state["cash"],
        "currency": state["currency"],
        "max_leverage": state["max_leverage"],
        "allowed_symbols": allowed_symbols(),
        "positions": positions_as_list(state),
        "history": state["history"][-25:],
        "updated_at": state["updated_at"],
        "notes": state["notes"],
    }


def require_symbol_allowed(symbol):
    whitelist = allowed_symbols()
    if whitelist and symbol not in whitelist:
        raise ValueError(f"Symbol {symbol} is not in the demo broker whitelist.")


def place_demo_order(symbol, side, amount, leverage=1):
    symbol = normalize_symbol(symbol)
    side = str(side or "").strip().upper()
    amount = float(amount)
    leverage = float(leverage)

    if side not in {"BUY", "SELL"}:
        raise ValueError("Demo broker side must be BUY or SELL.")
    if amount <= 0:
        raise ValueError("Demo broker amount must be greater than zero.")
    if leverage > leverage_cap():
        raise ValueError(f"Demo broker leverage cannot exceed {leverage_cap():.0f}.")
    if leverage < 1:
        raise ValueError("Demo broker leverage cannot be less than 1.")

    require_symbol_allowed(symbol)

    market = latest_price(symbol)
    price = market["price"]
    units = amount / price
    state = load_state()
    positions = state["positions"]
    current = positions.get(symbol, {"units": 0.0, "avg_price": 0.0, "last_price": price})
    executed_units = units

    if side == "BUY":
        if amount > state["cash"]:
            raise ValueError("Insufficient demo broker cash for requested buy.")
        new_units = current["units"] + units
        if new_units <= 0:
            raise ValueError("Computed unit count is invalid.")
        weighted_cost = (current["units"] * current["avg_price"]) + amount
        current["units"] = new_units
        current["avg_price"] = weighted_cost / new_units
        current["last_price"] = price
        state["cash"] -= amount
        positions[symbol] = current
    else:
        if current["units"] <= 0:
            raise ValueError(f"No demo broker position to sell for {symbol}.")
        units_to_sell = min(units, current["units"])
        executed_units = units_to_sell
        proceeds = units_to_sell * price
        current["units"] -= units_to_sell
        current["last_price"] = price
        state["cash"] += proceeds
        if current["units"] <= 1e-9:
            positions.pop(symbol, None)
        else:
            positions[symbol] = current

    event = {
        "time": now_iso(),
        "symbol": symbol,
        "side": side,
        "amount": amount,
        "price": price,
        "units": executed_units,
        "leverage": leverage,
        "source": market["source"],
    }
    state["history"].append(event)
    save_state(state)
    return {
        "status": "accepted",
        "order": event,
        "broker_state": broker_state(),
    }
