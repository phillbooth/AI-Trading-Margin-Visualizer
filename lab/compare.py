import argparse
import importlib.util
import json
import sys
from pathlib import Path

from env_loader import load_repo_env

ROOT = Path(__file__).resolve().parents[1]
BRAIN_DIR = ROOT / "brain"
if str(BRAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BRAIN_DIR))

from backtest import load_candles, run_backtest, summarize_results  # noqa: E402
from strategy import Strategy as BaselineStrategy  # noqa: E402
from trainer import discover_data_files  # noqa: E402
from sandbox import load_candidate  # noqa: E402


def load_strategy_from_file(path):
    candidate = load_candidate(path)
    return candidate


def evaluate_strategy(strategy, data_files, passes, window, starting_equity):
    pass_results = []
    all_assets = []

    for pass_number in range(1, passes + 1):
        assets = []
        for data_file in data_files:
            candles = load_candles(data_file)
            if len(candles) <= window + 1:
                continue
            result = run_backtest(candles, strategy, window, starting_equity)
            result["data_file"] = str(data_file)
            result["pass"] = pass_number
            assets.append(result)
            all_assets.append(result)

        pass_results.append({
            "pass": pass_number,
            "summary": summarize_results(assets),
            "assets": assets,
        })

    return {
        "strategy": getattr(strategy, "name", strategy.__class__.__name__),
        "strategy_generation": getattr(strategy, "generation", None),
        "passes": pass_results,
        "summary": summarize_results(all_assets),
    }


def build_verdict(baseline_summary, candidate_summary, args):
    improved_accuracy = candidate_summary["accuracy"] - baseline_summary["accuracy"]
    improved_error = baseline_summary["avg_return_error"] - candidate_summary["avg_return_error"]
    improved_equity = candidate_summary["ending_equity_total"] - baseline_summary["ending_equity_total"]
    drawdown_change = baseline_summary["max_drawdown_pct"] - candidate_summary["max_drawdown_pct"]
    mistake_change = baseline_summary["mistake_count"] - candidate_summary["mistake_count"]

    reasons = []
    if improved_accuracy >= args.min_accuracy_delta:
        reasons.append(f"accuracy +{improved_accuracy:.4f}")
    if improved_error >= args.min_error_delta:
        reasons.append(f"avg_return_error -{improved_error:.4f}")
    if improved_equity >= args.min_equity_delta:
        reasons.append(f"ending_equity +{improved_equity:.2f}")
    if drawdown_change >= -args.max_drawdown_regression:
        reasons.append(f"max_drawdown change {drawdown_change:.4f}")
    if mistake_change > 0:
        reasons.append(f"mistakes -{mistake_change}")

    candidate_is_worse = (
        improved_accuracy < 0
        or improved_error < -args.max_error_regression
        or improved_equity < -args.max_equity_regression
        or drawdown_change < -args.max_drawdown_regression
    )

    promotes = (
        improved_accuracy >= args.min_accuracy_delta
        and improved_error >= args.min_error_delta
        and improved_equity >= args.min_equity_delta
        and drawdown_change >= -args.max_drawdown_regression
    )

    if promotes:
        verdict = "promote_candidate"
    elif candidate_is_worse:
        verdict = "reject_candidate"
    else:
        verdict = "hold_for_review"

    return {
        "verdict": verdict,
        "reasons": reasons,
        "deltas": {
            "accuracy": improved_accuracy,
            "avg_return_error": improved_error,
            "ending_equity_total": improved_equity,
            "max_drawdown_pct": drawdown_change,
            "mistake_count": mistake_change,
        },
    }


def compare_strategies(args):
    data_files = discover_data_files(args.data_dir, args.pattern)
    if not data_files:
        raise SystemExit(f"No historical CSV files found in {args.data_dir} matching {args.pattern}.")

    baseline = evaluate_strategy(BaselineStrategy(), data_files, args.passes, args.window, args.starting_equity)
    candidate = evaluate_strategy(load_strategy_from_file(args.candidate), data_files, args.passes, args.window, args.starting_equity)
    verdict = build_verdict(baseline["summary"], candidate["summary"], args)

    return {
        "data_dir": str(Path(args.data_dir)),
        "pattern": args.pattern,
        "data_files": [str(path) for path in data_files],
        "baseline": baseline,
        "candidate": candidate,
        "verdict": verdict,
    }


def main():
    load_repo_env()
    parser = argparse.ArgumentParser(description="Compare baseline and candidate strategy performance.")
    parser.add_argument("--data-dir", default="data/fixtures")
    parser.add_argument("--pattern", default="*.csv")
    parser.add_argument("--candidate", default="lab/candidates/strategy_candidate.py")
    parser.add_argument("--passes", type=int, default=3)
    parser.add_argument("--window", type=int, default=5)
    parser.add_argument("--starting-equity", type=float, default=10000)
    parser.add_argument("--report", default="run/latest_comparison_report.json")
    parser.add_argument("--min-accuracy-delta", type=float, default=0.01)
    parser.add_argument("--min-error-delta", type=float, default=0.01)
    parser.add_argument("--min-equity-delta", type=float, default=1.0)
    parser.add_argument("--max-drawdown-regression", type=float, default=0.25)
    parser.add_argument("--max-error-regression", type=float, default=0.02)
    parser.add_argument("--max-equity-regression", type=float, default=5.0)
    args = parser.parse_args()

    report = compare_strategies(args)
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["verdict"], indent=2))


if __name__ == "__main__":
    main()
