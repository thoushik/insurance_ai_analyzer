"""
Folder-safety: all paths MUST stay inside project root.
NEVER modify, delete, or access files outside this folder.
"""
from pathlib import Path

# Project root = directory containing this package's app folder
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

def get_project_root() -> Path:
    """Return the project root; all operations must stay under this."""
    return _PROJECT_ROOT

def resolve_local_path(relative_path: str) -> Path:
    """Resolve a path strictly inside project root. Raises if outside."""
    root = get_project_root()
    resolved = (root / relative_path).resolve()
    if not str(resolved).startswith(str(root)):
        raise PermissionError("Path must be inside project folder only.")
    return resolved

# Standard subfolders (all inside project only)
def get_venv_dir() -> Path:
    return get_project_root() / "venv"

def get_data_dir() -> Path:
    return get_project_root() / "data"

def get_logs_dir() -> Path:
    return get_project_root() / "logs"

def get_cache_dir() -> Path:
    return get_project_root() / "cache"

def get_db_path() -> Path:
    return get_project_root() / "data" / "local.db"
