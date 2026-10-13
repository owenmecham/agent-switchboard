#!/usr/bin/env bash
# EXAMPLE - edit me. Google Antigravity is a desktop (Mac) app. At time of writing it
# has no stable headless CLI, so this example opens the repo and hands off to a human
# by exiting non-zero with a clear note (the runner then marks the task needs-human).
# If your version has a CLI/agent command, replace the body below with it.
set -euo pipefail
dir="$(grep -m1 '^repo_path:' "$TASK_FILE" | sed 's/^repo_path: *//; s/"//g' || true)"
open -a "Antigravity" "${dir:-.}" 2>/dev/null || true
echo "Opened Antigravity for task $TASK_ID. Paste the task in and finish it there." >&2
exit 3
