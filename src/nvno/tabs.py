from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, HorizontalScroll
from textual.events import MouseDown
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Static

from .editor import Buffer
from .theme import TAB_CSS


class CloseTab(Static):
    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(" x ", classes="close-tab")

    async def _on_mouse_down(self, event: MouseDown) -> None:
        if event.button in {1, 2}:
            event.stop()
            self.post_message(TabBar.TabClosed(self.path))


class FileTab(Static):
    def __init__(self, path: Path, label: str, *, active: bool, has_error: bool) -> None:
        classes = "file-tab"
        if active:
            classes += " active"
        if has_error:
            classes += " save-error"
            label = f"{label}!"
        self.path = path
        super().__init__(f" {label} ", classes=classes)

    async def _on_mouse_down(self, event: MouseDown) -> None:
        if event.button == 1:
            event.stop()
            self.post_message(TabBar.TabSelected(self.path))
        elif event.button == 2:
            event.stop()
            self.post_message(TabBar.TabClosed(self.path))


class TabItem(Horizontal):
    def __init__(self, path: Path, label: str, *, active: bool, has_error: bool) -> None:
        classes = "tab-item"
        if active:
            classes += " active"
        self.path = path
        self.label = label
        self.active = active
        self.has_error = has_error
        super().__init__(classes=classes)

    def compose(self) -> ComposeResult:
        yield FileTab(
            self.path,
            self.label,
            active=self.active,
            has_error=self.has_error,
        )
        yield CloseTab(self.path)


class TabBar(Widget):
    class TabSelected(Message):
        def __init__(self, path: Path) -> None:
            super().__init__()
            self.path = path

    class TabClosed(Message):
        def __init__(self, path: Path) -> None:
            super().__init__()
            self.path = path

    DEFAULT_CSS = TAB_CSS

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.paths: list[Path] = []
        self.active_path: Path | None = None
        self.buffers: dict[Path, Buffer] = {}

    def compose(self) -> ComposeResult:
        yield HorizontalScroll(id="tab-scroll")

    def update_tabs(
        self,
        paths: list[Path],
        active_path: Path | None,
        buffers: dict[Path, Buffer],
    ) -> None:
        self.paths = list(paths)
        self.active_path = active_path
        self.buffers = buffers
        scroll = self.query_one("#tab-scroll", HorizontalScroll)
        scroll.remove_children()
        for path in self.paths:
            buffer = self.buffers.get(path)
            scroll.mount(
                TabItem(
                    path,
                    path.name,
                    active=path == self.active_path,
                    has_error=bool(buffer and buffer.save_error),
                )
            )

    def on_mouse_down(self, event: MouseDown) -> None:
        if event.button not in {1, 2}:
            return

        widget = event.widget
        path = getattr(widget, "path", None)
        if not isinstance(path, Path):
            return

        if event.button == 2 or isinstance(widget, CloseTab):
            event.stop()
            self.post_message(self.TabClosed(path))
        elif isinstance(widget, FileTab):
            event.stop()
            self.post_message(self.TabSelected(path))
