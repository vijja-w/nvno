from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nvno.file_policy import (
    MAX_EDITOR_FILE_SIZE_BYTES,
    UnsupportedEditorFileError,
    editor_file_policy,
)
from nvno.fs import read_text_for_editor


class FilePolicyTests(unittest.TestCase):
    def test_unsupported_file_type_is_blocked_before_reading(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "manual.pdf"
            path.write_bytes(b"%PDF")

            policy = editor_file_policy(path)

            self.assertFalse(policy.can_open)
            self.assertIn("not supported", policy.message or "")
            with self.assertRaises(UnsupportedEditorFileError):
                read_text_for_editor(path)

    def test_large_file_is_blocked_before_reading(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "large.txt"
            path.write_bytes(b"x" * (MAX_EDITOR_FILE_SIZE_BYTES + 1))

            policy = editor_file_policy(path)

            self.assertFalse(policy.can_open)
            self.assertIn("too large", policy.message or "")
            with self.assertRaises(UnsupportedEditorFileError):
                read_text_for_editor(path)


if __name__ == "__main__":
    unittest.main()
