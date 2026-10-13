#!/usr/bin/env bash
# EXAMPLE - edit me. Google Antigravity via its `agy` CLI in headless print mode (Mac).
#   agy -p PROMPT --model M --effort E --output-format json --print-timeout Ns
# `agy models` lists the model slugs your account can use. JSON output has the final answer
# in `.response`. agy exits 3 on its own errors (details on a stderr line starting AGY_ERROR:).
# Billing note: if GEMINI_API_KEY is set, agy may bill the API instead of your subscription,
# so we unset it here. Remove that line if API billing is what you want.
set -euo pipefail
unset GEMINI_API_KEY
dir="$(grep -m1 '^repo_path:' "$TASK_FILE" | sed 's/^repo_path: *//; s/"//g' || true)"
cd "${dir/#\~/$HOME}" 2>/dev/null || cd .
timeout_s="${AGY_TIMEOUT_SECONDS:-1500}"
out="$(agy -p "$(cat "$TASK_FILE")" \
  --model "${AGY_MODEL:-gemini-3.8-flash-medium}" --effort "${AGY_EFFORT:-medium}" \
  --output-format json --print-timeout "${timeout_s}s" < /dev/null)"
python3 -c 'import json,sys; d=json.loads(sys.stdin.read()); print(d.get("response", d) if isinstance(d, dict) else d)' <<<"$out"
