import argparse
import json
from pathlib import Path

from backtest import load_candles, run_backtest
from strategy import Strategy


def main():
    parser = argparse.ArgumentParser(description="Run the Brain historical prediction backtest.")
    parser.add_argument("--data", default="data/fixtures/sample_stock_ohlcv.csv")
    parser.add_argument("--window", type=int, default=5)
    parser.add_argument("--starting-equity", type=float, default=10000)
    parser.add_argument("--report", default="")
    args = parser.parse_args()

    candles = load_candles(args.data)
    if len(candles) <= args.window + 1:
        raise SystemExit("Not enough candles for the requested backtest window.")

    result = run_backtest(candles, Strategy(), args.window, args.starting_equity)
    summary = {key: result[key] for key in (
        "strategy",
        "strategy_generation",
        "symbol",
        "candle_count",
        "prediction_count",
        "accuracy",
        "avg_return_error",
        "ending_equity",
        "max_drawdown_pct",
    )}
    print(json.dumps(summary, indent=2))

    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
