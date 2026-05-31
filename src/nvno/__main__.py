from __future__ import annotations

import argparse
from pathlib import Path

from .app import NvnoApp


def app_for_path(path: str | None) -> NvnoApp:
    if path is None:
        return NvnoApp()

    launch_path = Path(path).expanduser()
    if launch_path.is_dir():
        return NvnoApp(project_root=launch_path)
    return NvnoApp(project_root=launch_path.parent, initial_path=launch_path)


def main(argv: list[str] | None = None) -> None:
    """Run the nvno terminal IDE."""
    parser = argparse.ArgumentParser(description="Run the nvno terminal IDE.")
    parser.add_argument(
        "path",
        nargs="?",
        help="Optional file to open, or directory to use as the workspace.",
    )
    args = parser.parse_args(argv)
    app_for_path(args.path).run()


if __name__ == "__main__":
    main()
