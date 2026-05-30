from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Buffer:
    path: Path
    text: str
    dirty: bool = False
    save_error: str | None = None
