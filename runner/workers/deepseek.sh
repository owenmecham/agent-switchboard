#!/usr/bin/env bash
# EXAMPLE - edit me. DeepSeek API (OpenAI-compatible). Good as a cheap second-opinion reviewer.
set -euo pipefail
source "$(dirname "$0")/_common.sh"
chat_api "https://api.deepseek.com/chat/completions" "$(get_secret DEEPSEEK_API_KEY)" "${DEEPSEEK_MODEL:-deepseek-chat}"
