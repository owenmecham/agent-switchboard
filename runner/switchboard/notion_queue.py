"""Notion database as a queue (Notion REST API via urllib, no SDK).

Database setup (property names are configurable, these are the defaults):
  Name      title         task title
  Task ID   rich_text     the task id (falls back to the page id)
  Status    select        queued / claimed / running / done / failed / needs-human
  Type      select        research, code, review ...
  Priority  select        optional
  Tags      multi_select  optional
  Worker    rich_text     optional, filled in by the runner
The task instructions are the page body. The result is appended to the page as blocks.
Share the database with your Notion integration ("..." menu > Connections).
Token: env var or Keychain item NOTION_TOKEN (configurable).
"""
import json

from . import http as _http
from . import taskfile
from .secrets import get_secret
from .taskfile import Task, now_iso

API = "https://api.notion.com/v1"
VERSION = "2022-06-28"
DEFAULT_PROPS = {"title": "Name", "id": "Task ID", "status": "Status", "type": "Type",
                 "priority": "Priority", "tags": "Tags", "worker": "Worker"}


class NotionQueue:
    name = "notion"

    def __init__(self, database_id, token_name="NOTION_TOKEN", properties=None,
                 status_property_type="select", status_page_id=None, http=None):
        self.db = database_id
        self.props = {**DEFAULT_PROPS, **(properties or {})}
        self.status_type = status_property_type      # "select" or Notion's built-in "status"
        self.status_page_id = status_page_id
        self._token_name = token_name
        self._http = http                             # fake in tests

    # -- plumbing -----------------------------------------------------------
    def _call(self, method, path, body=None):
        if self._http:
            return self._http(method, path, body)
        headers = {"Authorization": f"Bearer {get_secret(self._token_name)}",
                   "Notion-Version": VERSION}
        _, _, text = _http.request(method, API + path, headers, body)
        return json.loads(text) if text else {}

    @staticmethod
    def _plain(prop):
        if not prop:
            return None
        t = prop.get("type")
        if t in ("title", "rich_text"):
            return "".join(x.get("plain_text", x.get("text", {}).get("content", "")) for x in prop[t]) or None
        if t in ("select", "status"):
            return (prop[t] or {}).get("name")
        if t == "multi_select":
            return [x["name"] for x in prop[t]]
        return None

    def _page_to_task(self, page):
        p, P = page["properties"], self.props
        meta = {"id": self._plain(p.get(P["id"])) or page["id"],
                "title": self._plain(p.get(P["title"])) or "",
                "type": self._plain(p.get(P["type"])) or "general",
                "priority": self._plain(p.get(P["priority"])) or "normal",
                "tags": self._plain(p.get(P["tags"])) or [],
                "requested_by": "notion",
                "status": self._plain(p.get(P["status"])) or "queued"}
        return Task(meta=meta, body=self._body(page["id"]), ref=page["id"])

    def _body(self, page_id):
        out = []
        for b in self._call("GET", f"/blocks/{page_id}/children?page_size=100").get("results", []):
            rich = (b.get(b.get("type"), {}) or {}).get("rich_text", [])
            out.append("".join(x.get("plain_text", x.get("text", {}).get("content", "")) for x in rich))
        return "\n".join(out)

    def _status_value(self, status):
        return {self.status_type: {"name": status}}

    # -- contract -----------------------------------------------------------
    def list_queued(self):
        flt = {"property": self.props["status"], self.status_type: {"equals": "queued"}}
        res = self._call("POST", f"/databases/{self.db}/query", {"filter": flt, "page_size": 50})
        return [self._page_to_task(pg) for pg in res.get("results", [])]

    def claim(self, task, runner_id):
        # Notion has no compare-and-swap. Re-check then set; run one runner per database.
        page = self._call("GET", f"/pages/{task.ref}")
        if self._plain(page["properties"].get(self.props["status"])) != "queued":
            return False
        self.set_status(task, "claimed", claimed_by=runner_id)
        return True

    def set_status(self, task, status, **kv):
        task.meta["status"] = status
        task.meta.update(kv)
        props = {self.props["status"]: self._status_value(status)}
        if "worker" in kv and self.props.get("worker"):
            props[self.props["worker"]] = {"rich_text": [{"text": {"content": str(kv["worker"])}}]}
        self._call("PATCH", f"/pages/{task.ref}", {"properties": props})

    def write_result(self, task, status, worker, output, note=""):
        text = output.rstrip() or "(no output)"
        chunks = [text[i:i + 1900] for i in range(0, len(text), 1900)][:50]  # Notion: 2000 chars/block
        bullets = [f"status: {status}", f"worker: {worker}", f"finished: {now_iso()}"] + ([f"note: {note}"] if note else [])
        blocks = [{"object": "block", "type": "heading_2",
                   "heading_2": {"rich_text": [{"text": {"content": "Result"}}]}}]
        blocks += [{"object": "block", "type": "bulleted_list_item",
                    "bulleted_list_item": {"rich_text": [{"text": {"content": b}}]}} for b in bullets]
        blocks += [{"object": "block", "type": "code",
                    "code": {"language": "plain text", "rich_text": [{"text": {"content": c}}]}} for c in chunks]
        self._call("PATCH", f"/blocks/{task.ref}/children", {"children": blocks})
        self.set_status(task, status, worker=worker)

    def release(self, task):
        pass

    def write_digest(self, markdown):
        if not self.status_page_id:
            return
        for b in self._call("GET", f"/blocks/{self.status_page_id}/children?page_size=100").get("results", []):
            self._call("DELETE", f"/blocks/{b['id']}")
        lines = markdown.splitlines()[:90]
        self._call("PATCH", f"/blocks/{self.status_page_id}/children", {"children": [
            {"object": "block", "type": "paragraph",
             "paragraph": {"rich_text": [{"text": {"content": ln[:1900]}}]}} for ln in lines if ln.strip()]})
