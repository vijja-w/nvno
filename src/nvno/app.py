from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.timer import Timer
from textual.widgets import Static, TextArea, Tree

from .autosave import atomic_write_text
from .editor import Buffer
from .file_policy import UnsupportedEditorFileError, editor_file_policy
from .fs import read_text_for_editor
from .tabs import TabBar
from .theme import APP_CSS, EDITOR_THEME, language_for_path
from .tree import ProjectTree


class NvnoApp(App[None]):
    """A quiet terminal workspace with a tree, tabs, and autosaving editor."""

    CSS = APP_CSS

    BINDINGS = [
        Binding("ctrl+c", "quit", show=False, priority=True),
        Binding("ctrl+s", "save_now", show=False),
        Binding("ctrl+tab", "next_tab", show=False),
        Binding("escape", "focus_or_toggle_sidebar", show=False, priority=True),
        Binding("alt+1", "focus_or_toggle_sidebar", show=False, priority=True),
        Binding("meta+1", "focus_or_toggle_sidebar", show=False, priority=True),
        Binding("option+1", "focus_or_toggle_sidebar", show=False, priority=True),
        Binding("cmd+w", "close_active_tab", show=False, priority=True),
        Binding("meta+w", "close_active_tab", show=False, priority=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.project_root = Path.cwd().resolve()
        self.buffers: dict[Path, Buffer] = {}
        self.open_tabs: list[Path] = []
        self.active_path: Path | None = None
        self.loading_editor_text = False
        self.autosave_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="main"):
            yield ProjectTree(self.project_root, id="project-tree")
            with Vertical(id="right"):
                yield TabBar(id="tab-bar")
                yield TextArea.code_editor(
                    "",
                    id="editor",
                    soft_wrap=True,
                    theme=EDITOR_THEME,
                )
                yield Static("", id="blocked-file-pane")

    def on_mount(self) -> None:
        self.query_one("#editor", TextArea).display = False
        self.query_one("#blocked-file-pane", Static).display = False
        self.query_one("#right", Vertical).can_focus = True
        self._refresh_tabs()

    def on_tree_node_selected(self, event: Tree.NodeSelected[Path]) -> None:
        path = event.node.data
        if path is None:
            return
        if path.is_dir():
            event.node.toggle()
            if isinstance(event.control, ProjectTree):
                event.control.ensure_loaded(event.node)
        elif path.is_file():
            self.open_file(path)

    def on_tree_node_expanded(self, event: Tree.NodeExpanded[Path]) -> None:
        if isinstance(event.control, ProjectTree):
            event.control.ensure_loaded(event.node)

    def on_tab_bar_tab_selected(self, event: TabBar.TabSelected) -> None:
        self.switch_to(event.path)

    def on_tab_bar_tab_closed(self, event: TabBar.TabClosed) -> None:
        self.close_tab(event.path)

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if self.loading_editor_text or self.active_path is None:
            return
        if not self.buffers[self.active_path].editable:
            return

        buffer = self.buffers[self.active_path]
        buffer.text = event.text_area.text
        buffer.dirty = True
        self._schedule_autosave()

    def open_file(self, path: Path) -> None:
        path = path.resolve()
        if path in self.buffers:
            self.switch_to(path)
            return

        policy = editor_file_policy(path)
        if policy.can_open:
            try:
                buffer = Buffer(path=path, text=read_text_for_editor(path))
            except (OSError, UnsupportedEditorFileError) as exc:
                buffer = Buffer(path=path, text="", open_error=f"File cannot be opened: {exc}")
        else:
            buffer = Buffer(
                path=path,
                text="",
                open_error=policy.message or "File cannot be opened.",
            )
        self.buffers[path] = buffer
        self.open_tabs.append(path)
        self.switch_to(path)

    def switch_to(self, path: Path) -> None:
        path = path.resolve()
        if path not in self.buffers:
            return

        self._sync_active_editor_to_buffer()
        self.active_path = path
        buffer = self.buffers[path]
        if buffer.editable:
            self._load_editor_text(path, buffer.text)
        else:
            self._load_blocked_file(path, buffer.open_error or "File cannot be opened.")
        self._refresh_tabs()
        self.action_focus_editor()

    def action_save_now(self) -> None:
        self._sync_active_editor_to_buffer()
        self._save_dirty_buffers()
        self._refresh_tabs()

    def action_next_tab(self) -> None:
        if not self.open_tabs:
            return
        if self.active_path not in self.open_tabs:
            self.switch_to(self.open_tabs[0])
            return
        index = self.open_tabs.index(self.active_path)
        self.switch_to(self.open_tabs[(index + 1) % len(self.open_tabs)])

    def action_close_active_tab(self) -> None:
        if self.active_path is not None:
            self.close_tab(self.active_path)

    def action_focus_or_toggle_sidebar(self) -> None:
        tree = self.query_one("#project-tree", ProjectTree)
        if not tree.display:
            tree.display = True
            tree.focus()
        elif tree.has_focus:
            tree.display = False
            self.action_focus_editor()
        else:
            tree.focus()

    def action_focus_editor(self) -> None:
        editor = self.query_one("#editor", TextArea)
        if editor.display:
            editor.focus()
        else:
            self.query_one("#right", Vertical).focus()

    def close_tab(self, path: Path) -> None:
        path = path.resolve()
        if path not in self.buffers:
            return

        self._sync_active_editor_to_buffer()
        buffer = self.buffers[path]
        if buffer.dirty and not self._save_buffer(buffer):
            self._refresh_tabs()
            return

        was_active = path == self.active_path
        close_index = self.open_tabs.index(path)
        self.open_tabs.remove(path)
        self.buffers.pop(path, None)

        if not was_active:
            self._refresh_tabs()
            return

        if self.open_tabs:
            next_index = min(close_index, len(self.open_tabs) - 1)
            self.active_path = None
            self.switch_to(self.open_tabs[next_index])
        else:
            self.active_path = None
            self._clear_editor()
            self._refresh_tabs()

    def _load_editor_text(self, path: Path, text: str) -> None:
        editor = self.query_one("#editor", TextArea)
        blocked_pane = self.query_one("#blocked-file-pane", Static)
        editor.display = True
        blocked_pane.display = False
        self.loading_editor_text = True
        try:
            editor.language = language_for_path(path, editor.available_languages)
            editor.theme = EDITOR_THEME
            editor.load_text(text)
        finally:
            self.loading_editor_text = False

    def _load_blocked_file(self, path: Path, message: str) -> None:
        editor = self.query_one("#editor", TextArea)
        blocked_pane = self.query_one("#blocked-file-pane", Static)
        self.loading_editor_text = True
        try:
            editor.language = None
            editor.load_text("")
            editor.display = False
            blocked_pane.update(f"{path.name}\n\n{message}")
            blocked_pane.display = True
        finally:
            self.loading_editor_text = False

    def _clear_editor(self) -> None:
        editor = self.query_one("#editor", TextArea)
        blocked_pane = self.query_one("#blocked-file-pane", Static)
        self.loading_editor_text = True
        try:
            editor.language = None
            editor.load_text("")
            editor.display = False
            blocked_pane.update("")
            blocked_pane.display = False
        finally:
            self.loading_editor_text = False

    def _sync_active_editor_to_buffer(self) -> None:
        if self.active_path is None or self.active_path not in self.buffers:
            return
        buffer = self.buffers[self.active_path]
        if not buffer.editable:
            return
        editor = self.query_one("#editor", TextArea)
        if buffer.text != editor.text:
            buffer.text = editor.text
            buffer.dirty = True

    def _refresh_tabs(self) -> None:
        self.query_one("#tab-bar", TabBar).update_tabs(
            self.open_tabs,
            self.active_path,
            self.buffers,
        )

    def _schedule_autosave(self) -> None:
        if self.autosave_timer is not None:
            self.autosave_timer.stop()
        self.autosave_timer = self.set_timer(0.5, self._autosave_dirty_buffers)

    def _autosave_dirty_buffers(self) -> None:
        self._sync_active_editor_to_buffer()
        self._save_dirty_buffers()
        self._refresh_tabs()

    def _save_dirty_buffers(self) -> None:
        for buffer in self.buffers.values():
            if not buffer.editable or not buffer.dirty:
                continue
            self._save_buffer(buffer)

    def _save_buffer(self, buffer: Buffer) -> bool:
        if not buffer.editable:
            return True
        try:
            atomic_write_text(buffer.path, buffer.text)
        except Exception as exc:
            buffer.save_error = str(exc)
            return False
        else:
            buffer.dirty = False
            buffer.save_error = None
            return True
