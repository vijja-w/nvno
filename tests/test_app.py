from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from textual.containers import Vertical
from textual.widgets import Static, TextArea

from nvno.app import NvnoApp
from nvno.file_policy import MAX_EDITOR_FILE_SIZE_BYTES
from nvno.tabs import CloseTab, FileTab, TabBar
from nvno.theme import EDITOR_THEME, language_for_path
from nvno.tree import ProjectTree


class AppTests(unittest.IsolatedAsyncioTestCase):
    async def test_close_active_tab_selects_next_tab(self) -> None:
        app = NvnoApp()

        async with app.run_test() as pilot:
            await pilot.pause()
            app.open_file(Path("README.md"))
            app.open_file(Path("pyproject.toml"))
            await pilot.pause()

            app.close_tab(Path("pyproject.toml"))
            await pilot.pause()

            self.assertEqual(app.active_path, Path("README.md").resolve())
            self.assertEqual([path.name for path in app.open_tabs], ["README.md"])
            self.assertTrue(app.query_one("#editor", TextArea).display)

    async def test_close_last_tab_clears_editor(self) -> None:
        app = NvnoApp()

        async with app.run_test() as pilot:
            await pilot.pause()
            app.open_file(Path("README.md"))
            await pilot.pause()

            app.close_tab(Path("README.md"))
            await pilot.pause()

            self.assertIsNone(app.active_path)
            self.assertEqual(app.open_tabs, [])
            self.assertFalse(app.query_one("#editor", TextArea).display)
            self.assertFalse(app.query_one("#blocked-file-pane", Static).display)

    async def test_unsupported_file_opens_blocked_pane(self) -> None:
        pdf_path = Path("sample.pdf")
        pdf_path.write_bytes(b"%PDF")
        app = NvnoApp()

        try:
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                app.open_file(pdf_path)
                await pilot.pause()

                editor = app.query_one("#editor", TextArea)
                blocked_pane = app.query_one("#blocked-file-pane", Static)
                self.assertEqual(app.active_path, pdf_path.resolve())
                self.assertFalse(editor.display)
                self.assertTrue(blocked_pane.display)
                self.assertIn("not supported", str(blocked_pane.content))
                self.assertFalse(app.buffers[pdf_path.resolve()].editable)
        finally:
            pdf_path.unlink(missing_ok=True)

    async def test_large_file_opens_blocked_pane(self) -> None:
        large_path = Path("large.txt")
        large_path.write_bytes(b"x" * (MAX_EDITOR_FILE_SIZE_BYTES + 1))
        app = NvnoApp()

        try:
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                app.open_file(large_path)
                await pilot.pause()

                editor = app.query_one("#editor", TextArea)
                blocked_pane = app.query_one("#blocked-file-pane", Static)
                self.assertEqual(app.active_path, large_path.resolve())
                self.assertFalse(editor.display)
                self.assertTrue(blocked_pane.display)
                self.assertIn("too large", str(blocked_pane.content))
                self.assertFalse(app.buffers[large_path.resolve()].editable)
        finally:
            large_path.unlink(missing_ok=True)

    async def test_unreadable_file_opens_blocked_pane(self) -> None:
        text_path = Path("unreadable.txt")
        text_path.write_text("looks fine until read", encoding="utf-8")
        app = NvnoApp()

        try:
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                with patch.object(Path, "read_text", side_effect=OSError("permission denied")):
                    app.open_file(text_path)
                await pilot.pause()

                editor = app.query_one("#editor", TextArea)
                blocked_pane = app.query_one("#blocked-file-pane", Static)
                self.assertEqual(app.active_path, text_path.resolve())
                self.assertFalse(editor.display)
                self.assertTrue(blocked_pane.display)
                self.assertIn("cannot be opened", str(blocked_pane.content))
                self.assertFalse(app.buffers[text_path.resolve()].editable)
        finally:
            text_path.unlink(missing_ok=True)

    async def test_tab_close_button_click_closes_tab(self) -> None:
        app = NvnoApp()

        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.open_file(Path("README.md"))
            await pilot.pause()

            self.assertTrue(await pilot.click(CloseTab))
            await pilot.pause()

            self.assertEqual(app.open_tabs, [])
            self.assertIsNone(app.active_path)

    async def test_tab_bar_keeps_tabs_above_scrollbar(self) -> None:
        app = NvnoApp()

        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.open_file(Path("tests/test_app.py"))
            await pilot.pause()

            self.assertEqual(app.query_one(TabBar).region.height, 2)
            self.assertEqual(app.query_one(FileTab).region.height, 1)
            self.assertEqual(app.query_one(CloseTab).region.height, 1)

    async def test_many_tabs_keep_first_tab_visible_with_scrollbar(self) -> None:
        app = NvnoApp()

        async with app.run_test(size=(60, 20)) as pilot:
            await pilot.pause()
            for path in [
                Path("README.md"),
                Path("pyproject.toml"),
                Path("uv.lock"),
                Path("src/nvno/app.py"),
                Path("src/nvno/tabs.py"),
                Path("src/nvno/tree.py"),
                Path("tests/test_app.py"),
            ]:
                app.open_file(path)
            await pilot.pause()

            first_tab = app.query(FileTab).first()
            self.assertEqual(first_tab.region.y, app.query_one(TabBar).region.y)
            self.assertEqual(first_tab.region.height, 1)

    async def test_tab_label_click_selects_tab(self) -> None:
        app = NvnoApp()

        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.open_file(Path("README.md"))
            app.open_file(Path("pyproject.toml"))
            await pilot.pause()

            first_tab = app.query(FileTab).first()
            self.assertTrue(await pilot.click(first_tab))
            await pilot.pause()

            self.assertEqual(app.active_path, Path("README.md").resolve())

    async def test_tree_file_click_opens_file(self) -> None:
        app = NvnoApp()

        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()

            self.assertTrue(await pilot.click(ProjectTree, offset=(4, 5)))
            await pilot.pause()

            self.assertEqual(app.active_path, Path("pyproject.toml").resolve())

    async def test_editor_theme_and_language_follow_active_file(self) -> None:
        html_path = Path("sample.html")
        py_path = Path("tests/test_app.py")
        html_path.write_text("<h1>Hello</h1>", encoding="utf-8")
        app = NvnoApp()

        try:
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                app.open_file(html_path)
                await pilot.pause()
                editor = app.query_one("#editor", TextArea)
                self.assertEqual(editor.theme, EDITOR_THEME)
                self.assertEqual(editor.language, "html")
                self.assertTrue(editor._highlights)

                app.open_file(py_path)
                await pilot.pause()
                self.assertEqual(editor.theme, EDITOR_THEME)
                self.assertEqual(editor.language, "python")
                self.assertTrue(editor._highlights)
        finally:
            html_path.unlink(missing_ok=True)

    def test_language_for_path_uses_supported_extensions(self) -> None:
        available = {"html", "python"}

        self.assertEqual(language_for_path(Path("index.html"), available), "html")
        self.assertEqual(language_for_path(Path("app.py"), available), "python")
        self.assertIsNone(language_for_path(Path("notes.unknown"), available))

    async def test_sidebar_shortcut_focuses_then_collapses_tree(self) -> None:
        app = NvnoApp()

        async with app.run_test() as pilot:
            await pilot.pause()
            tree = app.query_one(ProjectTree)
            editor = app.query_one("#editor", TextArea)

            self.assertTrue(tree.display)
            app.open_file(Path("README.md"))
            await pilot.pause()
            editor.focus()

            app.action_focus_or_toggle_sidebar()
            await pilot.pause()
            self.assertTrue(tree.display)
            self.assertTrue(tree.has_focus)

            app.action_focus_or_toggle_sidebar()
            await pilot.pause()
            self.assertFalse(tree.display)
            self.assertTrue(editor.has_focus)

            app.action_focus_or_toggle_sidebar()
            await pilot.pause()
            self.assertTrue(tree.display)
            self.assertTrue(tree.has_focus)

            app.action_focus_editor()
            await pilot.pause()
            self.assertTrue(editor.has_focus)
            self.assertTrue(tree.display)

            tree.action_collapse_or_parent()
            self.assertFalse(tree.root.is_expanded)
            tree.action_expand_or_select()
            self.assertTrue(tree.root.is_expanded)

    async def test_sidebar_shortcut_can_collapse_before_file_is_open(self) -> None:
        app = NvnoApp()

        async with app.run_test() as pilot:
            await pilot.pause()
            tree = app.query_one(ProjectTree)
            right = app.query_one("#right", Vertical)

            tree.focus()
            app.action_focus_or_toggle_sidebar()
            await pilot.pause()

            self.assertFalse(tree.display)
            self.assertTrue(right.has_focus)


if __name__ == "__main__":
    unittest.main()
