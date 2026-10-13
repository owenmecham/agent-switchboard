# Shared helpers for worker scripts. Source me.
# get_secret NAME: read from env first, then the macOS Keychain (service = NAME).
#   Store a key once with:  security add-generic-password -a "$USER" -s DEEPSEEK_API_KEY -w
get_secret() {
  local name="$1" val="${!1:-}"
  if [ -z "$val" ] && command -v security >/dev/null 2>&1; then
    val="$(security find-generic-password -s "$name" -w 2>/dev/null || true)"
  fi
  [ -n "$val" ] || { echo "missing secret $name (set env var or Keychain item)" >&2; exit 2; }
  printf '%s' "$val"
}
# chat_api URL KEY MODEL: send the task file as one user message to an
# OpenAI-compatible /chat/completions endpoint and print the reply.
chat_api() {
  python3 - "$1" "$2" "$3" <<'PY'
import json, os, sys, urllib.request
url, key, model = sys.argv[1:4]
task = open(os.environ["TASK_FILE"], encoding="utf-8").read()
req = urllib.request.Request(url, method="POST",
    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    data=json.dumps({"model": model, "messages": [
        {"role": "system", "content": "You are a worker in an agent switchboard. Do the task below and reply with the result only."},
        {"role": "user", "content": task}]}).encode())
print(json.load(urllib.request.urlopen(req, timeout=600))["choices"][0]["message"]["content"])
PY
}
