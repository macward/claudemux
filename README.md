# claude-tmux

CLI tool to launch and interact with Claude Code sessions remotely via tmux + iTerm2.

## Requirements

- macOS
- [iTerm2](https://iterm2.com/)
- tmux (`brew install tmux`)
- jq (`brew install jq`) — required for hooks
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

# Detached (no iTerm2, just tmux session)
uv run python main.py start ~/Developer/myproject --name worker --detach

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
uv run python main.py read <session-name> --lines 500
```

### kill

Kill a tmux session.

```bash
uv run python main.py kill <session-name>
```

## Hooks

Claude Code hooks allow detecting when Claude finishes responding — no polling needed.

### setup-hooks / remove-hooks

Install or remove the Stop hook in `~/.claude/settings.json`.

```bash
# Install
uv run python main.py setup-hooks

# Remove
uv run python main.py remove-hooks
```

When installed, Claude Code writes a signal file to `/tmp/claude-tmux/<session-id>.json` every time it finishes responding. The signal contains `session_id`, `transcript_path`, `cwd`, and `completed_at`.

### wait

Block until a session completes (reads the signal file).

```bash
# Wait up to 5 minutes (default)
uv run python main.py wait

# Custom timeout
uv run python main.py wait --timeout 60 --interval 0.5
```

### Typical agent workflow

```bash
uv run python main.py setup-hooks                          # once
uv run python main.py start ~/myproject --name task1 --detach
uv run python main.py send task1 "fix the failing tests"
uv run python main.py wait --timeout 120                    # blocks until done
```

## How it works

1. **start** creates a detached tmux session running `claude` and opens iTerm2 attached to it. Reuses an existing iTerm2 window if one is open.
2. **send** uses `tmux send-keys -l` to type text into the session as literal input.
3. **read** uses `tmux capture-pane` to grab scrollback output.
4. **wait** polls `/tmp/claude-tmux/` for signal files written by the Stop hook.
5. The **Stop hook** (`hooks/on-stop.sh`) runs when Claude finishes responding, writing session metadata to a JSON signal file.
