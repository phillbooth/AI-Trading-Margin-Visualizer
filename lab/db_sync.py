import os
import subprocess
from pathlib import Path

try:
    import psycopg
    from psycopg.types.json import Jsonb
except ImportError:  # pragma: no cover - optional dependency in local dev
    psycopg = None
    Jsonb = None


ROOT = Path(__file__).resolve().parents[1]


def db_support_status():
    if psycopg is None or Jsonb is None:
        return {"enabled": False, "reason": "psycopg_not_installed"}
    return {"enabled": True}


def connect():
    status = db_support_status()
    if not status["enabled"]:
        raise RuntimeError(status["reason"])

    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "neural_twin"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "password"),
    )


def current_git_commit():
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def sync_strategy_generation(manifest):
    status = db_support_status()
    if not status["enabled"]:
        return {
            "status": "skipped",
            "reason": status["reason"],
        }

    baseline = manifest.get("baseline_strategy", {})
    promoted = manifest.get("promoted_strategy", {})
    verdict = manifest.get("verdict", {})
    comparison_report = manifest.get("comparison_report_payload", {})
    approval_reason = "; ".join(verdict.get("reasons", [])) or verdict.get("verdict", "")

    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE strategy_generations SET is_active = FALSE WHERE is_active = TRUE"
                )
                cur.execute(
                    """
                    INSERT INTO strategy_generations (
                        generation,
                        git_commit_sha,
                        parent_generation,
                        prompt_summary,
                        validation_status,
                        baseline_metrics,
                        candidate_metrics,
                        approval_reason,
                        strategy_path,
                        candidate_snapshot_path,
                        comparison_report,
                        promotion_manifest,
                        source_provider,
                        is_active,
                        promoted_at
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (generation) DO UPDATE SET
                        git_commit_sha = EXCLUDED.git_commit_sha,
                        parent_generation = EXCLUDED.parent_generation,
                        prompt_summary = EXCLUDED.prompt_summary,
                        validation_status = EXCLUDED.validation_status,
                        baseline_metrics = EXCLUDED.baseline_metrics,
                        candidate_metrics = EXCLUDED.candidate_metrics,
                        approval_reason = EXCLUDED.approval_reason,
                        strategy_path = EXCLUDED.strategy_path,
                        candidate_snapshot_path = EXCLUDED.candidate_snapshot_path,
                        comparison_report = EXCLUDED.comparison_report,
                        promotion_manifest = EXCLUDED.promotion_manifest,
                        source_provider = EXCLUDED.source_provider,
                        is_active = EXCLUDED.is_active,
                        promoted_at = EXCLUDED.promoted_at
                    """,
                    (
                        promoted.get("generation"),
                        current_git_commit(),
                        baseline.get("generation"),
                        manifest.get("prompt_task"),
                        manifest.get("status", "promoted"),
                        Jsonb(comparison_report.get("baseline", {}).get("summary", {})),
                        Jsonb(comparison_report.get("candidate", {}).get("summary", {})),
                        approval_reason,
                        manifest.get("active_config", {}).get("strategy_path") or manifest.get("promoted_strategy_path"),
                        manifest.get("candidate_snapshot_path"),
                        Jsonb(comparison_report),
                        Jsonb(manifest),
                        manifest.get("source_provider") or os.getenv("LLM_PROVIDER", ""),
                        True,
                        manifest.get("promoted_at"),
                    ),
                )
            conn.commit()
    except Exception as error:  # pragma: no cover - depends on runtime DB
        return {
            "status": "failed",
            "error": str(error),
        }

    return {
        "status": "synced",
        "generation": promoted.get("generation"),
    }
