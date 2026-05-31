# nvno

`nvno` is a tiny terminal IDE for working inside a project directory.

It opens the current directory with a file tree, tabs, an editor, syntax highlighting, and autosave.

## Install

```bash
uv tool install git+https://github.com/vijja-w/nvno.git
```

## Use

```bash
cd ~/code/my-project
nvno
```

Open a specific file with its parent directory as the workspace:

```bash
nvno ~/.zshrc
```

Open a specific directory as the workspace:

```bash
nvno ~/code/my-project
```

Shortcuts:

- `Esc`: focus/open the file tree; if the tree is already focused, collapse it.
- `Ctrl+C`: quit.
