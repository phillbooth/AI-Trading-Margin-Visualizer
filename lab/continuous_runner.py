import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from env_loader import load_repo_env

ROOT = Path(__file__).resolve().parents[1]


def now_utc():
    return datetime.now(timezone.utc)


def iso_now():
    return now_utc().isoformat()


def resolve_repo_path(path_value):
    path = Path(path_value)
    return path if path.is_absolute() else ROOT / path


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def print_process_output(result):
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)


def run_command(command, cwd):
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        encoding="utf-8",
    )
    print_process_output(result)
    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode,
            command,
            output=result.stdout,
            stderr=result.stderr,
        )
    return result


def acquire_lock(lock_path):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "pid": os.getpid(),
        "run_id": str(uuid.uuid4()),
        "created_at": iso_now(),
        "cwd": str(ROOT),
    }
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        descriptor = os.open(str(lock_path), flags)
    except FileExistsError as error:
        raise SystemExit(
            f"Continuous runner lock already exists at {lock_path}. "
            "Remove it only if you are sure no other continuous runner is active."
        ) from error

    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return payload


def release_lock(lock_path, lock_payload):
    if not lock_path.exists():
        return
    try:
        current = read_json(lock_path)
    except (OSError, json.JSONDecodeError):
        current = {}
    if current.get("run_id") == lock_payload.get("run_id"):
        lock_path.unlink(missing_ok=True)


def build_import_command(args):
    if not args.import_symbols:
        return None
    return [
        sys.executable,
        str(ROOT / "data" / "import_stocks.py"),
        "--symbols",
        args.import_symbols,
        "--years",
        str(args.import_years),
        "--out",
        args.import_out,
    ]


def build_trainer_command(args):
    command = [
        sys.executable,
        str(ROOT / "lab" / "trainer.py"),
        "--report",
        args.report,
        "--provider",
        args.provider,
        "--candidate",
        args.candidate,
        "--comparison-report",
        args.comparison_report,
        "--promotion-report",
        args.promotion_report,
        "--promotion-archive-dir",
        args.promotion_archive_dir,
        "--min-accuracy",
        str(args.min_accuracy),
        "--min-mistakes-for-rewrite",
        str(args.min_mistakes_for_rewrite),
        "--max-drawdown-pct",
        str(args.max_drawdown_pct),
    ]
    if args.benchmark:
        command.extend(["--benchmark", args.benchmark])
    else:
        command.extend([
            "--data-dir",
            args.data_dir,
            "--pattern",
            args.pattern,
            "--passes",
            str(args.passes),
            "--window",
            str(args.window),
            "--starting-equity",
            str(args.starting_equity),
        ])
        if args.symbols:
            command.extend(["--symbols", args.symbols])
    command.append("--auto-promote" if args.auto_promote else "--no-auto-promote")
    return command


def report_summary(report):
    final = report.get("final_summary", {})
    auto = report.get("auto_evolution", {})
    verdict = auto.get("verdict", {})
    promotion = auto.get("promotion", {})
    return {
        "strategy_generation": report.get("strategy_generation"),
        "prediction_count": final.get("prediction_count"),
        "accuracy": final.get("accuracy"),
        "mistake_count": final.get("mistake_count"),
        "max_drawdown_pct": final.get("max_drawdown_pct"),
        "rewrite_recommendation": final.get("rewrite_recommendation"),
        "candidate_verdict": verdict.get("verdict"),
        "candidate_reasons": verdict.get("reasons", []),
        "promotion_status": promotion.get("status"),
        "promotion_reason": promotion.get("reason"),
    }


def update_status(status_path, **fields):
    existing = {}
    if status_path.exists():
        try:
            existing = read_json(status_path)
        except (OSError, json.JSONDecodeError):
            existing = {}
    existing.update(fields)
    write_json(status_path, existing)


def sleep_with_status(args, status_path, seconds, state, message):
    next_run_at = (now_utc() + timedelta(seconds=seconds)).isoformat()
    update_status(
        status_path,
        state=state,
        message=message,
        sleeping_for_seconds=seconds,
        next_run_at=next_run_at,
        updated_at=iso_now(),
    )
    time.sleep(seconds)


def run_cycle(args, cycle_number, status_path):
    import_command = build_import_command(args)
    training_report_path = resolve_repo_path(args.report)

    update_status(
        status_path,
        cycle_number=cycle_number,
        state="starting_cycle",
        message=f"Starting cycle {cycle_number}.",
        updated_at=iso_now(),
        active_report_path=str(training_report_path),
    )

    if import_command:
        update_status(
            status_path,
            state="importing_data",
            message=f"Refreshing historical data for {args.import_symbols}.",
            last_import_command=import_command,
            updated_at=iso_now(),
        )
        run_command(import_command, cwd=ROOT)

    trainer_command = build_trainer_command(args)
    update_status(
        status_path,
        state="training",
        message=f"Running trainer cycle {cycle_number}.",
        last_trainer_command=trainer_command,
        updated_at=iso_now(),
    )
    run_command(trainer_command, cwd=ROOT)

    report = read_json(training_report_path)
    summary = report_summary(report)
    update_status(
        status_path,
        state="cycle_completed",
        message=f"Completed cycle {cycle_number}.",
        last_cycle_completed_at=iso_now(),
        last_report_summary=summary,
        updated_at=iso_now(),
    )
    return summary


def main():
    load_repo_env()
    parser = argparse.ArgumentParser(
        description="Run repeated historical training cycles until a stop file is created."
    )
    parser.add_argument("--benchmark", default=os.getenv("CONTINUOUS_BENCHMARK", ""))
    parser.add_argument("--data-dir", default=os.getenv("CONTINUOUS_DATA_DIR", "data/historical"))
    parser.add_argument("--pattern", default=os.getenv("CONTINUOUS_PATTERN", "*.csv"))
    parser.add_argument("--symbols", default=os.getenv("CONTINUOUS_SYMBOLS", ""))
    parser.add_argument("--passes", type=int, default=int(os.getenv("TRAINING_PASSES", "3")))
    parser.add_argument("--window", type=int, default=5)
    parser.add_argument("--starting-equity", type=float, default=10000)
    parser.add_argument("--report", default="run/continuous_latest_training_report.json")
    parser.add_argument("--provider", default=os.getenv("LLM_PROVIDER", "mock"))
    parser.add_argument("--candidate", default="lab/candidates/strategy_candidate.py")
    parser.add_argument("--comparison-report", default="run/continuous_latest_comparison_report.json")
    parser.add_argument("--promotion-report", default="run/continuous_latest_promotion_report.json")
    parser.add_argument("--promotion-archive-dir", default="run/promotions")
    parser.add_argument("--min-accuracy", type=float, default=0.52)
    parser.add_argument("--min-mistakes-for-rewrite", type=int, default=3)
    parser.add_argument("--max-drawdown-pct", type=float, default=float(os.getenv("MAX_DRAWDOWN_PCT", "12")))
    parser.add_argument("--auto-promote", dest="auto_promote", action="store_true")
    parser.add_argument("--no-auto-promote", dest="auto_promote", action="store_false")
    parser.set_defaults(auto_promote=True)
    parser.add_argument("--interval-seconds", type=int, default=int(os.getenv("CONTINUOUS_INTERVAL_SECONDS", "3600")))
    parser.add_argument(
        "--pause-poll-seconds",
        type=int,
        default=int(os.getenv("CONTINUOUS_PAUSE_POLL_SECONDS", "30")),
    )
    parser.add_argument(
        "--max-consecutive-failures",
        type=int,
        default=int(os.getenv("CONTINUOUS_MAX_CONSECUTIVE_FAILURES", "5")),
    )
    parser.add_argument("--max-cycles", type=int, default=0, help="0 means run until stopped.")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit.")
    parser.add_argument("--import-symbols", default=os.getenv("CONTINUOUS_IMPORT_SYMBOLS", ""))
    parser.add_argument("--import-years", type=int, default=int(os.getenv("CONTINUOUS_IMPORT_YEARS", "5")))
    parser.add_argument("--import-out", default=os.getenv("CONTINUOUS_IMPORT_OUT", "data/historical"))
    parser.add_argument("--lock-file", default="run/continuous.lock")
    parser.add_argument("--status-file", default="run/continuous_status.json")
    parser.add_argument("--stop-file", default="run/STOP")
    parser.add_argument("--pause-file", default="run/PAUSE")
    args = parser.parse_args()

    lock_path = resolve_repo_path(args.lock_file)
    status_path = resolve_repo_path(args.status_file)
    stop_path = resolve_repo_path(args.stop_file)
    pause_path = resolve_repo_path(args.pause_file)

    lock_payload = acquire_lock(lock_path)
    update_status(
        status_path,
        state="started",
        message="Continuous runner started.",
        started_at=iso_now(),
        updated_at=iso_now(),
        pid=os.getpid(),
        run_id=lock_payload["run_id"],
        benchmark=args.benchmark,
        data_dir=str(resolve_repo_path(args.data_dir)),
        provider=args.provider,
        interval_seconds=args.interval_seconds,
        stop_file=str(stop_path),
        pause_file=str(pause_path),
        lock_file=str(lock_path),
    )

    cycle_number = 0
    consecutive_failures = 0
    exit_code = 0

    try:
        while True:
            if stop_path.exists():
                update_status(
                    status_path,
                    state="stopped",
                    message=f"Stop file detected at {stop_path}.",
                    stopped_at=iso_now(),
                    updated_at=iso_now(),
                )
                break

            if pause_path.exists():
                sleep_with_status(
                    args,
                    status_path,
                    args.pause_poll_seconds,
                    state="paused",
                    message=f"Pause file detected at {pause_path}. Waiting.",
                )
                continue

            if args.max_cycles and cycle_number >= args.max_cycles:
                update_status(
                    status_path,
                    state="completed",
                    message=f"Reached max cycles ({args.max_cycles}).",
                    completed_at=iso_now(),
                    updated_at=iso_now(),
                )
                break

            cycle_number += 1

            try:
                summary = run_cycle(args, cycle_number, status_path)
            except Exception as error:
                consecutive_failures += 1
                update_status(
                    status_path,
                    state="failed_cycle",
                    message=f"Cycle {cycle_number} failed: {error}",
                    last_error=str(error),
                    consecutive_failures=consecutive_failures,
                    updated_at=iso_now(),
                )
                if consecutive_failures >= args.max_consecutive_failures:
                    update_status(
                        status_path,
                        state="stopped_on_failures",
                        message=(
                            "Stopping continuous runner after reaching the consecutive failure limit "
                            f"({args.max_consecutive_failures})."
                        ),
                        stopped_at=iso_now(),
                        updated_at=iso_now(),
                    )
                    exit_code = 1
                    break
                if args.once:
                    exit_code = 1
                    break
                sleep_with_status(
                    args,
                    status_path,
                    args.interval_seconds,
                    state="sleeping_after_failure",
                    message=f"Sleeping after failed cycle {cycle_number}.",
                )
                continue

            consecutive_failures = 0
            update_status(
                status_path,
                state="cycle_completed",
                message=f"Cycle {cycle_number} completed.",
                consecutive_failures=0,
                last_cycle_summary=summary,
                updated_at=iso_now(),
            )

            if args.once:
                update_status(
                    status_path,
                    state="completed",
                    message="Continuous runner completed one cycle because --once was set.",
                    completed_at=iso_now(),
                    updated_at=iso_now(),
                )
                break

            sleep_with_status(
                args,
                status_path,
                args.interval_seconds,
                state="sleeping",
                message=f"Sleeping after cycle {cycle_number}.",
            )
    finally:
        release_lock(lock_path, lock_payload)

    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
