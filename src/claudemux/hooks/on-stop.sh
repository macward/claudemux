#!/bin/bash
set -e

# Only run for sessions created by claudemux
if [[ "$CLAUDEMUX" != "1" ]]; then
    exit 0
fi

SIGNAL_DIR="/tmp/claude-tmux"
mkdir -p "$SIGNAL_DIR"

INPUT=$(cat)

SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty')
TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // empty')
CWD=$(echo "$INPUT" | jq -r '.cwd // empty')
SESSION_NAME="${CLAUDEMUX_SESSION:-$SESSION_ID}"

if [[ -z "$SESSION_ID" ]]; then
    echo "Error: missing session_id in hook input" >&2
    exit 1
fi

if [[ ! "$SESSION_NAME" =~ ^[a-zA-Z0-9_-]+$ ]]; then
    echo "Error: invalid session name '$SESSION_NAME'" >&2
    exit 1
fi

TMPFILE=$(mktemp "${SIGNAL_DIR}/${SESSION_NAME}.XXXXXX.tmp")

jq -n \
  --arg session_id "$SESSION_ID" \
  --arg session_name "$SESSION_NAME" \
  --arg transcript_path "$TRANSCRIPT_PATH" \
  --arg cwd "$CWD" \
  --arg completed_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  '{
    session_id: $session_id,
    session_name: $session_name,
    transcript_path: $transcript_path,
    cwd: $cwd,
    completed_at: $completed_at
  }' > "$TMPFILE"

mv "$TMPFILE" "${SIGNAL_DIR}/${SESSION_NAME}.json"

exit 0
