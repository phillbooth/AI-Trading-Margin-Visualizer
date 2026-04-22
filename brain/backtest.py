import csv
from pathlib import Path


def load_candles(path):
    with Path(path).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    candles = []
    for row in rows:
        candles.append({
            "time": row["time"],
            "symbol": row["symbol"],
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": float(row["volume"]),
        })
    return candles


def classify_return(return_pct, threshold=0.12):
    if return_pct > threshold:
        return "UP"
    if return_pct < -threshold:
        return "DOWN"
    return "FLAT"


def max_drawdown_pct(equity_curve):
    peak = equity_curve[0]
    drawdown = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        if peak:
            drawdown = max(drawdown, ((peak - value) / peak) * 100)
    return drawdown


def decision_from_prediction(prediction):
    if prediction["direction"] == "UP":
        return "BUY"
    if prediction["direction"] == "DOWN":
        return "SELL"
    return "HOLD"


def summarize_results(results):
    total_predictions = sum(result["prediction_count"] for result in results)
    weighted_accuracy = sum(result["accuracy"] * result["prediction_count"] for result in results)
    weighted_error = sum(result["avg_return_error"] * result["prediction_count"] for result in results)
    scored = max(1, total_predictions)

    return {
        "asset_count": len(results),
        "prediction_count": total_predictions,
        "mistake_count": sum(len(result["mistakes"]) for result in results),
        "accuracy": weighted_accuracy / scored,
        "avg_return_error": weighted_error / scored,
        "max_drawdown_pct": max((result["max_drawdown_pct"] for result in results), default=0.0),
        "ending_equity_total": sum(result["ending_equity"] for result in results),
    }


def run_backtest(candles, strategy, window, starting_equity):
    equity = starting_equity
    equity_curve = [equity]
    predictions = []
    mistakes = []
    correct = 0
    return_error_sum = 0.0

    for index in range(window, len(candles) - 1):
        history = candles[:index + 1]
        current = history[-1]
        actual = candles[index + 1]
        prediction = strategy.predict(history)
        actual_return_pct = ((actual["close"] - current["close"]) / current["close"]) * 100
        actual_direction = classify_return(actual_return_pct)
        was_correct = prediction["direction"] == actual_direction
        correct += 1 if was_correct else 0
        return_error_sum += abs(prediction["expected_return_pct"] - actual_return_pct)

        decision = decision_from_prediction(prediction)
        exposure = min(0.20, prediction["confidence"] / 500)
        signed_exposure = exposure if decision == "BUY" else -exposure if decision == "SELL" else 0.0
        equity *= 1 + ((actual_return_pct / 100) * signed_exposure)
        equity_curve.append(equity)

        record = {
            "time": current["time"],
            "symbol": current["symbol"],
            "strategy_generation": strategy.generation,
            "predicted_direction": prediction["direction"],
            "predicted_return_pct": prediction["expected_return_pct"],
            "confidence": prediction["confidence"],
            "actual_direction": actual_direction,
            "actual_return_pct": actual_return_pct,
            "was_correct": was_correct,
            "decision": decision,
            "paper_equity": equity,
            "signals": prediction["signals"],
            "reason": prediction["reason"],
        }
        predictions.append(record)

        if not was_correct and abs(actual_return_pct) >= 0.35:
            mistakes.append({
                "time": current["time"],
                "symbol": current["symbol"],
                "mistake_type": "wrong_direction",
                "severity": "high" if abs(actual_return_pct) >= 1.5 else "medium",
                "context": record,
            })

    scored = max(1, len(predictions))
    return {
        "strategy": strategy.name,
        "strategy_generation": strategy.generation,
        "symbol": candles[0]["symbol"] if candles else "UNKNOWN",
        "window": window,
        "candle_count": len(candles),
        "prediction_count": len(predictions),
        "accuracy": correct / scored,
        "avg_return_error": return_error_sum / scored,
        "ending_equity": equity,
        "max_drawdown_pct": max_drawdown_pct(equity_curve),
        "predictions": predictions,
        "mistakes": mistakes,
    }
