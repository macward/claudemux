# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python CLI tool for launching, managing, and interacting with Claude Code sessions remotely via tmux.

## Tech Stack

- Python 3.13+
- tmux (via subprocess)
- uv for dependency management

## Build & Run

```bash
uv sync                      # Install dependencies
uv tool install .            # Install as global CLI command
claudemux start              # Launch a session
claudemux send <s> "hi"     # Send prompt
claudemux read <s>           # Read output
claudemux list               # List sessions
claudemux kill <s>           # Kill a session
```

## Architecture

- Single-file CLI (`src/claudemux/main.py`) using argparse subcommands
- tmux is the communication channel: `send-keys -l` for input, `capture-pane` for output
- `start` attaches in current terminal via `os.execvp`, `--detach` skips attaching
- Session bookmarks stored in `~/.claudemux/sessions.json` (atomic writes)
- All tmux `-t` targets use `=name:0.0` for exact match (no fuzzy)
- Session names validated to `[a-zA-Z0-9_-]`
- Stop hook installed to `~/.claude/hooks/`, signals written to `/tmp/claude-tmux/`

## Conventions

- No singletons unless strictly necessary
- Type hints on all function signatures
- Validate at system boundaries (user input, session names)
