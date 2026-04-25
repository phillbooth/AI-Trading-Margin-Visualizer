import importlib.util
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path


BRAIN_DIR = Path(__file__).resolve().parent
ROOT = BRAIN_DIR.parent
VERSIONS_DIR = BRAIN_DIR / "versions"
ACTIVE_CONFIG_PATH = ROOT / "config" / "active_strategy.json"
ACTIVE_GENERATION_ENV = "ACTIVE_STRATEGY_GENERATION"
DEFAULT_GENERATION_ID = "g0001"
GENERATION_PATTERN = re.compile(r"^g?(\d+)$")
VERSION_FILE_PATTERN = re.compile(r"^strategy_(g\d{4})\.py$")


def normalize_generation_id(value):
    text = str(value or "").strip().lower()
    if not text:
        return ""
    match = GENERATION_PATTERN.fullmatch(text)
    if not match:
        raise ValueError(f"Invalid strategy generation value: {value!r}")
    return f"g{int(match.group(1)):04d}"


def generation_number_from_id(generation_id):
    return int(normalize_generation_id(generation_id)[1:])


def version_path_for_generation(generation_id):
    return VERSIONS_DIR / f"strategy_{normalize_generation_id(generation_id)}.py"


def relative_repo_path(path):
    try:
        return str(Path(path).resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(Path(path).resolve())


def read_active_config():
    if not ACTIVE_CONFIG_PATH.exists():
        return {}
    return json.loads(ACTIVE_CONFIG_PATH.read_text(encoding="utf-8-sig"))


def resolve_active_generation():
    override = normalize_generation_id(os.getenv(ACTIVE_GENERATION_ENV, ""))
    if override:
        return override

    config = read_active_config()
    configured = normalize_generation_id(config.get("active_generation", ""))
    if configured:
        return configured

    return DEFAULT_GENERATION_ID


def resolve_active_strategy_path():
    path = version_path_for_generation(resolve_active_generation())
    if not path.exists():
        raise FileNotFoundError(f"Active strategy file not found: {path}")
    return path


def resolve_strategy_source_path(path_value):
    if not path_value:
        return resolve_active_strategy_path()

    path = Path(path_value)
    if not path.is_absolute():
        path = ROOT / path

    loader_path = BRAIN_DIR / "strategy.py"
    if path.resolve() == loader_path.resolve():
        return resolve_active_strategy_path()
    return path


def list_version_paths():
    return sorted(path for path in VERSIONS_DIR.glob("strategy_g*.py") if path.is_file())


def generation_id_from_path(path):
    match = VERSION_FILE_PATTERN.fullmatch(Path(path).name)
    if not match:
        raise ValueError(f"Unrecognized strategy version filename: {path}")
    return match.group(1)


def next_generation_id():
    versions = list_version_paths()
    if not versions:
        return DEFAULT_GENERATION_ID
    latest = max(generation_number_from_id(generation_id_from_path(path)) for path in versions)
    return f"g{latest + 1:04d}"


def write_active_config(generation_id, strategy_path):
    generation_id = normalize_generation_id(generation_id)
    ACTIVE_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "active_generation": generation_id,
        "strategy_path": relative_repo_path(strategy_path),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    ACTIVE_CONFIG_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def load_strategy_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load strategy module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_active_strategy_class():
    generation_id = resolve_active_generation()
    module = load_strategy_module(resolve_active_strategy_path(), f"active_strategy_{generation_id}")
    if not hasattr(module, "Strategy"):
        raise ValueError("Active strategy module does not export Strategy.")
    return module.Strategy

