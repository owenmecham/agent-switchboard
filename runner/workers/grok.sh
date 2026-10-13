#!/usr/bin/env bash
# EXAMPLE - edit me. xAI Grok API (OpenAI-compatible). Use for research / writing tasks.
set -euo pipefail
source "$(dirname "$0")/_common.sh"
chat_api "https://api.x.ai/v1/chat/completions" "$(get_secret XAI_API_KEY)" "${GROK_MODEL:-grok-4}"
