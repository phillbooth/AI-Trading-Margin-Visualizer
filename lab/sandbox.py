import ast
import importlib.util
from pathlib import Path


BLOCKED_IMPORTS = {
    "os",
    "sys",
    "subprocess",
    "socket",
    "pathlib",
    "shutil",
    "requests",
    "httpx",
}


def validate_candidate_source(source):
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in BLOCKED_IMPORTS:
                    raise ValueError(f"Blocked import: {alias.name}")
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".")[0] in BLOCKED_IMPORTS:
                raise ValueError(f"Blocked import: {node.module}")

    class_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    if "Strategy" not in class_names:
        raise ValueError("Candidate must define a Strategy class.")
    return True


def load_candidate(path):
    spec = importlib.util.spec_from_file_location("candidate_strategy", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "Strategy"):
        raise ValueError("Candidate module does not export Strategy.")
    return module.Strategy()


def write_candidate(path, source):
    validate_candidate_source(source)
    candidate_path = Path(path)
    candidate_path.parent.mkdir(parents=True, exist_ok=True)
    candidate_path.write_text(source, encoding="utf-8")
    return candidate_path
