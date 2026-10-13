#!/usr/bin/env bash
# EXAMPLE - edit me. Cursor's CLI agent in print mode (local). For Cursor/Grok *cloud*
# agents, swap this for a call to that product's background-agent API.
set -euo pipefail
export CURSOR_API_KEY="$(source "$(dirname "$0")/_common.sh"; get_secret CURSOR_API_KEY)"
cursor-agent -p "$(cat "$TASK_FILE")" --output-format text
