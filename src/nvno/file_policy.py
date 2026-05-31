from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

MAX_EDITOR_FILE_SIZE_BYTES = 1 * 1024 * 1024

IGNORED_FILE_SUFFIXES = {
    ".7z",
    ".avi",
    ".bmp",
    ".bz2",
    ".dmg",
    ".doc",
    ".docx",
    ".eot",
    ".exe",
    ".gif",
    ".gz",
    ".ico",
    ".jar",
    ".jpeg",
    ".jpg",
    ".mov",
    ".mp3",
    ".mp4",
    ".otf",
    ".pdf",
    ".png",
    ".ppt",
    ".pptx",
    ".pyc",
    ".rar",
    ".sqlite",
    ".tar",
    ".tgz",
    ".ttf",
    ".wav",
    ".webm",
    ".webp",
    ".woff",
    ".woff2",
    ".xls",
    ".xlsx",
    ".zip",
}


@dataclass(frozen=True)
class FileOpenPolicy:
    can_open: bool
    message: str | None = None


class UnsupportedEditorFileError(ValueError):
    pass


def editor_file_policy(path: Path) -> FileOpenPolicy:
    suffixes = {suffix.lower() for suffix in path.suffixes}
    ignored_suffixes = suffixes & IGNORED_FILE_SUFFIXES
    if ignored_suffixes:
        suffix = sorted(ignored_suffixes)[-1]
        return FileOpenPolicy(
            can_open=False,
            message=f"File type not supported ({suffix}).",
        )

    try:
        file_size = path.stat().st_size
    except OSError as exc:
        return FileOpenPolicy(can_open=False, message=f"File cannot be opened: {exc}")

    if file_size > MAX_EDITOR_FILE_SIZE_BYTES:
        return FileOpenPolicy(
            can_open=False,
            message=(
                "File is too large "
                f"({format_file_size(file_size)}; max {format_file_size(MAX_EDITOR_FILE_SIZE_BYTES)})."
            ),
        )

    return FileOpenPolicy(can_open=True)


def ensure_editor_file_supported(path: Path) -> None:
    policy = editor_file_policy(path)
    if not policy.can_open:
        raise UnsupportedEditorFileError(policy.message or "File cannot be opened.")


def format_file_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
