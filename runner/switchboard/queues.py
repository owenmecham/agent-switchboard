"""Queue adapters. Each one implements the contract in spec/queue-adapter-contract.md:

    list_queued() -> [Task]          tasks with status 'queued'
    claim(task, runner_id) -> bool   atomically take a task; False if someone else did
    set_status(task, status, **kv)   move along the lifecycle
    write_result(task, status, worker, output, note="")
    release(task)                    drop any lock after finishing
"""
import json
import os
import subprocess
from pathlib import Path

from . import taskfile
from .taskfile import now_iso


class FolderQueue:
    """A folder of Markdown files. Works with an Obsidian vault, a synced Dropbox/iCloud
    folder, or anything that syncs files. Layout:
        <root>/tasks/*.md     one task per file (status lives in frontmatter)
        <root>/.locks/        lock files so two runners never take the same task
    """

    name = "folder"

    def __init__(self, root):
        self.root = Path(root).expanduser()
        self.tasks_dir = self.root / "tasks"
        self.locks_dir = self.root / ".locks"
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        self.locks_dir.mkdir(parents=True, exist_ok=True)

    def _load(self, path):
        return taskfile.parse(path.read_text(encoding="utf-8"), ref=path)

    def _save(self, task):
        tmp = task.ref.with_suffix(".md.tmp")
        tmp.write_text(taskfile.render(task), encoding="utf-8")
        os.replace(tmp, task.ref)  # atomic swap so sync tools never see half a file

    def list_queued(self):
        out = []
        for p in sorted(self.tasks_dir.glob("*.md")):
            try:
                t = self._load(p)
            except ValueError:
                continue  # not a task file (e.g. a note someone dropped here)
            if t.status == "queued":
                out.append(t)
        return out

    def claim(self, task, runner_id):
        lock = self.locks_dir / f"{task.id}.lock"
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            return False
        with os.fdopen(fd, "w") as f:
            f.write(f"{runner_id} {now_iso()}\n")
        fresh = self._load(task.ref)  # re-read: did it change since we listed it?
        if fresh.status != "queued":
            lock.unlink(missing_ok=True)
            return False
        task.meta, task.body = fresh.meta, fresh.body
        self.set_status(task, "claimed", claimed_by=runner_id, claimed_at=now_iso())
        return True

    def set_status(self, task, status, **kv):
        task.meta["status"] = status
        task.meta.update(kv)
        task.meta["updated"] = now_iso()
        self._save(task)

    def write_result(self, task, status, worker, output, note=""):
        task.body = task.body.rstrip() + "\n" + taskfile.result_section(status, worker, output, note)
        self.set_status(task, status, worker=worker)

    def release(self, task):
        (self.locks_dir / f"{task.id}.lock").unlink(missing_ok=True)


class GitHubQueue:
    """GitHub issues as the queue, via the `gh` CLI (already logged in with `gh auth login`).
    A task is an issue whose body is the task file and which carries the label
    'switchboard:queued'. Status moves by swapping 'switchboard:<status>' labels.
    The result is posted as an issue comment. The runner never merges or closes PRs.
    """

    name = "github"
    PREFIX = "switchboard:"

    def __init__(self, repo, gh="gh"):
        self.repo, self.gh = repo, gh

    def _gh(self, *args, input_text=None):
        r = subprocess.run([self.gh, *args, "--repo", self.repo], input=input_text,
                           capture_output=True, text=True, check=True)
        return r.stdout

    def list_queued(self):
        raw = self._gh("issue", "list", "--label", self.PREFIX + "queued", "--state", "open",
                       "--json", "number,body,title", "--limit", "50")
        out = []
        for issue in json.loads(raw or "[]"):
            try:
                t = taskfile.parse(issue["body"].replace("\r\n", "\n"), ref=issue["number"])
            except ValueError:
                continue
            t.meta["status"] = "queued"  # labels are the source of truth on GitHub
            out.append(t)
        return out

    def claim(self, task, runner_id):
        # Labels are not truly atomic. Good enough for one runner; for several, give
        # each runner its own label filter or use the folder queue's lock files.
        raw = self._gh("issue", "view", str(task.ref), "--json", "labels")
        labels = {l["name"] for l in json.loads(raw)["labels"]}
        if self.PREFIX + "queued" not in labels:
            return False
        self.set_status(task, "claimed", claimed_by=runner_id)
        return True

    def set_status(self, task, status, **kv):
        old = task.meta.get("status", "queued")
        task.meta["status"] = status
        self._gh("issue", "edit", str(task.ref), "--remove-label", self.PREFIX + old,
                 "--add-label", self.PREFIX + status)
        if kv:
            self._gh("issue", "comment", str(task.ref), "--body",
                     f"switchboard: **{status}** " + ", ".join(f"{k}={v}" for k, v in kv.items()))

    def write_result(self, task, status, worker, output, note=""):
        self._gh("issue", "comment", str(task.ref), "--body-file", "-",
                 input_text=taskfile.result_section(status, worker, output, note))
        self.set_status(task, status)

    def release(self, task):
        pass


def make_queue(kind, **opts):
    if kind == "folder":
        return FolderQueue(opts["path"])
    if kind == "github":
        return GitHubQueue(opts["repo"])
    raise ValueError(f"unknown queue '{kind}' (try 'folder' or 'github')")
