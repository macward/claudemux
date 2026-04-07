import argparse
import glob
import json
import os
import random
import re
import shutil
import string
import subprocess
import sys
import tempfile
import time


DATA_DIR = os.path.expanduser("~/.claudemux")
SESSIONS_FILE = os.path.join(DATA_DIR, "sessions.json")
HOOK_SOURCE = os.path.join(os.path.dirname(__file__), "hooks", "on-stop.sh")
HOOK_INSTALL_DIR = os.path.expanduser("~/.claude/hooks")
HOOK_INSTALLED_PATH = os.path.join(HOOK_INSTALL_DIR, "claude-tmux-on-stop.sh")
SIGNAL_DIR = "/tmp/claude-tmux"
CLAUDE_SETTINGS_PATH = os.path.expanduser("~/.claude/settings.json")
SESSION_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+$")
BASE_COMMANDS = ["tmux", "claude"]
GUI_COMMANDS = ["osascript"]
MAX_CAPTURE_LINES = 10000

COMMANDS_NEEDING_GUI = {"start"}


def preflight_check(command: str) -> None:
    required = list(BASE_COMMANDS)
    if command in COMMANDS_NEEDING_GUI:
        required.extend(GUI_COMMANDS)

    missing = [cmd for cmd in required if not shutil.which(cmd)]
    if missing:
        print(f"Error: missing required commands: {', '.join(missing)}")
        print("Install them before running:")
        for cmd in missing:
            if cmd == "tmux":
                print("  brew install tmux")
            elif cmd == "claude":
                print("  See https://claude.ai/code")
            elif cmd == "osascript":
                print("  osascript is part of macOS — are you running on macOS?")
        raise SystemExit(1)


def validate_session_name(name: str) -> str:
    if not SESSION_NAME_PATTERN.match(name):
        print(f"Error: session name '{name}' contains invalid characters. Use only [a-zA-Z0-9_-].")
        raise SystemExit(1)
    return name


def load_sessions() -> dict[str, str]:
    if not os.path.exists(SESSIONS_FILE):
        return {}
    try:
        with open(SESSIONS_FILE) as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"Warning: {SESSIONS_FILE} is corrupt. Resetting.")
        return {}


def save_sessions(sessions: dict[str, str]) -> None:
    os.makedirs(os.path.dirname(SESSIONS_FILE), exist_ok=True)
    _atomic_write_json(SESSIONS_FILE, sessions)


def generate_session_name() -> str:
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=5))
    return f"claude-{suffix}"


def _tmux_target(session_name: str) -> str:
    return f"={session_name}:0.0"


def is_tmux_session_alive(session_name: str) -> bool:
    result = subprocess.run(
        ["tmux", "has-session", "-t", f"={session_name}"],
        capture_output=True,
    )
    return result.returncode == 0


def create_tmux_session_with_claude(session_name: str, working_dir: str | None = None) -> None:
    cmd = ["tmux", "new-session", "-d", "-s", session_name, "-e", "CLAUDEMUX=1", "-e", f"CLAUDEMUX_SESSION={session_name}"]
    if working_dir:
        resolved = os.path.expanduser(working_dir)
        if not os.path.isdir(resolved):
            print(f"Error: directory '{resolved}' does not exist.")
            raise SystemExit(1)
        cmd.extend(["-c", resolved])
    cmd.append("claude")
    subprocess.run(cmd, check=True, timeout=30)


def _get_or_create_window_script() -> str:
    """AppleScript snippet that sets `targetWindow` to an existing window or creates one."""
    return """
        set windowCount to count of windows
        if windowCount > 0 then
            set targetWindow to current window
        else
            set targetWindow to (create window with default profile)
        end if
    """


LAYOUTS = {
    "single": """
    tell application "iTerm2"
        activate
        {get_window}
        tell current session of targetWindow
            write text "tmux attach-session -t {session_name}"
        end tell
    end tell
    """,
    "split-right": """
    tell application "iTerm2"
        activate
        {get_window}
        tell current session of targetWindow
            write text "tmux attach-session -t {session_name}"
            set logPane to (split vertically with default profile)
        end tell
        tell logPane
            write text "echo '-- Log pane ready --'"
        end tell
    end tell
    """,
    "split-bottom": """
    tell application "iTerm2"
        activate
        {get_window}
        tell current session of targetWindow
            write text "tmux attach-session -t {session_name}"
            set logPane to (split horizontally with default profile)
        end tell
        tell logPane
            write text "echo '-- Log pane ready --'"
        end tell
    end tell
    """,
    "three-pane": """
    tell application "iTerm2"
        activate
        {get_window}
        tell current session of targetWindow
            write text "tmux attach-session -t {session_name}"
            set rightPane to (split vertically with default profile)
        end tell
        tell rightPane
            write text "echo '-- Right pane ready --'"
            set bottomPane to (split horizontally with default profile)
        end tell
        tell bottomPane
            write text "echo '-- Bottom-right pane ready --'"
        end tell
    end tell
    """,
}


def open_iterm_with_tmux(session_name: str, layout: str = "single") -> None:
    validate_session_name(session_name)
    template = LAYOUTS[layout]
    applescript = template.format(
        session_name=session_name,
        get_window=_get_or_create_window_script(),
    )
    subprocess.run(["osascript", "-e", applescript], check=True, timeout=30)


def capture_pane(session_name: str, lines: int = 200) -> str:
    result = subprocess.run(
        ["tmux", "capture-pane", "-t", _tmux_target(session_name), "-p", "-S", f"-{lines}"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.rstrip("\n")


def send_prompt(session_name: str, prompt: str) -> None:
    if not is_tmux_session_alive(session_name):
        print(f"Error: session '{session_name}' not found. Run 'start' first.")
        raise SystemExit(1)

    subprocess.run(
        ["tmux", "send-keys", "-t", _tmux_target(session_name), "-l", prompt],
        check=True, timeout=10,
    )
    subprocess.run(
        ["tmux", "send-keys", "-t", _tmux_target(session_name), "Enter"],
        check=True, timeout=10,
    )
    print(f"Prompt sent to '{session_name}'.")


def cmd_start(args: argparse.Namespace) -> None:
    if args.saved and (args.path or args.name):
        print("Error: --saved cannot be combined with a path or --name.")
        raise SystemExit(1)

    if args.saved:
        sessions = load_sessions()
        if args.saved not in sessions:
            print(f"Error: saved session '{args.saved}' not found. Run 'saved' to see available.")
            raise SystemExit(1)
        session_name = validate_session_name(args.saved)
        working_dir = sessions[args.saved]
    else:
        session_name = validate_session_name(args.name) if args.name else generate_session_name()
        working_dir = args.path

    layout = args.layout

    if is_tmux_session_alive(session_name):
        print(f"Session '{session_name}' already exists, attaching...")
    else:
        print(f"Creating tmux session '{session_name}' with Claude Code...")
        if working_dir:
            print(f"Working directory: {os.path.expanduser(working_dir)}")
        create_tmux_session_with_claude(session_name, working_dir)

    if args.detach:
        print(f"Session '{session_name}' created (detached).")
        return

    print(f"Opening iTerm2 with layout '{layout}'...")
    open_iterm_with_tmux(session_name, layout)
    print("Done.")


def cmd_send(args: argparse.Namespace) -> None:
    validate_session_name(args.session)
    send_prompt(args.session, args.prompt)


def cmd_list(args: argparse.Namespace) -> None:
    result = subprocess.run(
        ["tmux", "list-sessions", "-F", "#{session_name}\t#{session_windows} windows\t#{session_created_string}\t#{?session_attached,attached,detached}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("No active tmux sessions.")
        return

    print(f"{'Name':<25} {'Windows':<12} {'Status':<10} {'Created'}")
    print("-" * 70)
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) != 4:
            continue
        name, windows, created, status = parts
        print(f"{name:<25} {windows:<12} {status:<10} {created}")


def cmd_save(args: argparse.Namespace) -> None:
    validate_session_name(args.name)
    resolved = os.path.expanduser(args.path)
    if not os.path.isdir(resolved):
        print(f"Error: directory '{resolved}' does not exist.")
        raise SystemExit(1)

    sessions = load_sessions()
    sessions[args.name] = resolved
    save_sessions(sessions)
    print(f"Saved '{args.name}' -> {resolved}")


def cmd_saved(args: argparse.Namespace) -> None:
    sessions = load_sessions()
    if not sessions:
        print("No saved sessions.")
        return

    print(f"{'Name':<25} {'Path'}")
    print("-" * 60)
    for name, path in sessions.items():
        print(f"{name:<25} {path}")


def cmd_kill(args: argparse.Namespace) -> None:
    validate_session_name(args.session)
    if not is_tmux_session_alive(args.session):
        print(f"Error: session '{args.session}' not found.")
        raise SystemExit(1)

    subprocess.run(
        ["tmux", "kill-session", "-t", f"={args.session}"],
        check=True, timeout=10,
    )
    print(f"Session '{args.session}' killed.")


def cmd_unsave(args: argparse.Namespace) -> None:
    validate_session_name(args.name)
    sessions = load_sessions()
    if args.name not in sessions:
        print(f"Error: '{args.name}' not found.")
        raise SystemExit(1)

    del sessions[args.name]
    save_sessions(sessions)
    print(f"Removed '{args.name}'.")


def _atomic_write_json(path: str, data: dict) -> None:
    dir_path = os.path.dirname(path)
    os.makedirs(dir_path, exist_ok=True)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile("w", dir=dir_path, delete=False, suffix=".tmp") as tmp:
            json.dump(data, tmp, indent=2)
            tmp_path = tmp.name
        os.replace(tmp_path, path)
    except Exception:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def _install_hook_script() -> None:
    if not os.path.isfile(HOOK_SOURCE):
        print(f"Error: hook script not found at {HOOK_SOURCE}")
        raise SystemExit(1)

    os.makedirs(HOOK_INSTALL_DIR, exist_ok=True)
    shutil.copy2(HOOK_SOURCE, HOOK_INSTALLED_PATH)
    os.chmod(HOOK_INSTALLED_PATH, 0o755)


def cmd_setup_hooks(args: argparse.Namespace) -> None:
    if not os.path.isfile(HOOK_SOURCE):
        print(f"Error: hook script not found at {HOOK_SOURCE}")
        raise SystemExit(1)

    if not shutil.which("jq"):
        print("Error: jq is required for hooks. Install with: brew install jq")
        raise SystemExit(1)

    settings: dict = {}
    if os.path.exists(CLAUDE_SETTINGS_PATH):
        with open(CLAUDE_SETTINGS_PATH) as f:
            try:
                settings = json.load(f)
            except json.JSONDecodeError:
                print(f"Error: {CLAUDE_SETTINGS_PATH} contains invalid JSON.")
                print("Fix or back up the file before running setup-hooks.")
                raise SystemExit(1)

    hook_entry = {
        "hooks": [
            {
                "type": "command",
                "command": HOOK_INSTALLED_PATH,
                "timeout": 30,
            }
        ]
    }

    hooks = settings.get("hooks", {})
    stop_hooks = hooks.get("Stop", [])

    already_installed = any(
        any(h.get("command") == HOOK_INSTALLED_PATH for h in entry.get("hooks", []))
        for entry in stop_hooks
    )

    if already_installed:
        # Update the script in case it changed
        _install_hook_script()
        print("Hooks already configured. Script updated.")
        return

    _install_hook_script()
    stop_hooks.append(hook_entry)
    hooks["Stop"] = stop_hooks
    settings["hooks"] = hooks

    _atomic_write_json(CLAUDE_SETTINGS_PATH, settings)

    print(f"Stop hook installed in {CLAUDE_SETTINGS_PATH}")
    print(f"Script: {HOOK_INSTALLED_PATH}")
    print(f"Signals will be written to {SIGNAL_DIR}/")


def cmd_remove_hooks(args: argparse.Namespace) -> None:
    if not os.path.exists(CLAUDE_SETTINGS_PATH):
        print("No Claude settings found.")
        return

    with open(CLAUDE_SETTINGS_PATH) as f:
        try:
            settings = json.load(f)
        except json.JSONDecodeError:
            print(f"Error: {CLAUDE_SETTINGS_PATH} contains invalid JSON.")
            print("Fix or back up the file before running remove-hooks.")
            raise SystemExit(1)

    hooks = settings.get("hooks", {})
    stop_hooks = hooks.get("Stop", [])

    filtered = [
        entry for entry in stop_hooks
        if not any(h.get("command") == HOOK_INSTALLED_PATH for h in entry.get("hooks", []))
    ]

    if len(filtered) == len(stop_hooks):
        print("Hook not found in settings.")
        return

    if filtered:
        hooks["Stop"] = filtered
    else:
        del hooks["Stop"]

    if hooks:
        settings["hooks"] = hooks
    else:
        del settings["hooks"]

    _atomic_write_json(CLAUDE_SETTINGS_PATH, settings)

    if os.path.exists(HOOK_INSTALLED_PATH):
        os.unlink(HOOK_INSTALLED_PATH)

    print("Stop hook removed.")


def _atomic_consume(signal_path: str) -> dict | None:
    """Atomically rename the signal file before reading to avoid race conditions."""
    consumed_path = signal_path + ".consumed"
    try:
        os.rename(signal_path, consumed_path)
    except FileNotFoundError:
        return None
    try:
        with open(consumed_path) as f:
            data = json.load(f)
    except json.JSONDecodeError:
        print(f"Warning: malformed signal file left at {consumed_path}", file=sys.stderr)
        return None
    try:
        os.unlink(consumed_path)
    except OSError:
        pass
    return data


def read_signal(session_id: str) -> dict | None:
    signal_path = os.path.join(SIGNAL_DIR, f"{session_id}.json")
    try:
        with open(signal_path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def consume_signal(session_id: str) -> dict | None:
    signal_path = os.path.join(SIGNAL_DIR, f"{session_id}.json")
    return _atomic_consume(signal_path)


def _print_signal(data: dict) -> None:
    name = data.get("session_name", data.get("session_id", "unknown"))
    print(f"\nSession completed: {name}")
    print(f"  Transcript: {data.get('transcript_path', 'N/A')}")
    print(f"  CWD: {data.get('cwd', 'N/A')}")
    print(f"  Completed at: {data.get('completed_at', 'N/A')}")


def cmd_wait(args: argparse.Namespace) -> None:
    timeout = args.timeout
    interval = args.interval
    session_filter = args.session
    deadline = time.monotonic() + timeout

    if args.clean:
        stale = glob.glob(os.path.join(SIGNAL_DIR, "*.json"))
        for f in stale:
            try:
                os.unlink(f)
            except OSError:
                pass
        if stale:
            print(f"Cleaned {len(stale)} stale signal(s).")

    if session_filter:
        print(f"Waiting for session '{session_filter}' to complete (timeout: {timeout}s)...")
    else:
        print(f"Waiting for any Claude session to complete (timeout: {timeout}s)...")

    while time.monotonic() < deadline:
        signals = glob.glob(os.path.join(SIGNAL_DIR, "*.json"))
        for signal_path in signals:
            if session_filter:
                fname = os.path.basename(signal_path)
                sid = fname.removesuffix(".json")
                if sid != session_filter:
                    continue

            data = _atomic_consume(signal_path)
            if data is None:
                continue

            _print_signal(data)
            return

        time.sleep(interval)

    print(f"\nTimeout after {timeout}s — no completion signal received.")
    raise SystemExit(1)


def cmd_read(args: argparse.Namespace) -> None:
    validate_session_name(args.session)
    if not is_tmux_session_alive(args.session):
        print(f"Error: session '{args.session}' not found. Run 'list' to see active sessions.")
        raise SystemExit(1)

    lines = min(max(args.lines, 1), MAX_CAPTURE_LINES)
    output = capture_pane(args.session, lines=lines)
    print(output)


def main() -> None:
    parser = argparse.ArgumentParser(description="tmux + Claude Code launcher")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser("start", help="Launch iTerm2 + tmux + Claude Code")
    start_parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Working directory for Claude Code (e.g. ~/Developer/myproject)",
    )
    start_parser.add_argument(
        "--name",
        default=None,
        help="Session name (default: random)",
    )
    start_parser.add_argument(
        "--saved",
        default=None,
        help="Use a saved session (name + path)",
    )
    start_parser.add_argument(
        "--layout",
        default="single",
        choices=LAYOUTS.keys(),
        help="iTerm2 pane layout (default: single)",
    )
    start_parser.add_argument(
        "--detach",
        action="store_true",
        help="Create tmux session without opening iTerm2",
    )

    save_parser = subparsers.add_parser("save", help="Save a session name + path")
    save_parser.add_argument("name", help="Session name")
    save_parser.add_argument("path", help="Working directory path")

    subparsers.add_parser("saved", help="List saved sessions")

    unsave_parser = subparsers.add_parser("unsave", help="Remove a saved session")
    unsave_parser.add_argument("name", help="Session name to remove")

    send_parser = subparsers.add_parser("send", help="Send a prompt to Claude Code")
    send_parser.add_argument("session", help="Session name")
    send_parser.add_argument("prompt", help="The prompt text to send")

    read_parser = subparsers.add_parser("read", help="Read current pane output")
    read_parser.add_argument("session", help="Session name")
    read_parser.add_argument(
        "--lines",
        type=int,
        default=200,
        help="Number of scrollback lines to capture (default: 200)",
    )

    kill_parser = subparsers.add_parser("kill", help="Kill a tmux session")
    kill_parser.add_argument("session", help="Session name to kill")

    subparsers.add_parser("list", help="List active tmux sessions")

    subparsers.add_parser("setup-hooks", help="Install Stop hook in Claude settings")
    subparsers.add_parser("remove-hooks", help="Remove Stop hook from Claude settings")

    wait_parser = subparsers.add_parser("wait", help="Wait for a session to complete")
    wait_parser.add_argument(
        "--session",
        default=None,
        help="Only wait for this specific session (default: any)",
    )
    wait_parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Max seconds to wait (default: 300)",
    )
    wait_parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Poll interval in seconds (default: 1.0)",
    )
    wait_parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove stale signal files before waiting",
    )

    args = parser.parse_args()

    preflight_check(args.command)

    if args.command == "start":
        cmd_start(args)
    elif args.command == "send":
        cmd_send(args)
    elif args.command == "read":
        cmd_read(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "save":
        cmd_save(args)
    elif args.command == "saved":
        cmd_saved(args)
    elif args.command == "unsave":
        cmd_unsave(args)
    elif args.command == "kill":
        cmd_kill(args)
    elif args.command == "setup-hooks":
        cmd_setup_hooks(args)
    elif args.command == "remove-hooks":
        cmd_remove_hooks(args)
    elif args.command == "wait":
        cmd_wait(args)


if __name__ == "__main__":
    main()
