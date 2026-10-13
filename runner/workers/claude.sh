#!/usr/bin/env bash
# EXAMPLE - edit me. Claude Code CLI in non-interactive ("print") mode.
#   -p PROMPT               run once and exit
#   --output-format text    print only the final answer
#   --permission-mode / --allowedTools  decide what it may do without asking. Start narrow.
# Runs in the task's `repo_path:` (or the current dir). Keep it on a branch; a human merges.
set -euo pipefail
dir="$(grep -m1 '^repo_path:' "$TASK_FILE" | sed 's/^repo_path: *//; s/"//g' || true)"
cd "${dir/#\~/$HOME}" 2>/dev/null || cd .
claude -p "$(cat "$TASK_FILE")" --output-format text \
  --permission-mode "${CLAUDE_PERMISSION_MODE:-acceptEdits}" \
  --allowedTools "${CLAUDE_ALLOWED_TOOLS:-Read,Edit,Write,Grep,Glob,Bash(git:*)}" < /dev/null
