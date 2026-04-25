import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def resolve_repo_path(path_value):
    path = Path(path_value)
    return path if path.is_absolute() else ROOT / path


def load_benchmark(path_value):
    path = resolve_repo_path(path_value)
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"Benchmark file must contain a JSON object: {path}")
    payload["_path"] = str(path)
    return payload


def benchmark_name(benchmark):
    return benchmark.get("name") or Path(benchmark.get("_path", "benchmark")).stem


def benchmark_symbols(benchmark):
    symbols = benchmark.get("symbols", [])
    if not isinstance(symbols, list):
        raise ValueError("Benchmark 'symbols' must be a list.")
    return [str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()]


def apply_benchmark_defaults(args, benchmark):
    mappings = {
        "data_dir": "data_dir",
        "pattern": "pattern",
        "passes": "passes",
        "window": "window",
        "starting_equity": "starting_equity",
        "min_accuracy": "min_accuracy",
        "min_mistakes_for_rewrite": "min_mistakes_for_rewrite",
        "max_drawdown_pct": "max_drawdown_pct",
        "provider": "provider",
        "candidate": "candidate",
        "comparison_report": "comparison_report",
        "promotion_report": "promotion_report",
        "promotion_archive_dir": "promotion_archive_dir",
        "contribution_dir": "contribution_dir",
        "auto_promote": "auto_promote",
    }

    for benchmark_key, arg_name in mappings.items():
        if benchmark_key in benchmark:
            setattr(args, arg_name, benchmark[benchmark_key])

    if benchmark.get("symbols"):
        args.symbols = ",".join(benchmark_symbols(benchmark))

    args.benchmark_name = benchmark_name(benchmark)
    return args


def normalize_symbols(symbols_value):
    if not symbols_value:
        return []
    if isinstance(symbols_value, str):
        return [symbol.strip().upper() for symbol in symbols_value.split(",") if symbol.strip()]
    if isinstance(symbols_value, list):
        return [str(symbol).strip().upper() for symbol in symbols_value if str(symbol).strip()]
    raise ValueError("Symbols must be a comma-separated string or a list.")


def build_contribution_filename(prefix, benchmark_name_value, generation, created_at=None):
    timestamp = created_at or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    benchmark_part = benchmark_name_value or "ad_hoc"
    generation_part = f"g{int(generation):04d}" if generation is not None else "g_unknown"
    return f"{prefix}_{benchmark_part}_{generation_part}_{timestamp}.json"
