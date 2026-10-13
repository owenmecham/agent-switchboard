"""The status digest: one small note/issue/page listing open and recently finished tasks,
so a Grok check-in reads ONE thing instead of scanning the whole queue.

The runner keeps a little local state file (JSON) of what it has seen, and after every
poll rewrites the digest into each reachable queue (folder: status.md, GitHub: an issue
labeled switchboard:status, Notion: a page you choose, MCP notes: a note).
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .taskfile import now_iso

OPEN = ("queued", "claimed", "running")


def load(path):
    p = Path(path).expanduser()
    return json.loads(p.read_text()) if p.exists() else {"tasks": {}}


def save(state, path):
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=1))


def record(state, queue_name, task, status, worker=None, note=""):
    state["tasks"][task.id] = {"title": task.meta.get("title", ""), "queue": queue_name,
                               "status": status, "worker": worker, "note": note,
                               "updated": now_iso()}


def render(state, keep_hours=48):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=keep_hours)
    rows = sorted(state["tasks"].items(), key=lambda kv: kv[1]["updated"], reverse=True)
    open_, recent = [], []
    for tid, t in rows:
        if t["status"] in OPEN:
            open_.append((tid, t))
        elif datetime.fromisoformat(t["updated"]) >= cutoff:
            recent.append((tid, t))

    def line(tid, t):
        extra = f" via {t['worker']}" if t.get("worker") else ""
        note = f" ({t['note']})" if t.get("note") else ""
        return f"| {tid} | {t['title']} | {t['status']}{extra}{note} | {t['queue']} | {t['updated']} |"

    out = ["---", "type: switchboard-status", f"updated: {now_iso()}",
           f"open: {len(open_)}", f"needs_human: {sum(t['status'] == 'needs-human' for _, t in recent)}",
           "---", "", "# Switchboard status", "",
           "## Open", "", "| id | title | status | queue | updated |", "|---|---|---|---|---|"]
    out += [line(*r) for r in open_] or ["| - | nothing open | | | |"]
    out += ["", f"## Finished (last {keep_hours}h)", "",
            "| id | title | status | queue | updated |", "|---|---|---|---|---|"]
    out += [line(*r) for r in recent] or ["| - | nothing yet | | | |"]
    return "\n".join(out) + "\n"
