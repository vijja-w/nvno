from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Buffer:
    path: Path
    text: str
    dirty: bool = False
    save_error: str | None = None
    open_error: str | None = None
    preview: bool = False

    @property
    def editable(self) -> bool:
        return self.open_error is None
