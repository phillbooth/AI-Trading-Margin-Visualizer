from pathlib import Path
import sys

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from strategy_registry import load_active_strategy_class, resolve_active_generation, resolve_active_strategy_path


ACTIVE_GENERATION = resolve_active_generation()
ACTIVE_STRATEGY_PATH = resolve_active_strategy_path()
Strategy = load_active_strategy_class()
