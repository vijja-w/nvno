import tempfile
import unittest
from pathlib import Path

from nvno.autosave import atomic_write_text
from nvno.fs import IGNORED_DIRS, is_ignored, sorted_children


class AutosaveTests(unittest.TestCase):
    def test_atomic_write_text_replaces_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp_path = Path(temp_dir)
            target = tmp_path / "note.txt"
            target.write_text("old", encoding="utf-8")

            atomic_write_text(target, "new")

            self.assertEqual(target.read_text(encoding="utf-8"), "new")
            self.assertEqual(list(tmp_path.glob(".note.txt.*.tmp")), [])

    def test_sorted_children_skips_ignored_dirs_and_orders_dirs_first(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp_path = Path(temp_dir)
            (tmp_path / "z_file.py").write_text("", encoding="utf-8")
            (tmp_path / "a_dir").mkdir()
            (tmp_path / "b_file.py").write_text("", encoding="utf-8")
            for dirname in IGNORED_DIRS:
                (tmp_path / dirname).mkdir()

            self.assertEqual(
                [path.name for path in sorted_children(tmp_path)],
                ["a_dir", "b_file.py", "z_file.py"],
            )
            self.assertTrue(is_ignored(tmp_path / ".git"))


if __name__ == "__main__":
    unittest.main()
