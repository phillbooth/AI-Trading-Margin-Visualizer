import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from benchmarks import (
    apply_benchmark_defaults,
    benchmark_name,
    build_contribution_filename,
    load_benchmark,
    normalize_symbols,
)
from db_sync import sync_training_report
from env_loader import load_repo_env

ROOT = Path(__file__).resolve().parents[1]
BRAIN_DIR = ROOT / "brain"
if str(BRAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BRAIN_DIR))

from backtest import load_candles, run_backtest, summarize_results  # noqa: E402
from strategy import Strategy  # noqa: E402


def resolve_repo_path(path_value):
    path = Path(path_value)
    return path if path.is_absolute() else ROOT / path


def discover_data_files(data_dir, pattern, symbols=None):
    files = sorted(Path(data_dir).glob(pattern))
    file_list = [path for path in files if path.is_file()]
    symbol_set = {symbol.upper() for symbol in (symbols or [])}
    if not symbol_set:
        return file_list
    return [path for path in file_list if path.stem.upper() in symbol_set]


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
        "benchmark": {
            "name": args.benchmark_name,
            "path": args.benchmark_path,
            "symbols": args.symbol_list,
        },
        "data_dir": str(Path(args.data_dir)),
        "pattern": args.pattern,
        "data_files": [str(path) for path in data_files],
        "window": args.window,
        "starting_equity": args.starting_equity,
        "final_summary": final_summary,
        "passes": passes,
        "mistakes": all_mistakes,
    }


def maybe_run_evolution(args, report, report_path):
    if report["final_summary"]["rewrite_recommendation"] != "queue_candidate":
        return None

    candidate_path = resolve_repo_path(args.candidate)
    comparison_path = resolve_repo_path(args.comparison_report)
    promotion_path = resolve_repo_path(args.promotion_report)

    evolver_cmd = [
        sys.executable,
        str(ROOT / "lab" / "evolver.py"),
        "--provider",
        args.provider,
        "--mistakes",
        str(report_path),
        "--strategy",
        str(ROOT / "brain" / "strategy.py"),
        "--candidate",
        str(candidate_path),
    ]
    subprocess.run(evolver_cmd, check=True, cwd=ROOT)

    compare_cmd = [
        sys.executable,
        str(ROOT / "lab" / "compare.py"),
        "--data-dir",
        args.data_dir,
        "--pattern",
        args.pattern,
        "--candidate",
        str(candidate_path),
        "--passes",
        str(args.passes),
        "--window",
        str(args.window),
        "--starting-equity",
        str(args.starting_equity),
        "--report",
        str(comparison_path.relative_to(ROOT)),
    ]
    if args.symbol_list:
        compare_cmd.extend(["--symbols", ",".join(args.symbol_list)])
    if args.benchmark_path:
        compare_cmd.extend(["--benchmark", args.benchmark_path])
    subprocess.run(compare_cmd, check=True, cwd=ROOT)

    comparison_data = json.loads(comparison_path.read_text(encoding="utf-8"))
    auto_evolution = {
        "candidate_path": str(candidate_path),
        "comparison_report": str(comparison_path),
        "verdict": comparison_data.get("verdict", {}),
    }

    verdict_name = auto_evolution["verdict"].get("verdict")
    if not args.auto_promote:
        auto_evolution["promotion"] = {
            "status": "skipped",
            "reason": "auto_promotion_disabled",
        }
        return auto_evolution

    if verdict_name != "promote_candidate":
        auto_evolution["promotion"] = {
            "status": "skipped",
            "reason": f"verdict_{verdict_name or 'unknown'}",
        }
        return auto_evolution

    promote_cmd = [
        sys.executable,
        str(ROOT / "lab" / "promote.py"),
        "--candidate",
        str(candidate_path),
        "--strategy",
        str(ROOT / "brain" / "strategy.py"),
        "--comparison-report",
        str(comparison_path),
        "--manifest",
        str(promotion_path),
        "--archive-dir",
        args.promotion_archive_dir,
    ]
    subprocess.run(promote_cmd, check=True, cwd=ROOT)
    auto_evolution["promotion"] = json.loads(promotion_path.read_text(encoding="utf-8"))
    return auto_evolution


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


def build_contribution_manifest(args, report):
    auto = report.get("auto_evolution", {})
    contribution = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "benchmark": {
            "name": args.benchmark_name or "ad_hoc",
            "path": args.benchmark_path,
            "symbols": args.symbol_list,
            "data_dir": args.data_dir,
            "pattern": args.pattern,
        },
        "strategy": {
            "name": report.get("strategy"),
            "generation": report.get("strategy_generation"),
        },
        "final_summary": report.get("final_summary", {}),
        "auto_evolution": {
            "candidate_path": auto.get("candidate_path"),
            "comparison_report": auto.get("comparison_report"),
            "verdict": auto.get("verdict"),
            "promotion": auto.get("promotion"),
        },
        "report_paths": {
            "training_report": str(resolve_repo_path(args.report)),
            "comparison_report": str(resolve_repo_path(args.comparison_report)),
            "promotion_report": str(resolve_repo_path(args.promotion_report)),
        },
    }
    return contribution


def maybe_write_contribution_manifest(args, report):
    if not args.write_contribution_manifest:
        return None

    contribution_dir = resolve_repo_path(args.contribution_dir)
    contribution_dir.mkdir(parents=True, exist_ok=True)
    filename = build_contribution_filename(
        "contribution",
        args.benchmark_name or "ad_hoc",
        report.get("strategy_generation"),
    )
    path = contribution_dir / filename
    manifest = build_contribution_manifest(args, report)
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return str(path)


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
    summary = {
        "passes": final["passes"],
        "prediction_count": final["prediction_count"],
        "accuracy": final["accuracy"],
        "mistake_count": final["mistake_count"],
        "max_drawdown_pct": final["max_drawdown_pct"],
        "rewrite_recommendation": final["rewrite_recommendation"],
    }
    auto_evolution = report.get("auto_evolution")
    if auto_evolution:
        summary["candidate_verdict"] = auto_evolution.get("verdict", {}).get("verdict")
        summary["promotion_status"] = auto_evolution.get("promotion", {}).get("status")
    if report.get("contribution_manifest"):
        summary["contribution_manifest"] = report["contribution_manifest"]
    print(json.dumps(summary, indent=2))


def main():
    load_repo_env()
    parser = argparse.ArgumentParser(description="Run repeated historical training passes across many assets.")
    parser.add_argument("--benchmark", default="")
    parser.add_argument("--data-dir", default="data/fixtures")
    parser.add_argument("--pattern", default="*.csv")
    parser.add_argument("--symbols", default="")
    parser.add_argument("--passes", type=int, default=3)
    parser.add_argument("--window", type=int, default=5)
    parser.add_argument("--starting-equity", type=float, default=10000)
    parser.add_argument("--report", default="run/latest_training_report.json")
    parser.add_argument("--provider", default=os.getenv("LLM_PROVIDER", "mock"))
    parser.add_argument("--candidate", default="lab/candidates/strategy_candidate.py")
    parser.add_argument("--comparison-report", default="run/latest_comparison_report.json")
    parser.add_argument("--promotion-report", default="run/latest_promotion_report.json")
    parser.add_argument("--promotion-archive-dir", default="run/promotions")
    parser.add_argument("--min-accuracy", type=float, default=0.52)
    parser.add_argument("--min-mistakes-for-rewrite", type=int, default=3)
    parser.add_argument("--max-drawdown-pct", type=float, default=12)
    parser.add_argument("--contribution-dir", default="run/contributions")
    parser.add_argument("--write-contribution-manifest", dest="write_contribution_manifest", action="store_true")
    parser.add_argument("--no-write-contribution-manifest", dest="write_contribution_manifest", action="store_false")
    parser.add_argument("--auto-promote", dest="auto_promote", action="store_true")
    parser.add_argument("--no-auto-promote", dest="auto_promote", action="store_false")
    parser.add_argument("--sync-db", dest="sync_db", action="store_true")
    parser.add_argument("--no-sync-db", dest="sync_db", action="store_false")
    parser.set_defaults(auto_promote=True, write_contribution_manifest=True, sync_db=True)
    args = parser.parse_args()

    args.benchmark_name = ""
    args.benchmark_path = ""
    if args.benchmark:
        benchmark = load_benchmark(args.benchmark)
        args = apply_benchmark_defaults(args, benchmark)
        args.benchmark_path = benchmark["_path"]
        if not args.benchmark_name:
            args.benchmark_name = benchmark_name(benchmark)

    args.symbol_list = normalize_symbols(args.symbols)
    data_files = discover_data_files(args.data_dir, args.pattern, args.symbol_list)
    if not data_files:
        symbol_note = f" for symbols {', '.join(args.symbol_list)}" if args.symbol_list else ""
        raise SystemExit(f"No historical CSV files found in {args.data_dir} matching {args.pattern}{symbol_note}.")

    report = build_training_report(args, data_files)
    report_path = resolve_repo_path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    auto_evolution = maybe_run_evolution(args, report, report_path)
    if auto_evolution:
        report["auto_evolution"] = auto_evolution
    if args.sync_db:
        report["db_sync"] = {
            "training_report": sync_training_report(report),
        }
    else:
        report["db_sync"] = {
            "training_report": {
                "status": "skipped",
                "reason": "disabled_by_flag",
            },
        }
    contribution_manifest_path = maybe_write_contribution_manifest(args, report)
    if contribution_manifest_path:
        report["contribution_manifest"] = contribution_manifest_path
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print_pass_summaries(report)


if __name__ == "__main__":
    main()
