# tmux-poc

CLI to launch and interact with Claude Code sessions remotely via tmux + iTerm2.

## Requirements

- macOS
- [iTerm2](https://iterm2.com/)
- tmux (`brew install tmux`)
- [Claude Code CLI](https://claude.ai/code) (`claude` in PATH)
- [uv](https://docs.astral.sh/uv/)

## Setup

```bash
uv sync
```

## Commands

### start

Launch a new Claude Code session in iTerm2 via tmux.

```bash
# Basic (random session name, current directory)
uv run python main.py start

# With a working directory
uv run python main.py start ~/Developer/myproject

# With a custom name
uv run python main.py start ~/Developer/myproject --name my-session

# With a layout
uv run python main.py start ~/Developer/myproject --layout split-right

# From a saved session
uv run python main.py start --saved my-project
```

**Layouts:**

| Layout | Description |
|---|---|
| `single` | Claude Code only (default) |
| `split-right` | Claude Code left, log pane right |
| `split-bottom` | Claude Code top, log pane bottom |
| `three-pane` | Claude Code left, two panes stacked right |

### save / saved / unsave

Bookmark sessions (name + path) for quick reuse. Stored in `sessions.json`.

```bash
# Save a session
uv run python main.py save my-project ~/Developer/myproject

# List saved sessions
uv run python main.py saved

# Remove a saved session
uv run python main.py unsave my-project
```

### list

Show all active tmux sessions.

```bash
uv run python main.py list
```

### send

Send a prompt to a running Claude Code session.

```bash
uv run python main.py send <session-name> "your prompt here"
```

### read

Capture the current output from a session (uses `tmux capture-pane`).

```bash
uv run python main.py read <session-name>
```

## How it works

1. **start** creates a detached tmux session running `claude` and opens iTerm2 attached to it. Reuses an existing iTerm2 window if one is open.
2. **send** uses `tmux send-keys` to type text into the session remotely.
3. **read** uses `tmux capture-pane -p -S -` to grab the full scrollback buffer.
