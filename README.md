# claudemux

CLI tool to launch and interact with Claude Code sessions remotely via tmux.

## Requirements

- macOS
- tmux (`brew install tmux`)
- jq (`brew install jq`) — required for hooks
- [Claude Code CLI](https://claude.ai/code) (`claude` in PATH)
- [uv](https://docs.astral.sh/uv/)
- One of: [iTerm2](https://iterm2.com/), [Ghostty](https://ghostty.org/), or Terminal.app (built-in)

## Install

```bash
# From GitHub (recommended)
uv tool install git+https://github.com/macward/claudemux.git

# Or from local clone
git clone git@github.com:macward/claudemux.git
cd claudemux
uv tool install .

# Uninstall
claudemux remove-hooks    # remove Stop hook from Claude settings
uv tool uninstall claudemux
```

## Commands

### start

Launch a new Claude Code session via tmux. Auto-detects your terminal (iTerm2 > Ghostty > Terminal.app).

```bash
# Basic (random session name, auto-detect terminal)
claudemux start

# With a working directory
claudemux start ~/Developer/myproject

# With a custom name
claudemux start ~/Developer/myproject --name my-session

# Force a specific terminal
claudemux start ~/Developer/myproject --terminal ghostty

# With a layout
claudemux start ~/Developer/myproject --layout split-right

# Detached (no terminal, just tmux session)
claudemux start ~/Developer/myproject --name worker --detach

# From a saved session
claudemux start --saved my-project
```

**Terminals:**

| Terminal | Layouts supported |
|---|---|
| `iterm2` | single, split-right, split-bottom, three-pane |
| `ghostty` | single |
| `terminal` | single |

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
claudemux save my-project ~/Developer/myproject

# List saved sessions
claudemux saved

# Remove a saved session
claudemux unsave my-project
```

### list

Show all active tmux sessions.

```bash
claudemux list
```

### send

Send a prompt to a running Claude Code session.

```bash
claudemux send my-session "your prompt here"
claudemux send my-session "refactor the auth module to use async/await"
claudemux send my-session "/init"
```

### read

Capture the current output from a session (uses `tmux capture-pane`).

```bash
claudemux read <session-name>
claudemux read <session-name> --lines 500
```

### kill

Kill a tmux session.

```bash
claudemux kill <session-name>
```

## Hooks

Claude Code hooks allow detecting when Claude finishes responding — no polling needed.

### setup-hooks / remove-hooks

Install or remove the Stop hook in `~/.claude/settings.json`.

```bash
# Install
claudemux setup-hooks

# Remove
claudemux remove-hooks
```

When installed, Claude Code writes a signal file to `/tmp/claude-tmux/<session-name>.json` every time a claudemux session finishes responding. The hook only fires for sessions created by claudemux (not regular Claude Code sessions). The signal contains `session_id`, `session_name`, `transcript_path`, `cwd`, and `completed_at`.

### wait

Block until a session completes (reads the signal file).

```bash
# Wait up to 5 minutes (default)
claudemux wait

# Wait for a specific session
claudemux wait --session my-session

# Custom timeout
claudemux wait --timeout 60 --interval 0.5

# Clean stale signals before waiting
claudemux wait --clean
```

### Typical agent workflow

```bash
claudemux setup-hooks                                        # once
claudemux start ~/myproject --name task1 --detach
claudemux send task1 "fix the failing tests"
claudemux wait --session task1 --timeout 120                 # blocks until done
claudemux read task1                                         # see what Claude did
claudemux kill task1                                         # cleanup
```

## How it works

1. **start** creates a detached tmux session running `claude` and opens a terminal attached to it. Auto-detects iTerm2, Ghostty, or Terminal.app.
2. **send** uses `tmux send-keys -l` to type text into the session as literal input.
3. **read** uses `tmux capture-pane` to grab scrollback output.
4. **wait** polls `/tmp/claude-tmux/` for signal files written by the Stop hook.
5. The **Stop hook** (`hooks/on-stop.sh`) runs only in claudemux sessions (via `CLAUDEMUX=1` env var), writing session metadata to a JSON signal file named after the tmux session.
