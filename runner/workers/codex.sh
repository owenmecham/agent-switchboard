#!/usr/bin/env bash
# EXAMPLE - edit me. OpenAI Codex CLI, non-interactive.
set -euo pipefail
dir="$(grep -m1 '^repo_path:' "$TASK_FILE" | sed 's/^repo_path: *//; s/"//g' || true)"
cd "${dir:-.}"
codex exec "$(cat "$TASK_FILE")"
