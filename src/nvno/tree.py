from __future__ import annotations

from pathlib import Path

from textual.binding import Binding
from textual import events
from textual.message import Message
from textual.widgets import Tree
from textual.widgets import Static

from .fs import sorted_children


class DirectoryRefreshButton(Static):
    class Pressed(Message):
        pass

    def __init__(self, **kwargs: object) -> None:
        super().__init__(" Refresh ", **kwargs)

    async def _on_click(self, event: events.Click) -> None:
        event.stop()
        self.post_message(self.Pressed())


class ProjectTree(Tree[Path]):
    """Directory tree rooted at the current project."""

    BINDINGS = [
        *Tree.BINDINGS,
        Binding("right", "expand_or_select", show=False),
        Binding("left", "collapse_or_parent", show=False),
    ]

    def __init__(self, root_path: Path, **kwargs: object) -> None:
        self.root_path = root_path.resolve()
        super().__init__(self.root_path.name or str(self.root_path), data=self.root_path, **kwargs)

    def on_mount(self) -> None:
        self.show_root = True
        self.root.expand()
        self._populate(self.root)

    def ensure_loaded(self, node) -> None:
        path = node.data
        if isinstance(path, Path) and path.is_dir() and not node.children:
            self._populate(node)

    def refresh_directory(self) -> None:
        self.root.remove_children()
        self.root.expand()
        self._populate(self.root)
        self.refresh()

    async def _on_click(self, event: events.Click) -> None:
        event.stop()
        self.focus()
        _, scroll_y = self.scroll_offset
        line_no = event.y + scroll_y
        node = self.get_node_at_line(line_no)
        if node is None:
            return

        self.cursor_line = line_no
        self.post_message(Tree.NodeSelected(node))

    def action_expand_or_select(self) -> None:
        node = self.cursor_node
        if node is None:
            return

        path = node.data
        if isinstance(path, Path) and path.is_dir():
            self.ensure_loaded(node)
            if not node.is_expanded:
                node.expand()
            else:
                self.post_message(Tree.NodeSelected(node))
        else:
            self.post_message(Tree.NodeSelected(node))

    def action_collapse_or_parent(self) -> None:
        node = self.cursor_node
        if node is None:
            return

        path = node.data
        if isinstance(path, Path) and path.is_dir() and node.is_expanded:
            node.collapse()
        elif node.parent is not None:
            self.move_cursor(node.parent, animate=True)

    def _populate(self, node) -> None:
        path = node.data
        if not isinstance(path, Path) or not path.is_dir():
            return

        for child_path in sorted_children(path):
            if child_path.is_dir():
                child = node.add(child_path.name, data=child_path)
                child.allow_expand = True
            else:
                node.add_leaf(child_path.name, data=child_path)
