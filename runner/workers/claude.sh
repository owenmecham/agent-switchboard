#!/usr/bin/env bash
# EXAMPLE - edit me. Claude Code CLI in non-interactive ("print") mode.
# Runs in the repo named by the task's `repo_path:` line, or the current dir.
# Claude Code may edit files there. Keep it on a branch; a human merges.
set -euo pipefail
dir="$(grep -m1 '^repo_path:' "$TASK_FILE" | sed 's/^repo_path: *//; s/"//g' || true)"
cd "${dir:-.}"
claude -p "$(cat "$TASK_FILE")" --output-format text
