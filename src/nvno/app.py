from __future__ import annotations

import os
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.events import MouseDown
from textual.message import Message
from textual.css.query import NoMatches
from textual.timer import Timer
from textual.widgets import Markdown, Static, TextArea, Tree

from .autosave import atomic_write_text
from .editor import Buffer
from .file_policy import UnsupportedEditorFileError, editor_file_policy
from .fs import is_ignored, read_text_for_editor
from .tabs import TabBar
from .theme import APP_CSS, EDITOR_THEME, is_markdown_path, language_for_path
from .tree import DirectoryRefreshButton, ProjectTree

FileIdentity = tuple[int, int]


class MarkdownPreviewToggle(Static):
    class Pressed(Message):
        pass

    def __init__(self, **kwargs: object) -> None:
        super().__init__("Preview", **kwargs)

    async def _on_mouse_down(self, event: MouseDown) -> None:
        if event.button != 1:
            return
        event.stop()
        self.post_message(self.Pressed())

    def set_previewing(self, previewing: bool) -> None:
        self.update("Edit" if previewing else "Preview")
        self.set_class(previewing, "active")


class MarkdownPreview(Markdown):
    can_focus = True


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

    def __init__(
        self,
        project_root: Path | None = None,
        initial_path: Path | None = None,
    ) -> None:
        super().__init__()
        self.project_root = (project_root or Path.cwd()).expanduser().resolve()
        self.initial_path = initial_path.expanduser().resolve() if initial_path else None
        self.buffers: dict[Path, Buffer] = {}
        self.open_tabs: list[Path] = []
        self.active_path: Path | None = None
        self.file_identities: dict[Path, FileIdentity | None] = {}
        self.loading_editor_text = False
        self.autosave_timer: Timer | None = None
        self.file_watch_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="main"):
            with Vertical(id="sidebar"):
                yield ProjectTree(self.project_root, id="project-tree")
                with Horizontal(id="sidebar-footer"):
                    yield DirectoryRefreshButton(id="refresh-directory-button")
                    yield Static("", id="sidebar-footer-spacer")
            with Vertical(id="right"):
                yield TabBar(id="tab-bar")
                yield TextArea.code_editor(
                    "",
                    id="editor",
                    soft_wrap=True,
                    theme=EDITOR_THEME,
                )
                yield MarkdownPreview("", id="markdown-preview", open_links=False)
                yield Static("", id="blocked-file-pane")
                with Horizontal(id="file-footer"):
                    yield Static("", id="path-status")
                    yield MarkdownPreviewToggle(id="markdown-preview-toggle")

    def on_mount(self) -> None:
        self.query_one("#editor", TextArea).display = False
        self.query_one("#markdown-preview", Markdown).display = False
        self.query_one("#blocked-file-pane", Static).display = False
        self.query_one("#markdown-preview-toggle", MarkdownPreviewToggle).display = False
        self.query_one("#right", Vertical).can_focus = True
        self._refresh_tabs()
        if self.initial_path is not None:
            self.open_file(self.initial_path)
        self.file_watch_timer = self.set_interval(0.75, self._reconcile_open_files)

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

    def on_directory_refresh_button_pressed(self, event: DirectoryRefreshButton.Pressed) -> None:
        event.stop()
        self._refresh_directory()

    def on_tab_bar_tab_selected(self, event: TabBar.TabSelected) -> None:
        self.switch_to(event.path)

    def on_tab_bar_tab_closed(self, event: TabBar.TabClosed) -> None:
        self.close_tab(event.path)

    def on_markdown_preview_toggle_pressed(
        self, event: MarkdownPreviewToggle.Pressed
    ) -> None:
        event.stop()
        if self.active_path is None or self.active_path not in self.buffers:
            return
        if not is_markdown_path(self.active_path):
            return

        buffer = self.buffers[self.active_path]
        if not buffer.editable:
            return
        if not buffer.preview:
            self._sync_active_editor_to_buffer()

        buffer.preview = not buffer.preview
        if buffer.preview:
            self._load_markdown_preview(buffer.text)
        else:
            self._load_editor_text(self.active_path, buffer.text)
            self.action_focus_editor()
        self._refresh_path_status()

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
        self.file_identities[path] = self._file_identity(path)
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
            if buffer.preview and is_markdown_path(path):
                self._load_markdown_preview(buffer.text)
            else:
                buffer.preview = False
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
        preview = self.query_one("#markdown-preview", MarkdownPreview)
        if editor.display:
            editor.focus()
        elif preview.display:
            preview.focus()
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
        self.file_identities.pop(path, None)

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
        preview = self.query_one("#markdown-preview", Markdown)
        blocked_pane = self.query_one("#blocked-file-pane", Static)
        editor.display = True
        preview.display = False
        blocked_pane.display = False
        self.loading_editor_text = True
        try:
            editor.language = language_for_path(path, editor.available_languages)
            editor.theme = EDITOR_THEME
            editor.load_text(text)
        finally:
            self.loading_editor_text = False

    def _load_markdown_preview(self, text: str) -> None:
        editor = self.query_one("#editor", TextArea)
        preview = self.query_one("#markdown-preview", MarkdownPreview)
        blocked_pane = self.query_one("#blocked-file-pane", Static)
        self.loading_editor_text = True
        try:
            editor.display = False
            blocked_pane.display = False
            preview.display = True
            preview.update(text)
            preview.focus()
        finally:
            self.loading_editor_text = False

    def _load_blocked_file(self, path: Path, message: str) -> None:
        editor = self.query_one("#editor", TextArea)
        preview = self.query_one("#markdown-preview", Markdown)
        blocked_pane = self.query_one("#blocked-file-pane", Static)
        self.loading_editor_text = True
        try:
            editor.language = None
            editor.load_text("")
            editor.display = False
            preview.display = False
            blocked_pane.update(f"{path.name}\n\n{message}")
            blocked_pane.display = True
        finally:
            self.loading_editor_text = False

    def _clear_editor(self) -> None:
        editor = self.query_one("#editor", TextArea)
        preview = self.query_one("#markdown-preview", Markdown)
        blocked_pane = self.query_one("#blocked-file-pane", Static)
        self.loading_editor_text = True
        try:
            editor.language = None
            editor.load_text("")
            editor.display = False
            preview.update("")
            preview.display = False
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
        try:
            editor = self.query_one("#editor", TextArea)
        except NoMatches:
            return
        if not editor.display:
            return
        if buffer.text != editor.text:
            buffer.text = editor.text
            buffer.dirty = True

    def _refresh_tabs(self) -> None:
        try:
            tab_bar = self.query_one("#tab-bar", TabBar)
        except NoMatches:
            return

        tab_bar.update_tabs(
            self.open_tabs,
            self.active_path,
            self.buffers,
        )
        self._refresh_path_status()

    def _refresh_directory(self) -> None:
        self.query_one("#project-tree", ProjectTree).refresh_directory()
        self._reconcile_open_files()

    def _refresh_path_status(self) -> None:
        status = self.query_one("#path-status", Static)
        toggle = self.query_one("#markdown-preview-toggle", MarkdownPreviewToggle)
        if self.active_path is None:
            status.update("")
            toggle.display = False
            return

        buffer = self.buffers.get(self.active_path)
        can_preview = bool(
            buffer and buffer.editable and is_markdown_path(self.active_path)
        )
        toggle.display = can_preview
        toggle.set_previewing(bool(can_preview and buffer and buffer.preview))

        width = max(status.size.width - 2, 0) or 80
        status.update(self._format_status_path(self.active_path, width))

    def _format_status_path(self, path: Path, max_width: int) -> str:
        try:
            display_path = str(path.resolve().relative_to(self.project_root))
        except ValueError:
            display_path = str(path.resolve())

        if len(display_path) <= max_width:
            return display_path
        if max_width <= 3:
            return display_path[-max_width:]
        return "..." + display_path[-(max_width - 3) :]

    def _reconcile_open_files(self) -> None:
        if not self.open_tabs:
            return

        identity_locations: dict[FileIdentity, Path] | None = None
        changed = False
        for path in list(self.open_tabs):
            if path.exists():
                self.file_identities[path] = self._file_identity(path)
                continue

            identity = self.file_identities.get(path)
            new_path: Path | None = None
            if identity is not None:
                if identity_locations is None:
                    identity_locations = self._project_file_identities()
                new_path = identity_locations.get(identity)

            if new_path is not None and new_path not in self.buffers:
                self._retarget_open_file(path, new_path)
            else:
                self._close_missing_tab(path)
            changed = True

        if changed:
            self.query_one("#project-tree", ProjectTree).refresh_directory()
            self._refresh_tabs()

    def _close_missing_tab(self, path: Path) -> None:
        was_active = path == self.active_path
        close_index = self.open_tabs.index(path)
        self.open_tabs.remove(path)
        self.buffers.pop(path, None)
        self.file_identities.pop(path, None)

        if not was_active:
            return

        if self.open_tabs:
            next_index = min(close_index, len(self.open_tabs) - 1)
            self.active_path = None
            self.switch_to(self.open_tabs[next_index])
        else:
            self.active_path = None
            self._clear_editor()

    def _retarget_open_file(self, old_path: Path, new_path: Path) -> None:
        new_path = new_path.resolve()
        buffer = self.buffers.pop(old_path)
        buffer.path = new_path
        self.buffers[new_path] = buffer

        tab_index = self.open_tabs.index(old_path)
        self.open_tabs[tab_index] = new_path

        identity = self.file_identities.pop(old_path, None)
        self.file_identities[new_path] = identity or self._file_identity(new_path)

        if self.active_path == old_path:
            self.active_path = new_path

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
            self.file_identities[buffer.path] = self._file_identity(buffer.path)
            return True

    def _file_identity(self, path: Path) -> FileIdentity | None:
        try:
            stat = path.stat()
        except OSError:
            return None
        return (stat.st_dev, stat.st_ino)

    def _project_file_identities(self) -> dict[FileIdentity, Path]:
        identities: dict[FileIdentity, Path] = {}
        for root, dir_names, file_names in os.walk(self.project_root):
            root_path = Path(root)
            dir_names[:] = [
                name for name in dir_names if not is_ignored(root_path / name)
            ]
            for file_name in file_names:
                path = root_path / file_name
                identity = self._file_identity(path)
                if identity is not None:
                    identities[identity] = path.resolve()
        return identities
