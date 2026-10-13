"""Notion, MCP-notes, failover and digest tests, all with in-memory fakes (no network)."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))

from switchboard import mini_yaml  # noqa: E402
from switchboard.cli import run_all  # noqa: E402
from switchboard.mcp_queue import McpClient, McpNotesQueue  # noqa: E402
from switchboard.notion_queue import NotionQueue  # noqa: E402
from switchboard.queues import FolderQueue  # noqa: E402

DEMO = mini_yaml.loads((ROOT / "routing/rules.demo.yml").read_text())
ENV = {"os": "linux", "env": {}}


# ---------------------------------------------------------------- Notion fake
class FakeNotion:
    def __init__(self):
        self.pages = {}
        self.children = {}

    def add(self, pid, title, type_, status="queued"):
        sel = lambda v: {"type": "select", "select": {"name": v}}
        self.pages[pid] = {"id": pid, "properties": {
            "Name": {"type": "title", "title": [{"plain_text": title}]},
            "Task ID": {"type": "rich_text", "rich_text": [{"plain_text": "n-" + pid}]},
            "Status": sel(status), "Type": sel(type_),
            "Tags": {"type": "multi_select", "multi_select": []}}}
        self.children[pid] = [{"id": pid + "-b1", "type": "paragraph",
                               "paragraph": {"rich_text": [{"plain_text": "Do the thing."}]}}]

    def status(self, pid):
        return self.pages[pid]["properties"]["Status"]["select"]["name"]

    def __call__(self, method, path, body):
        parts = path.split("?")[0].strip("/").split("/")
        if method == "POST" and parts[0] == "databases":
            want = body["filter"]["select"]["equals"]
            return {"results": [p for pid, p in self.pages.items() if self.status(pid) == want]}
        if parts[0] == "pages" and method == "GET":
            return self.pages[parts[1]]
        if parts[0] == "pages" and method == "PATCH":
            for k, v in body["properties"].items():
                self.pages[parts[1]]["properties"][k] = {"type": next(iter(v)), **v}
            return {}
        if parts[0] == "blocks" and method == "GET":
            return {"results": self.children.get(parts[1], [])}
        if parts[0] == "blocks" and method == "PATCH":
            self.children.setdefault(parts[1], []).extend(body["children"])
            return {}
        if parts[0] == "blocks" and method == "DELETE":
            for k in self.children:
                self.children[k] = [b for b in self.children[k] if b.get("id") != parts[1]]
            return {}
        raise AssertionError(f"unexpected {method} {path}")


class NotionTests(unittest.TestCase):
    def test_round_trip(self):
        fake = FakeNotion()
        fake.add("p1", "Research desks", "research")
        fake.add("p2", "Email landlord", "send")
        fake.add("p3", "Old one", "research", status="done")
        fake.children["status"] = [{"id": "old", "type": "paragraph", "paragraph": {"rich_text": []}}]
        q = NotionQueue("db", http=fake, status_page_id="status")
        tasks = q.list_queued()
        self.assertEqual([t.id for t in tasks], ["n-p1", "n-p2"])
        self.assertIn("Do the thing.", tasks[0].body)
        run_all([q], DEMO, env=ENV)
        self.assertEqual(fake.status("p1"), "done")
        self.assertEqual(fake.status("p2"), "needs-human")
        self.assertEqual(fake.status("p3"), "done")
        kinds = [b["type"] for b in fake.children["p1"]]
        self.assertIn("heading_2", kinds)
        code = [b for b in fake.children["p1"] if b["type"] == "code"][0]
        self.assertIn("echo-worker handled task n-p1", code["code"]["rich_text"][0]["text"]["content"])
        self.assertEqual(fake.pages["p1"]["properties"]["Worker"]["rich_text"][0]["text"]["content"], "echo")
        digest = " ".join(b["paragraph"]["rich_text"][0]["text"]["content"] for b in fake.children["status"])
        self.assertIn("n-p1", digest)
        self.assertNotIn("old", [b.get("id") for b in fake.children["status"]])

    def test_claim_rechecks(self):
        fake = FakeNotion()
        fake.add("p1", "x", "research")
        q = NotionQueue("db", http=fake)
        t = q.list_queued()[0]
        self.assertTrue(q.claim(t, "a"))
        self.assertFalse(q.claim(t, "b"))


# ---------------------------------------------------------------- MCP fake
class FakeMcpServer:
    """Pretends to be a notes MCP server reached over JSON-RPC (Streamable HTTP payloads)."""

    def __init__(self):
        self.notes = {}
        self.calls = []

    def __call__(self, payload):
        self.calls.append(payload.get("method"))
        if "id" not in payload:
            return None  # notification
        if payload["method"] == "initialize":
            return {"jsonrpc": "2.0", "id": payload["id"], "result": {"capabilities": {}}}
        a = payload["params"]["arguments"]
        name = payload["params"]["name"]
        ok, text = True, ""
        if name == "list_directory":
            text = "\n".join(f"- {p}" for p in self.notes if p.startswith(a["path"]))
        elif name == "read_note":
            # servers often add their own metadata frontmatter on top
            text = "---\ntitle: whatever\npermalink: x\n---\n\n" + self.notes[a["file_path"]]
        elif name == "edit_note" and a["operation"] == "find_replace":
            n = self.notes[a["file_path"]]
            if a["find"] in n:
                self.notes[a["file_path"]] = n.replace(a["find"], a["replace"], 1)
            else:
                ok, text = False, "find text not found"
        elif name == "edit_note" and a["operation"] == "append":
            self.notes[a["file_path"]] += a["content"]
        elif name == "write_note":
            self.notes[a["folder"] + "/" + a["title"]] = a["content"]
        return {"jsonrpc": "2.0", "id": payload["id"],
                "result": {"content": [{"type": "text", "text": text}], "isError": not ok}}


TASK = """---
id: {id}
title: {title}
type: {type}
status: queued
---

## Task
Something.
"""


class McpTests(unittest.TestCase):
    def setUp(self):
        self.srv = FakeMcpServer()
        self.srv.notes["sb/tasks/a.md"] = TASK.format(id="m-1", title="Research", type="research")
        self.srv.notes["sb/tasks/b.md"] = TASK.format(id="m-2", title="Review", type="review")
        tools = mini_yaml.loads((ROOT / "runner/queues.example.yml").read_text())["queues"][1]["tools"]
        self.q = McpNotesQueue("http://fake", "sb/tasks", tools, client=McpClient("http://fake", http=self.srv))

    def test_round_trip(self):
        run_all([self.q], DEMO, env=ENV)
        self.assertEqual(self.srv.calls[:2], ["initialize", "notifications/initialized"])
        a = self.srv.notes["sb/tasks/a.md"]
        self.assertIn("status: done", a)
        self.assertIn("## Result", a)
        self.assertIn("echo-worker handled task m-1", a)
        self.assertIn("status: done", self.srv.notes["sb/tasks/b.md"])   # broken -> echo fallback
        self.assertIn("m-2", self.srv.notes["agent-switchboard/switchboard status"])
        self.assertEqual(run_all([self.q], DEMO, env=ENV), [])

    def test_claim_is_compare_and_swap(self):
        t = self.q.list_queued()[0]
        self.assertTrue(self.q.claim(t, "a"))
        self.assertFalse(self.q.claim(t, "b"))

    def test_sse_response_parsing(self):
        import switchboard.http as h
        orig = h.request
        h.request = lambda *a, **k: (200, {"Mcp-Session-Id": "s1"},
                                     'event: message\ndata: {"jsonrpc":"2.0","id":1,"result":{}}\n\n')
        try:
            c = McpClient("http://fake")
            self.assertEqual(c._rpc("initialize", {}), {})
            self.assertEqual(c.session, "s1")
        finally:
            h.request = orig


# ---------------------------------------------------------------- failover + digest
class Broken:
    name = "notion"

    def list_queued(self):
        raise RuntimeError("network down")


class FailoverTests(unittest.TestCase):
    def test_unreachable_primary_still_processes_folder(self):
        d = Path(tempfile.mkdtemp())
        try:
            shutil.copytree(ROOT / "examples/demo-vault/agent-switchboard", d / "q")
            folder = FolderQueue(d / "q")
            with self.assertLogs("switchboard", "ERROR") as logs:
                summary = run_all([Broken(), folder], DEMO, env=ENV, state_path=d / "state.json")
            self.assertIn("unreachable", logs.output[0])
            self.assertEqual(len(summary), 4)
            status = (d / "q/status.md").read_text()
            self.assertIn("# Switchboard status", status)
            self.assertIn("needs-human", status)
            self.assertIn("needs_human: 1", status)
            self.assertTrue((d / "state.json").exists())
        finally:
            shutil.rmtree(d)


if __name__ == "__main__":
    unittest.main()
