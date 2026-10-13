"""Read and write task files: Markdown with YAML frontmatter (see spec/task-format.md)."""
from dataclasses import dataclass, field
from datetime import datetime, timezone

from . import mini_yaml

STATUSES = ("queued", "claimed", "running", "done", "failed", "needs-human")


@dataclass
class Task:
    meta: dict
    body: str
    ref: object = None          # where it lives: a Path (folder) or issue number (github)
    extra: dict = field(default_factory=dict)

    @property
    def id(self):
        return str(self.meta.get("id"))

    @property
    def type(self):
        return self.meta.get("type", "general")

    @property
    def tags(self):
        return list(self.meta.get("tags") or [])

    @property
    def status(self):
        return self.meta.get("status", "queued")


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse(text, ref=None):
    if not text.startswith("---"):
        raise ValueError("task file must start with '---' frontmatter")
    _, fm, body = text.split("---", 2)
    meta = mini_yaml.loads(fm) or {}
    if "id" not in meta:
        raise ValueError("task frontmatter needs an 'id'")
    return Task(meta=meta, body=body.lstrip("\n"), ref=ref)


def render(task):
    return "---\n" + mini_yaml.dump_flat(task.meta) + "---\n\n" + task.body.rstrip() + "\n"


def result_section(status, worker, output, note=""):
    lines = ["", "## Result", "",
             f"- status: {status}",
             f"- worker: {worker}",
             f"- finished: {now_iso()}"]
    if note:
        lines.append(f"- note: {note}")
    lines += ["", "```text", output.rstrip() or "(no output)", "```", ""]
    return "\n".join(lines)
