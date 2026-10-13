"""Tiny JSON-over-HTTP helper (urllib). Adapters take an `http` callable so tests can fake it."""
import json
import urllib.error
import urllib.request


def request(method, url, headers=None, body=None, timeout=60):
    """Returns (status, response_headers, text)."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=dict(headers or {}))
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, dict(r.headers), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {url} -> HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:500]}")
