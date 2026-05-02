import os
from pathlib import Path

from strategy_registry import (
    ACTIVE_GENERATION_ENV,
    generation_id_from_path,
    list_version_paths,
    load_strategy_module,
    read_active_config,
    relative_repo_path,
    resolve_active_generation,
    resolve_active_strategy_path,
)

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover - optional dependency in local dev
    psycopg = None
    dict_row = None


ROOT = Path(__file__).resolve().parents[1]


def db_support_status():
    if psycopg is None or dict_row is None:
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
        row_factory=dict_row,
    )


def generation_id_from_int(number):
    return f"g{int(number):04d}"


def selection_source():
    return "env_override" if os.getenv(ACTIVE_GENERATION_ENV, "").strip() else "config"


def strategy_metadata_from_path(path):
    path = Path(path)
    module = load_strategy_module(path, f"strategy_meta_{path.stem}")
    strategy_class = getattr(module, "Strategy", None)
    if strategy_class is None:
        raise ValueError(f"Strategy file does not export Strategy: {path}")
    strategy = strategy_class()
    return {
        "generation": getattr(strategy, "generation", None),
        "generation_id": generation_id_from_path(path),
        "name": getattr(strategy, "name", strategy.__class__.__name__),
        "strategy_path": relative_repo_path(path),
    }


def fallback_active_record():
    active_path = resolve_active_strategy_path()
    active_config = read_active_config()
    metadata = strategy_metadata_from_path(active_path)
    return {
        **metadata,
        "validation_status": "config_only",
        "approval_reason": None,
        "promoted_at": active_config.get("updated_at"),
        "is_active": True,
        "selection_source": selection_source(),
        "db_status": "fallback",
    }


def fallback_history(limit):
    active_generation_id = resolve_active_generation()
    items = []
    for path in sorted(list_version_paths(), reverse=True)[:limit]:
        metadata = strategy_metadata_from_path(path)
        items.append({
            **metadata,
            "validation_status": "config_only",
            "approval_reason": None,
            "promoted_at": None,
            "is_active": metadata["generation_id"] == active_generation_id,
            "selected": metadata["generation_id"] == active_generation_id,
        })
    return items


def fetch_db_generation(generation):
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT generation, validation_status, approval_reason, promoted_at,
                       strategy_path, is_active, baseline_metrics, candidate_metrics
                FROM strategy_generations
                WHERE generation = %s
                LIMIT 1
                """,
                (generation,),
            )
            return cur.fetchone()


def fetch_db_history(limit):
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT generation, validation_status, approval_reason, promoted_at,
                       strategy_path, is_active
                FROM strategy_generations
                ORDER BY generation DESC
                LIMIT %s
                """,
                (limit,),
            )
            return cur.fetchall()


def fetch_active_strategy_record():
    local = fallback_active_record()
    status = db_support_status()
    if not status["enabled"]:
        return local

    try:
        row = fetch_db_generation(local["generation"])
    except Exception:  # pragma: no cover - depends on runtime DB
        return local

    if not row:
        return local

    return {
        **local,
        "validation_status": row["validation_status"],
        "approval_reason": row["approval_reason"],
        "promoted_at": row["promoted_at"].isoformat() if row["promoted_at"] else local["promoted_at"],
        "is_active": row["is_active"],
        "baseline_metrics": row.get("baseline_metrics"),
        "candidate_metrics": row.get("candidate_metrics"),
        "db_status": "connected",
    }


def fetch_strategy_history(limit=10):
    active_generation_id = resolve_active_generation()
    status = db_support_status()
    if not status["enabled"]:
        return fallback_history(limit)

    try:
        rows = fetch_db_history(limit)
    except Exception:  # pragma: no cover - depends on runtime DB
        return fallback_history(limit)

    if not rows:
        return fallback_history(limit)

    items = []
    for row in rows:
        generation = row["generation"]
        generation_id = generation_id_from_int(generation)
        path_value = row["strategy_path"]
        name = f"strategy_{generation_id}"
        if path_value:
            try:
                meta = strategy_metadata_from_path(ROOT / path_value)
                name = meta["name"]
            except Exception:
                pass
        items.append({
            "generation": generation,
            "generation_id": generation_id,
            "name": name,
            "strategy_path": path_value,
            "validation_status": row["validation_status"],
            "approval_reason": row["approval_reason"],
            "promoted_at": row["promoted_at"].isoformat() if row["promoted_at"] else None,
            "is_active": row["is_active"],
            "selected": generation_id == active_generation_id,
        })
    return items


def fetch_db_decisions(limit):
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    d.id,
                    d.decision,
                    d.reason,
                    d.paper_equity,
                    d.created_at,
                    a.symbol,
                    p.candle_time,
                    p.predicted_direction,
                    p.actual_direction,
                    p.actual_return_pct,
                    p.was_correct
                FROM decisions d
                JOIN assets a ON a.id = d.asset_id
                LEFT JOIN predictions p ON p.id = d.prediction_id
                ORDER BY COALESCE(p.candle_time, d.created_at) DESC, d.id DESC
                LIMIT %s
                """,
                (limit,),
            )
            return cur.fetchall()


def fetch_db_mistakes(limit):
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    m.id,
                    m.mistake_type,
                    m.severity,
                    m.context,
                    m.created_at,
                    a.symbol
                FROM mistake_logs m
                JOIN assets a ON a.id = m.asset_id
                ORDER BY m.created_at DESC, m.id DESC
                LIMIT %s
                """,
                (limit,),
            )
            return cur.fetchall()


def fetch_recent_decisions(limit=20):
    status = db_support_status()
    if not status["enabled"]:
        return {"source": "local", "status": "fallback", "items": []}

    try:
        rows = fetch_db_decisions(limit)
    except Exception:  # pragma: no cover - runtime DB dependency
        return {"source": "local", "status": "fallback", "items": []}

    items = []
    for row in rows:
        timestamp = row["candle_time"] or row["created_at"]
        items.append(
            {
                "id": row["id"],
                "time": timestamp.isoformat() if timestamp else None,
                "symbol": row["symbol"],
                "decision": row["decision"],
                "reason": row["reason"],
                "paper_equity": float(row["paper_equity"]) if row["paper_equity"] is not None else None,
                "predicted_direction": row["predicted_direction"],
                "actual_direction": row["actual_direction"],
                "actual_return_pct": float(row["actual_return_pct"]) if row["actual_return_pct"] is not None else None,
                "was_correct": row["was_correct"],
            }
        )
    return {"source": "postgres", "status": "ok", "items": items}


def fetch_recent_mistakes(limit=20):
    status = db_support_status()
    if not status["enabled"]:
        return {"source": "local", "status": "fallback", "items": []}

    try:
        rows = fetch_db_mistakes(limit)
    except Exception:  # pragma: no cover - runtime DB dependency
        return {"source": "local", "status": "fallback", "items": []}

    items = []
    for row in rows:
        context = row["context"] if isinstance(row["context"], dict) else {}
        items.append(
            {
                "id": row["id"],
                "time": row["created_at"].isoformat() if row["created_at"] else context.get("time"),
                "symbol": row["symbol"],
                "mistake_type": row["mistake_type"],
                "severity": row["severity"],
                "title": context.get("mistake_type") or row["mistake_type"],
                "detail": context.get("reason")
                or context.get("detail")
                or f"{row['symbol']} {row['mistake_type']} ({row['severity']})",
                "context": context,
            }
        )
    return {"source": "postgres", "status": "ok", "items": items}
