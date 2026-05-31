from __future__ import annotations

from pathlib import Path

# Change most of nvno's visual personality here.
PALETTE = {
    "bg": "#101114",
    "surface": "#171a21",
    "surface_lift": "#20242d",
    "editor_bg": "#1e1f35",
    "text": "#f4f1ea",
    "muted": "#8b95a7",
    "accent": "#7dd3fc",
    "accent_2": "#f0abfc",
    "danger": "#fb7185",
    "selection": "#334155",
}

EDITOR_THEME = "dracula"

LANGUAGE_BY_SUFFIX = {
    ".bash": "bash",
    ".css": "css",
    ".go": "go",
    ".htm": "html",
    ".html": "html",
    ".java": "java",
    ".js": "javascript",
    ".json": "json",
    ".jsx": "javascript",
    ".md": "markdown",
    ".py": "python",
    ".regex": "regex",
    ".rs": "rust",
    ".sh": "bash",
    ".sql": "sql",
    ".toml": "toml",
    ".ts": "javascript",
    ".tsx": "javascript",
    ".xml": "xml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".zsh": "bash",
}

LANGUAGE_BY_NAME = {
    "Dockerfile": "bash",
    "Makefile": "bash",
}


def language_for_path(
    path: Path,
    available_languages: set[str] | frozenset[str] | None = None,
) -> str | None:
    language = LANGUAGE_BY_NAME.get(path.name) or LANGUAGE_BY_SUFFIX.get(path.suffix.lower())
    if available_languages is not None and language not in available_languages:
        return None
    return language


APP_CSS = f"""
Screen {{
    layout: vertical;
    background: {PALETTE["bg"]};
    color: {PALETTE["text"]};
}}

#main {{
    height: 100%;
    background: {PALETTE["bg"]};
}}

#sidebar {{
    width: 32;
    height: 100%;
    background: {PALETTE["surface"]};
}}

#project-tree {{
    width: 100%;
    height: 1fr;
    border: none;
    background: {PALETTE["surface"]};
    color: {PALETTE["muted"]};
}}

#project-tree:focus {{
    background: {PALETTE["surface_lift"]};
    color: {PALETTE["text"]};
}}

#sidebar-footer {{
    height: 1;
    background: {PALETTE["bg"]};
}}

#refresh-directory-button {{
    width: 9;
    height: 1;
    color: {PALETTE["bg"]};
    background: {PALETTE["accent"]};
    text-style: bold;
}}

#refresh-directory-button:hover {{
    background: {PALETTE["accent_2"]};
}}

#sidebar-footer-spacer {{
    width: 1fr;
    height: 1;
    background: {PALETTE["bg"]};
}}

#right {{
    width: 1fr;
    height: 100%;
    background: {PALETTE["editor_bg"]};
}}

#editor {{
    height: 1fr;
    border: none;
    background: {PALETTE["editor_bg"]};
    color: {PALETTE["text"]};
}}

#blocked-file-pane {{
    height: 1fr;
    padding: 2 4;
    background: {PALETTE["editor_bg"]};
    color: {PALETTE["muted"]};
}}

#path-status {{
    height: 1;
    padding: 0 1;
    background: {PALETTE["bg"]};
    color: {PALETTE["muted"]};
    text-overflow: ellipsis;
}}
"""

TAB_CSS = f"""
TabBar {{
    height: 2;
    background: {PALETTE["bg"]};
}}

#tab-scroll {{
    height: 2;
    overflow-x: auto;
    overflow-y: hidden;
    background: {PALETTE["bg"]};
}}

TabItem {{
    width: auto;
    height: 1;
    margin: 0;
    padding: 0;
    background: {PALETTE["surface"]};
}}

FileTab {{
    width: auto;
    min-width: 8;
    height: 1;
    margin: 0;
    padding: 0;
    color: {PALETTE["muted"]};
    background: {PALETTE["surface"]};
}}

FileTab.active {{
    color: {PALETTE["bg"]};
    background: {PALETTE["accent"]};
    text-style: bold;
}}

FileTab.save-error {{
    color: {PALETTE["danger"]};
}}

CloseTab {{
    width: 3;
    min-width: 3;
    height: 1;
    margin: 0;
    padding: 0;
    color: {PALETTE["muted"]};
    background: {PALETTE["surface"]};
    text-style: bold;
}}

TabItem.active CloseTab {{
    color: {PALETTE["bg"]};
    background: {PALETTE["accent"]};
    text-style: bold;
}}
"""
