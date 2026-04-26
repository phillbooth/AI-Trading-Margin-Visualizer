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
    configured = float(os.getenv("DEMO_BROKER_MAX_LEVERAGE", "1"))
    return min(10.0, max(1.0, configured))


def fee_pct():
    return float(os.getenv("DEMO_BROKER_FEE_PCT", "0.1"))


def min_trade_interval_ms():
    return int(os.getenv("DEMO_BROKER_MIN_TRADE_INTERVAL_MS", "300000"))


def max_order_pct():
    return float(os.getenv("DEMO_BROKER_MAX_ORDER_PCT", "10"))


def max_daily_loss():
    return float(os.getenv("DEMO_BROKER_MAX_DAILY_LOSS", "5"))


def allowed_symbols():
    raw = os.getenv("DEMO_BROKER_ALLOWED_SYMBOLS", "")
    return [normalize_symbol(symbol) for symbol in raw.split(",") if normalize_symbol(symbol)]


def default_state():
    return {
        "mode": "demo_only",
        "cash": initial_cash(),
        "currency": os.getenv("DEMO_BROKER_CURRENCY", "USD"),
        "max_leverage": leverage_cap(),
        "fee_pct": fee_pct(),
        "min_trade_interval_ms": min_trade_interval_ms(),
        "max_order_pct": max_order_pct(),
        "max_daily_loss": max_daily_loss(),
        "daily_realized_pnl": {},
        "positions": {},
        "history": [],
        "updated_at": now_iso(),
        "notes": [
            "Paper broker only.",
            "No shorting.",
            f"Configured leverage cap is {leverage_cap():.0f}. Absolute hard ceiling is 10.",
            f"Trade cooldown defaults to {min_trade_interval_ms()} ms.",
            f"Max order size defaults to {max_order_pct()}% of available cash.",
            f"Max realized daily loss defaults to {max_daily_loss()} in account currency.",
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
        latest = latest_price(symbol)
        market_value = position["units"] * latest["price"]
        exit_fee = estimate_fee(market_value)
        gross_unrealized = market_value - (position["units"] * position["avg_price"])
        net_unrealized = (market_value - exit_fee) - (position["units"] * position["avg_price"])
        items.append({
            "symbol": symbol,
            **position,
            "market_price": latest["price"],
            "market_value": market_value,
            "estimated_exit_fee": exit_fee,
            "unrealized_pnl_gross": gross_unrealized,
            "unrealized_pnl_net_after_exit_fee": net_unrealized,
        })
    return items


def broker_state():
    state = load_state()
    return {
        "mode": state["mode"],
        "cash": state["cash"],
        "currency": state["currency"],
        "max_leverage": state["max_leverage"],
        "fee_pct": state.get("fee_pct", fee_pct()),
        "min_trade_interval_ms": state.get("min_trade_interval_ms", min_trade_interval_ms()),
        "max_order_pct": state.get("max_order_pct", max_order_pct()),
        "max_daily_loss": state.get("max_daily_loss", max_daily_loss()),
        "allowed_symbols": allowed_symbols(),
        "daily_realized_pnl": state.get("daily_realized_pnl", {}),
        "cooldown": cooldown_status(state),
        "positions": positions_as_list(state),
        "history": state["history"][-25:],
        "updated_at": state["updated_at"],
        "notes": state["notes"],
    }


def require_symbol_allowed(symbol):
    whitelist = allowed_symbols()
    if whitelist and symbol not in whitelist:
        raise ValueError(f"Symbol {symbol} is not in the demo broker whitelist.")


def parse_event_time(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def today_key():
    return datetime.now(timezone.utc).date().isoformat()


def cooldown_status(state):
    minimum = state.get("min_trade_interval_ms", min_trade_interval_ms())
    if not state["history"]:
        return {
            "can_trade_now": True,
            "remaining_ms": 0,
            "last_trade_time": None,
            "min_trade_interval_ms": minimum,
        }

    last_event = state["history"][-1]
    last_time = parse_event_time(last_event.get("time"))
    if last_time is None:
        return {
            "can_trade_now": True,
            "remaining_ms": 0,
            "last_trade_time": None,
            "min_trade_interval_ms": minimum,
        }

    elapsed_ms = int((datetime.now(timezone.utc) - last_time).total_seconds() * 1000)
    remaining = max(0, minimum - elapsed_ms)
    return {
        "can_trade_now": remaining == 0,
        "remaining_ms": remaining,
        "last_trade_time": last_event.get("time"),
        "min_trade_interval_ms": minimum,
    }


def enforce_rate_limit(state):
    status = cooldown_status(state)
    if not status["can_trade_now"]:
        raise ValueError(
            f"Demo broker trade rate limit active. Wait {status['remaining_ms']} ms before placing another trade."
        )


def estimate_fee(amount):
    return amount * (fee_pct() / 100)


def enforce_max_daily_loss(state):
    pnl_today = float(state.get("daily_realized_pnl", {}).get(today_key(), 0.0))
    if pnl_today <= -state.get("max_daily_loss", max_daily_loss()):
        raise ValueError("Demo broker max daily loss reached. New trades are blocked for today.")


def enforce_max_order_size(state, amount, side):
    if side != "BUY":
        return
    cash = float(state["cash"])
    maximum = cash * (state.get("max_order_pct", max_order_pct()) / 100)
    if amount > maximum:
        raise ValueError(
            f"Demo broker max order size exceeded. Maximum allowed buy is {maximum:.2f} based on current cash."
        )


def place_demo_order(symbol, side, amount, leverage=1, target_exit_price=None, take_profit_pct=None):
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
    if leverage > 10:
        raise ValueError("Demo broker leverage cannot exceed the hard ceiling of 10.")

    require_symbol_allowed(symbol)

    market = latest_price(symbol)
    price = market["price"]
    units = amount / price
    state = load_state()
    enforce_max_daily_loss(state)
    enforce_rate_limit(state)
    enforce_max_order_size(state, amount, side)
    positions = state["positions"]
    current = positions.get(symbol, {"units": 0.0, "avg_price": 0.0, "last_price": price})
    executed_units = units
    estimated_fee = estimate_fee(amount)
    realized_pnl = 0.0

    if side == "BUY":
        total_cost = amount + estimated_fee
        if total_cost > state["cash"]:
            raise ValueError("Insufficient demo broker cash for requested buy plus fees.")
        new_units = current["units"] + units
        if new_units <= 0:
            raise ValueError("Computed unit count is invalid.")
        weighted_cost = (current["units"] * current["avg_price"]) + total_cost
        current["units"] = new_units
        current["avg_price"] = weighted_cost / new_units
        current["last_price"] = price
        if target_exit_price is not None:
            current["target_exit_price"] = float(target_exit_price)
        elif take_profit_pct is not None:
            current["target_exit_price"] = price * (1 + (float(take_profit_pct) / 100))
        state["cash"] -= total_cost
        positions[symbol] = current
    else:
        if current["units"] <= 0:
            raise ValueError(f"No demo broker position to sell for {symbol}.")
        units_to_sell = min(units, current["units"])
        executed_units = units_to_sell
        gross_proceeds = units_to_sell * price
        sell_fee = estimate_fee(gross_proceeds)
        proceeds = gross_proceeds - sell_fee
        cost_basis_sold = current["avg_price"] * units_to_sell
        realized_pnl = proceeds - cost_basis_sold
        current["units"] -= units_to_sell
        current["last_price"] = price
        state["cash"] += proceeds
        estimated_fee = sell_fee
        state.setdefault("daily_realized_pnl", {})
        state["daily_realized_pnl"][today_key()] = float(state["daily_realized_pnl"].get(today_key(), 0.0)) + realized_pnl
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
        "estimated_fee": estimated_fee,
        "realized_pnl": realized_pnl,
        "target_exit_price": float(target_exit_price) if target_exit_price is not None else None,
        "take_profit_pct": float(take_profit_pct) if take_profit_pct is not None else None,
        "source": market["source"],
    }
    state["history"].append(event)
    save_state(state)
    return {
        "status": "accepted",
        "order": event,
        "broker_state": broker_state(),
    }
