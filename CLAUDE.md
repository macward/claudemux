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
uv sync                      # Install dependencies
uv tool install .            # Install as global CLI command
claudemux start              # Launch a session
claudemux send <s> "hi"     # Send prompt
claudemux read <s>           # Read output
claudemux list               # List sessions
claudemux kill <s>           # Kill a session
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
