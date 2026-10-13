#!/usr/bin/env bash
# EXAMPLE - edit me. OpenAI Codex CLI, non-interactive.
#   --sandbox workspace-write  lets it edit files in the repo (no network). Use read-only for reviews.
#   -o FILE                    writes just the final message, which we print as the result.
# (`--full-auto` was removed from newer Codex versions; don't use it.)
set -euo pipefail
dir="$(grep -m1 '^repo_path:' "$TASK_FILE" | sed 's/^repo_path: *//; s/"//g' || true)"
last="$(mktemp)"; trap 'rm -f "$last"' EXIT
codex exec --sandbox "${CODEX_SANDBOX:-workspace-write}" -C "${dir/#\~/$HOME}" \
  -o "$last" "$(cat "$TASK_FILE")" < /dev/null >&2
cat "$last"
