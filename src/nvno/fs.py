from __future__ import annotations

from pathlib import Path

from .file_policy import ensure_editor_file_supported

IGNORED_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    "dist",
    "build",
}


def is_ignored(path: Path) -> bool:
    return path.is_dir() and path.name in IGNORED_DIRS


def sorted_children(directory: Path) -> list[Path]:
    try:
        children = [path for path in directory.iterdir() if not is_ignored(path)]
    except OSError:
        return []
    return sorted(children, key=lambda path: (path.is_file(), path.name.lower()))


def read_text_for_editor(path: Path) -> str:
    ensure_editor_file_supported(path)
    return path.read_text(encoding="utf-8", errors="replace")
