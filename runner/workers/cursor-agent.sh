#!/usr/bin/env bash
# EXAMPLE - edit me. Cursor's CLI agent, headless.
#   --print                 non-interactive; --output-format text = final answer only
#   --force                 allow file edits without prompting (remove for read-only work)
#   --trust                 trust the workspace without a prompt
# The binary is `cursor-agent` (newer installs also ship it as `agent`).
# For Cursor/Grok *cloud* agents, swap this for that product's background-agent API.
set -euo pipefail
source "$(dirname "$0")/_common.sh"
export CURSOR_API_KEY="$(get_secret CURSOR_API_KEY)"
dir="$(grep -m1 '^repo_path:' "$TASK_FILE" | sed 's/^repo_path: *//; s/"//g' || true)"
cd "${dir/#\~/$HOME}" 2>/dev/null || cd .
"${CURSOR_AGENT_BIN:-cursor-agent}" --print --force --trust --output-format text "$(cat "$TASK_FILE")" < /dev/null
