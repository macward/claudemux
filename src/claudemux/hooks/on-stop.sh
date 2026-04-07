#!/bin/bash
set -e

SIGNAL_DIR="/tmp/claude-tmux"
mkdir -p "$SIGNAL_DIR"

INPUT=$(cat)

SESSION_ID=$(echo "$INPUT" | jq -r '.session_id')

if [[ ! "$SESSION_ID" =~ ^[a-zA-Z0-9_-]+$ ]]; then
    echo "Error: invalid session_id '$SESSION_ID'" >&2
    exit 1
fi

TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path')
CWD=$(echo "$INPUT" | jq -r '.cwd')

TMPFILE=$(mktemp "${SIGNAL_DIR}/${SESSION_ID}.XXXXXX.tmp")

jq -n \
  --arg session_id "$SESSION_ID" \
  --arg transcript_path "$TRANSCRIPT_PATH" \
  --arg cwd "$CWD" \
  --arg completed_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  '{
    session_id: $session_id,
    transcript_path: $transcript_path,
    cwd: $cwd,
    completed_at: $completed_at
  }' > "$TMPFILE"

mv "$TMPFILE" "${SIGNAL_DIR}/${SESSION_ID}.json"

exit 0
