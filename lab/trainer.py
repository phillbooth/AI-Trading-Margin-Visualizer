import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from env_loader import load_repo_env

ROOT = Path(__file__).resolve().parents[1]
BRAIN_DIR = ROOT / "brain"
if str(BRAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BRAIN_DIR))

from backtest import load_candles, run_backtest, summarize_results  # noqa: E402
from strategy import Strategy  # noqa: E402


def discover_data_files(data_dir, pattern):
    files = sorted(Path(data_dir).glob(pattern))
    return [path for path in files if path.is_file()]


def report_checkpoint(pass_number, results):
    summary = summarize_results(results)
    summary["pass"] = pass_number
    summary["symbols"] = [result["symbol"] for result in results]
    return summary


def build_training_report(args, data_files):
    strategy = Strategy()
    passes = []
    all_mistakes = []

    for pass_number in range(1, args.passes + 1):
        pass_results = []
        for data_file in data_files:
            candles = load_candles(data_file)
            if len(candles) <= args.window + 1:
                continue
            result = run_backtest(candles, strategy, args.window, args.starting_equity)
            result["data_file"] = str(data_file)
            result["pass"] = pass_number
            pass_results.append(result)
            all_mistakes.extend({
                "pass": pass_number,
                "data_file": str(data_file),
                **mistake,
            } for mistake in result["mistakes"])

        passes.append({
            "summary": report_checkpoint(pass_number, pass_results),
            "assets": pass_results,
        })

    final_summary = summarize_results([
        asset
        for training_pass in passes
        for asset in training_pass["assets"]
    ])
    final_summary["passes"] = args.passes
    final_summary["rewrite_recommendation"] = rewrite_recommendation(final_summary, args)

    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "strategy": strategy.name,
        "strategy_generation": strategy.generation,
        "data_dir": str(Path(args.data_dir)),
        "pattern": args.pattern,
        "data_files": [str(path) for path in data_files],
        "window": args.window,
        "starting_equity": args.starting_equity,
        "final_summary": final_summary,
        "passes": passes,
        "mistakes": all_mistakes,
    }


def rewrite_recommendation(summary, args):
    if summary["prediction_count"] == 0:
        return "no_data"
    if summary["mistake_count"] >= args.min_mistakes_for_rewrite:
        return "queue_candidate"
    if summary["accuracy"] < args.min_accuracy:
        return "queue_candidate"
    if summary["max_drawdown_pct"] > args.max_drawdown_pct:
        return "queue_candidate"
    return "hold_current_strategy"


def print_pass_summaries(report):
    for training_pass in report["passes"]:
        summary = training_pass["summary"]
        print(
            f"pass {summary['pass']}: "
            f"assets={summary['asset_count']} "
            f"predictions={summary['prediction_count']} "
            f"accuracy={summary['accuracy']:.3f} "
            f"mistakes={summary['mistake_count']} "
            f"max_drawdown={summary['max_drawdown_pct']:.2f}%"
        )

    final = report["final_summary"]
    print(json.dumps({
        "passes": final["passes"],
        "prediction_count": final["prediction_count"],
        "accuracy": final["accuracy"],
        "mistake_count": final["mistake_count"],
        "max_drawdown_pct": final["max_drawdown_pct"],
        "rewrite_recommendation": final["rewrite_recommendation"],
    }, indent=2))


def main():
    load_repo_env()
    parser = argparse.ArgumentParser(description="Run repeated historical training passes across many assets.")
    parser.add_argument("--data-dir", default="data/fixtures")
    parser.add_argument("--pattern", default="*.csv")
    parser.add_argument("--passes", type=int, default=3)
    parser.add_argument("--window", type=int, default=5)
    parser.add_argument("--starting-equity", type=float, default=10000)
    parser.add_argument("--report", default="run/latest_training_report.json")
    parser.add_argument("--min-accuracy", type=float, default=0.52)
    parser.add_argument("--min-mistakes-for-rewrite", type=int, default=3)
    parser.add_argument("--max-drawdown-pct", type=float, default=12)
    args = parser.parse_args()

    data_files = discover_data_files(args.data_dir, args.pattern)
    if not data_files:
        raise SystemExit(f"No historical CSV files found in {args.data_dir} matching {args.pattern}.")

    report = build_training_report(args, data_files)
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print_pass_summaries(report)


if __name__ == "__main__":
    main()
