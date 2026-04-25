import ast
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from db_sync import sync_strategy_generation
from env_loader import load_repo_env
from sandbox import load_candidate, validate_candidate_source

ROOT = Path(__file__).resolve().parents[1]
BRAIN_DIR = ROOT / "brain"
if str(BRAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BRAIN_DIR))

from strategy_registry import (  # noqa: E402
    ACTIVE_GENERATION_ENV,
    generation_id_from_path,
    generation_number_from_id,
    next_generation_id,
    relative_repo_path,
    resolve_strategy_source_path,
    version_path_for_generation,
    write_active_config,
)


def resolve_repo_path(path_value):
    path = Path(path_value)
    return path if path.is_absolute() else ROOT / path


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def read_strategy_metadata(path):
    strategy = load_candidate(path)
    generation_id = ""
    path = Path(path).resolve()
    try:
        generation_id = generation_id_from_path(path)
    except ValueError:
        generation = getattr(strategy, "generation", None)
        if generation is not None:
            generation_id = f"g{int(generation):04d}"
    return {
        "path": str(path),
        "name": getattr(strategy, "name", strategy.__class__.__name__),
        "generation": getattr(strategy, "generation", None),
        "generation_id": generation_id,
    }


def source_for_promoted_generation(source, generation_id):
    generation_number = generation_number_from_id(generation_id)
    tree = ast.parse(source)

    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != "Strategy":
            continue
        for statement in node.body:
            if not isinstance(statement, ast.Assign):
                continue
            for target in statement.targets:
                if isinstance(target, ast.Name) and target.id == "generation":
                    statement.value = ast.Constant(generation_number)
                    ast.fix_missing_locations(tree)
                    return ast.unparse(tree) + "\n"

        node.body.insert(
            0,
            ast.Assign(
                targets=[ast.Name(id="generation", ctx=ast.Store())],
                value=ast.Constant(generation_number),
            ),
        )
        ast.fix_missing_locations(tree)
        return ast.unparse(tree) + "\n"

    raise ValueError("Candidate module does not define a Strategy class.")


def promote_candidate(candidate_path, strategy_path, comparison_report_path, manifest_path, archive_dir):
    comparison_report_path = resolve_repo_path(comparison_report_path)
    comparison_report = load_json(comparison_report_path)
    verdict = comparison_report.get("verdict", {})
    verdict_name = verdict.get("verdict")
    if verdict_name != "promote_candidate":
        raise ValueError(f"Refusing to promote candidate because verdict is {verdict_name!r}.")

    candidate_path = resolve_repo_path(candidate_path)
    strategy_path = resolve_strategy_source_path(strategy_path)
    manifest_path = resolve_repo_path(manifest_path)
    archive_dir = resolve_repo_path(archive_dir)

    if not candidate_path.exists():
        raise FileNotFoundError(f"Candidate strategy not found: {candidate_path}")
    if not strategy_path.exists():
        raise FileNotFoundError(f"Current strategy not found: {strategy_path}")

    candidate_source = candidate_path.read_text(encoding="utf-8")
    current_source = strategy_path.read_text(encoding="utf-8")
    promoted_generation = next_generation_id()
    promoted_strategy_path = version_path_for_generation(promoted_generation)
    if promoted_strategy_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing promoted strategy: {promoted_strategy_path}")

    validate_candidate_source(candidate_source)
    promoted_source = source_for_promoted_generation(candidate_source, promoted_generation)
    validate_candidate_source(promoted_source)

    current_meta = read_strategy_metadata(strategy_path)
    candidate_meta = read_strategy_metadata(candidate_path)

    archive_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    promoted_strategy_path.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = archive_dir / f"{timestamp}_{current_meta['generation_id'] or 'active'}_backup.py"
    candidate_snapshot_path = archive_dir / f"{timestamp}_{promoted_generation}_candidate_input.py"

    backup_path.write_text(current_source, encoding="utf-8")
    candidate_snapshot_path.write_text(candidate_source, encoding="utf-8")
    promoted_strategy_path.write_text(promoted_source, encoding="utf-8")
    active_config = write_active_config(promoted_generation, promoted_strategy_path)
    promoted_meta = read_strategy_metadata(promoted_strategy_path)

    manifest = {
        "status": "promoted",
        "promoted_at": datetime.now(timezone.utc).isoformat(),
        "strategy_loader_path": relative_repo_path(resolve_repo_path("brain/strategy.py")),
        "active_strategy_path_before": str(strategy_path),
        "promoted_strategy_path": str(promoted_strategy_path),
        "candidate_path": str(candidate_path),
        "comparison_report": str(comparison_report_path),
        "backup_path": str(backup_path),
        "candidate_snapshot_path": str(candidate_snapshot_path),
        "baseline_strategy": current_meta,
        "candidate_strategy_input": candidate_meta,
        "promoted_strategy": promoted_meta,
        "active_config": active_config,
        "env_override_generation": normalize_env_override(),
        "comparison_report_payload": comparison_report,
        "verdict": verdict,
    }
    manifest["db_sync"] = sync_strategy_generation(manifest)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def normalize_env_override():
    return os.getenv(ACTIVE_GENERATION_ENV, "").strip()


def main():
    load_repo_env()
    parser = argparse.ArgumentParser(description="Promote a candidate strategy after a passing comparison verdict.")
    parser.add_argument("--candidate", default="lab/candidates/strategy_candidate.py")
    parser.add_argument("--strategy", default="brain/strategy.py")
    parser.add_argument("--comparison-report", default="run/latest_comparison_report.json")
    parser.add_argument("--manifest", default="run/latest_promotion_report.json")
    parser.add_argument("--archive-dir", default="run/promotions")
    args = parser.parse_args()

    result = promote_candidate(
        candidate_path=args.candidate,
        strategy_path=args.strategy,
        comparison_report_path=args.comparison_report,
        manifest_path=args.manifest,
        archive_dir=args.archive_dir,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
