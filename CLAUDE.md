# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python CLI tool for launching, managing, and interacting with Claude Code sessions remotely via tmux + iTerm2 on macOS.

## Tech Stack

- Python 3.13+
- tmux (via subprocess)
- iTerm2 (via AppleScript/osascript)
- uv for dependency management

## Build & Run

```bash
uv sync                              # Install dependencies
uv run python main.py start          # Launch a session
uv run python main.py send <s> "hi"  # Send prompt
uv run python main.py read <s>       # Read output
uv run python main.py list           # List sessions
uv run python main.py kill <s>       # Kill a session
```

## Architecture

- Single-file CLI (`main.py`) using argparse subcommands
- tmux is the communication channel: `send-keys -l` for input, `capture-pane` for output
- iTerm2 is controlled via AppleScript templates (LAYOUTS dict)
- Session bookmarks stored in `sessions.json` (atomic writes, validated names)
- All tmux `-t` targets use `=name` for exact match (no fuzzy)
- Session names validated to `[a-zA-Z0-9_-]` to prevent AppleScript injection

## Conventions

- No singletons unless strictly necessary
- Type hints on all function signatures
- Validate at system boundaries (user input, session names)
