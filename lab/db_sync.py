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


def get_or_create_asset_id(cur, symbol, asset_type="STOCK", quote_currency="USD"):
    cur.execute(
        """
        INSERT INTO assets (symbol, name, asset_type, quote_currency)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (symbol) DO UPDATE SET
            asset_type = EXCLUDED.asset_type,
            quote_currency = COALESCE(assets.quote_currency, EXCLUDED.quote_currency)
        RETURNING id
        """,
        (symbol, symbol, asset_type, quote_currency),
    )
    return cur.fetchone()[0]


def normalize_strategy_generation(value, fallback=1):
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(fallback)


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


def sync_training_report(report):
    status = db_support_status()
    if not status["enabled"]:
        return {
            "status": "skipped",
            "reason": status["reason"],
        }

    created_at = report.get("created_at")
    prediction_rows = 0
    decision_rows = 0
    mistake_rows = 0
    backtest_rows = 0

    try:
        with connect() as conn:
            with conn.cursor() as cur:
                for training_pass in report.get("passes", []):
                    pass_summary = training_pass.get("summary", {})
                    pass_number = pass_summary.get("pass")
                    for asset_result in training_pass.get("assets", []):
                        symbol = asset_result.get("symbol")
                        if not symbol:
                            continue
                        asset_id = get_or_create_asset_id(cur, symbol)
                        predictions = asset_result.get("predictions", [])
                        mistakes = asset_result.get("mistakes", [])
                        prediction_id_by_time = {}

                        for prediction in predictions:
                            signals = prediction.get("signals", {})
                            cur.execute(
                                """
                                INSERT INTO predictions (
                                    asset_id,
                                    strategy_generation,
                                    candle_time,
                                    horizon_candles,
                                    predicted_direction,
                                    predicted_return_pct,
                                    confidence,
                                    quant_score,
                                    neural_score,
                                    sentiment_score,
                                    actual_direction,
                                    actual_return_pct,
                                    was_correct
                                )
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                RETURNING id
                                """,
                                (
                                    asset_id,
                                    normalize_strategy_generation(prediction.get("strategy_generation"), report.get("strategy_generation", 1)),
                                    prediction.get("time"),
                                    1,
                                    prediction.get("predicted_direction"),
                                    float(prediction.get("predicted_return_pct", 0.0)),
                                    float(prediction.get("confidence", 0.0)),
                                    float(signals.get("quant", 0.0)),
                                    float(signals.get("neural", 0.0)),
                                    float(signals.get("sentiment", 0.0)),
                                    prediction.get("actual_direction"),
                                    float(prediction.get("actual_return_pct", 0.0)),
                                    bool(prediction.get("was_correct")),
                                ),
                            )
                            prediction_id = cur.fetchone()[0]
                            prediction_rows += 1
                            prediction_id_by_time[prediction.get("time")] = prediction_id

                            cur.execute(
                                """
                                INSERT INTO decisions (
                                    prediction_id,
                                    asset_id,
                                    decision,
                                    reason,
                                    paper_position_size,
                                    paper_equity
                                )
                                VALUES (%s, %s, %s, %s, %s, %s)
                                """,
                                (
                                    prediction_id,
                                    asset_id,
                                    prediction.get("decision"),
                                    prediction.get("reason"),
                                    None,
                                    float(prediction.get("paper_equity", 0.0)),
                                ),
                            )
                            decision_rows += 1

                        for mistake in mistakes:
                            prediction_id = prediction_id_by_time.get(mistake.get("time"))
                            cur.execute(
                                """
                                INSERT INTO mistake_logs (
                                    prediction_id,
                                    asset_id,
                                    mistake_type,
                                    severity,
                                    context
                                )
                                VALUES (%s, %s, %s, %s, %s)
                                """,
                                (
                                    prediction_id,
                                    asset_id,
                                    mistake.get("mistake_type", "unknown"),
                                    mistake.get("severity", "low"),
                                    Jsonb(mistake.get("context", {})),
                                ),
                            )
                            mistake_rows += 1

                        if predictions:
                            data_start = predictions[0].get("time")
                            data_end = predictions[-1].get("time")
                        else:
                            data_start = None
                            data_end = None

                        cur.execute(
                            """
                            INSERT INTO backtest_runs (
                                strategy_generation,
                                asset_id,
                                data_start,
                                data_end,
                                candle_count,
                                accuracy,
                                avg_return_error,
                                max_drawdown_pct,
                                metrics
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                normalize_strategy_generation(asset_result.get("strategy_generation"), report.get("strategy_generation", 1)),
                                asset_id,
                                data_start,
                                data_end,
                                int(asset_result.get("candle_count", 0)),
                                float(asset_result.get("accuracy", 0.0)),
                                float(asset_result.get("avg_return_error", 0.0)),
                                float(asset_result.get("max_drawdown_pct", 0.0)),
                                Jsonb({
                                    "report_created_at": created_at,
                                    "pass": pass_number,
                                    "data_file": asset_result.get("data_file"),
                                    "window": asset_result.get("window"),
                                    "prediction_count": asset_result.get("prediction_count", 0),
                                    "ending_equity": asset_result.get("ending_equity", 0.0),
                                }),
                            ),
                        )
                        backtest_rows += 1
            conn.commit()
    except Exception as error:  # pragma: no cover - runtime DB dependency
        return {
            "status": "failed",
            "error": str(error),
        }

    return {
        "status": "synced",
        "prediction_rows": prediction_rows,
        "decision_rows": decision_rows,
        "mistake_rows": mistake_rows,
        "backtest_rows": backtest_rows,
    }
