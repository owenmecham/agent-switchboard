import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))

from switchboard import mini_yaml, routing, taskfile  # noqa: E402
from switchboard.cli import process_once  # noqa: E402
from switchboard.queues import FolderQueue  # noqa: E402

EXAMPLE = mini_yaml.loads((ROOT / "routing/rules.example.yml").read_text())
DEMO = mini_yaml.loads((ROOT / "routing/rules.demo.yml").read_text())


def task(type_, tags=(), **meta):
    return taskfile.Task(meta={"id": "t1", "type": type_, "tags": list(tags), **meta}, body="")


def env(os_name="linux", **vars_):
    return {"os": os_name, "env": vars_}


class Routing(unittest.TestCase):
    def test_research_goes_to_grok_then_deepseek(self):
        d = routing.route(task("research"), EXAMPLE, env(XAI_API_KEY="x", DEEPSEEK_API_KEY="y"))
        self.assertEqual(d["candidates"], ["grok", "deepseek"])

    def test_missing_key_falls_back(self):
        d = routing.route(task("research"), EXAMPLE, env(DEEPSEEK_API_KEY="y"))
        self.assertEqual(d["candidates"], ["deepseek"])
        self.assertIn("grok", d["skipped"])

    def test_send_always_needs_human(self):
        d = routing.route(task("send"), EXAMPLE, env(XAI_API_KEY="x"))
        self.assertEqual(d["action"], "needs-human")

    def test_unknown_type_hits_catch_all(self):
        d = routing.route(task("interpretive-dance"), EXAMPLE, env())
        self.assertEqual(d["action"], "needs-human")
        self.assertIn("no rule", d["reason"])

    def test_mac_only_skipped_on_linux(self):
        d = routing.route(task("code", tags=["ui"]), DEMO, env("linux"))
        self.assertEqual(d["candidates"], ["echo"])
        d = routing.route(task("code", tags=["ui"]), DEMO, env("macos"))
        self.assertEqual(d["candidates"], ["mac-thing", "echo"])

    def test_route_hint_goes_first(self):
        d = routing.route(task("review", route={"worker": "echo"}), DEMO, env())
        self.assertEqual(d["candidates"], ["echo", "broken"])

    def test_nothing_available_needs_human(self):
        d = routing.route(task("code"), EXAMPLE, env())  # no claude/codex binaries in CI
        if d["action"] == "needs-human":
            self.assertIn("no available worker", d["reason"])


class Yaml(unittest.TestCase):
    def test_roundtrip_frontmatter(self):
        t = task("code", tags=["a", "b"], title="Fix: the thing", route={"worker": "codex"})
        back = taskfile.parse(taskfile.render(t))
        self.assertEqual(back.meta, t.meta)


class FolderRoundTrip(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        shutil.copytree(ROOT / "examples/demo-vault/agent-switchboard", self.dir / "q")
        self.q = FolderQueue(self.dir / "q")

    def tearDown(self):
        shutil.rmtree(self.dir)

    def status(self, prefix):
        p = next((self.dir / "q/tasks").glob(prefix + "*.md"))
        return taskfile.parse(p.read_text()).meta["status"], p.read_text()

    def test_dry_run_changes_nothing(self):
        before = {p.name: p.read_text() for p in (self.dir / "q/tasks").glob("*.md")}
        process_once(self.q, DEMO, dry_run=True, env=env())
        after = {p.name: p.read_text() for p in (self.dir / "q/tasks").glob("*.md")}
        self.assertEqual(before, after)

    def test_full_round_trip(self):
        process_once(self.q, DEMO, env=env())
        s, text = self.status("2026-01-15-001")
        self.assertEqual(s, "done")
        self.assertIn("## Result", text)
        self.assertIn("echo-worker handled task 2026-01-15-001", text)
        s, text = self.status("2026-01-15-002")      # broken -> fallback echo
        self.assertEqual(s, "done")
        self.assertIn("worker: echo", text)
        s, _ = self.status("2026-01-15-003")         # send -> human
        self.assertEqual(s, "needs-human")
        self.assertEqual(list((self.dir / "q/.locks").iterdir()), [])
        self.assertEqual(process_once(self.q, DEMO, env=env()), [])  # runs once only

    def test_claim_is_exclusive(self):
        t = self.q.list_queued()[0]
        t2 = self.q.list_queued()[0]
        self.assertTrue(self.q.claim(t, "runner-a"))
        self.assertFalse(self.q.claim(t2, "runner-b"))

    def test_all_fail_escalates(self):
        rules = {"settings": {}, "workers": {"broken": {"command": "runner/workers/fail.sh"}},
                 "rules": [{"name": "x", "match": {}, "worker": "broken"}]}
        process_once(self.q, rules, env=env())
        s, text = self.status("2026-01-15-001")
        self.assertEqual(s, "needs-human")
        self.assertIn("pretending something broke", text)


if __name__ == "__main__":
    unittest.main()
