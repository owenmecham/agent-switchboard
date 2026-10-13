"""Any MCP "notes" server as a queue (e.g. Cloud Brain, basic-memory style servers).

The runner speaks MCP's Streamable HTTP transport directly: JSON-RPC 2.0 over POST,
`initialize` once, then `tools/call`. Tool names and argument shapes differ between servers,
so they're mapped in config (see runner/queues.example.yml). Placeholders in args:
  {folder}  the queue folder     {path}  a note's path     {title}  note title
  {content} note text            {find} / {replace}         text to swap

Claiming uses the server's find/replace edit as a compare-and-swap: replace
"status: queued" with "status: claimed". If the server reports that the text wasn't found,
someone else already took it.

Can't or don't want to call MCP from the runner? See docs: sync the notes to a local folder
and use the folder queue instead.
"""
import json
import re

from . import http as _http
from . import taskfile
from .secrets import get_secret
from .taskfile import now_iso

FM = re.compile(r"^---\n(.*?)\n---[ \t]*$", re.S | re.M)


class McpClient:
    def __init__(self, url, token_name=None, http=None):
        self.url, self.token_name, self._http = url, token_name, http
        self.session, self._id = None, 0

    def _post(self, payload):
        if self._http:
            return self._http(payload)
        headers = {"Accept": "application/json, text/event-stream"}
        if self.token_name:
            headers["Authorization"] = f"Bearer {get_secret(self.token_name)}"
        if self.session:
            headers["Mcp-Session-Id"] = self.session
        _, rh, text = _http.request("POST", self.url, headers, payload)
        sid = {k.lower(): v for k, v in rh.items()}.get("mcp-session-id")
        if sid:
            self.session = sid
        if not text.strip():
            return None
        if text.lstrip().startswith("{"):
            return json.loads(text)
        for line in text.splitlines():           # Server-Sent Events: take the response event
            if line.startswith("data:"):
                msg = json.loads(line[5:].strip())
                if msg.get("id") == payload.get("id"):
                    return msg
        return None

    def _rpc(self, method, params):
        self._id += 1
        msg = self._post({"jsonrpc": "2.0", "id": self._id, "method": method, "params": params})
        if msg is None:
            raise RuntimeError(f"MCP {method}: no response")
        if "error" in msg:
            raise RuntimeError(f"MCP {method}: {msg['error']}")
        return msg["result"]

    def connect(self):
        if self.session is not None or self._id:
            return
        self._rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                 "clientInfo": {"name": "agent-switchboard", "version": "1"}})
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def call(self, name, arguments):
        """Returns (ok, text). ok is False when the tool reports isError."""
        self.connect()
        res = self._rpc("tools/call", {"name": name, "arguments": arguments})
        text = "\n".join(c.get("text", "") for c in res.get("content", []) if c.get("type") == "text")
        if not text and "structuredContent" in res:
            text = json.dumps(res["structuredContent"])
        return not res.get("isError", False), text


def _fill(template, **values):
    if isinstance(template, str):
        return re.sub(r"\{(\w+)\}", lambda m: str(values.get(m.group(1), m.group(0))), template)
    if isinstance(template, dict):
        return {k: _fill(v, **values) for k, v in template.items()}
    if isinstance(template, list):
        return [_fill(v, **values) for v in template]
    return template


class McpNotesQueue:
    name = "mcp-notes"

    def __init__(self, url, folder, tools, token_name=None, path_regex=r"[\w.][\w./ \-]*\.md",
                 status_note_title="switchboard status", client=None):
        self.folder = folder.rstrip("/")
        self.tools = tools
        self.path_re = re.compile(path_regex)
        self.status_title = status_note_title
        self.mcp = client or McpClient(url, token_name)

    def _tool(self, op, **values):
        spec = self.tools[op]
        ok, text = self.mcp.call(spec["name"], _fill(spec.get("args", {}), folder=self.folder, **values))
        return ok, text

    @staticmethod
    def _note_text(raw):
        try:
            data = json.loads(raw)
            if isinstance(data, dict) and isinstance(data.get("content"), str):
                return data["content"]
        except ValueError:
            pass
        return raw

    def _read(self, path):
        ok, raw = self._tool("read", path=path)
        if not ok:
            return None
        text = self._note_text(raw)
        # the server may add its own frontmatter; use the block that has our id + status
        m = next((m for m in FM.finditer(text)
                  if re.search(r"^id:", m.group(1), re.M) and re.search(r"^status:", m.group(1), re.M)), None)
        if not m:
            return None
        try:
            return taskfile.parse(text[m.start():], ref=path)
        except ValueError:
            return None

    def list_queued(self):
        ok, listing = self._tool("list")
        if not ok:
            raise RuntimeError(f"mcp list failed: {listing[:200]}")
        paths = list(dict.fromkeys(p.strip() for p in self.path_re.findall(listing)))
        out = []
        for p in paths:
            t = self._read(p)
            if t and t.status == "queued":
                out.append(t)
        return out

    def _swap_status(self, task, old, new):
        ok, _ = self._tool("find_replace", path=task.ref, find=f"status: {old}", replace=f"status: {new}")
        return ok

    def claim(self, task, runner_id):
        if not self._swap_status(task, "queued", "claimed"):
            return False
        task.meta["status"] = "claimed"
        self._tool("append", path=task.ref, content=f"\n- claimed by {runner_id} at {now_iso()}\n")
        return True

    def set_status(self, task, status, **kv):
        old = task.meta.get("status", "queued")
        if old != status:
            self._swap_status(task, old, status)
        task.meta["status"] = status
        task.meta.update(kv)

    def write_result(self, task, status, worker, output, note=""):
        self._tool("append", path=task.ref, content=taskfile.result_section(status, worker, output, note))
        self.set_status(task, status, worker=worker)

    def release(self, task):
        pass

    def write_digest(self, markdown):
        if "write" in self.tools:
            self._tool("write", title=self.status_title, content=markdown)
