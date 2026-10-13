"""The runner loop: poll -> route -> claim -> run worker -> write result.

    python3 -m switchboard --queue folder --path ~/Vault/agent-switchboard --rules routing/rules.yml
    python3 -m switchboard --queue github --repo you/your-repo --rules routing/rules.yml --dry-run
"""
import argparse
import logging
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

from . import digest, mini_yaml, routing
from .queues import make_queue

log = logging.getLogger("switchboard")
REPO_ROOT = Path(__file__).resolve().parents[2]


def run_worker(name, task, rules, timeout):
    """Run a worker's command. The task file is passed by path (TASK_FILE) and on stdin.
    Whatever the worker prints on stdout becomes the result. Exit code 0 = success."""
    w = rules["workers"][name]
    cmd = w["command"]
    tmp = Path(os.environ.get("TMPDIR", "/tmp")) / f"switchboard-{task.id}.md"
    from .taskfile import render
    text = render(task)
    tmp.write_text(text, encoding="utf-8")
    env = dict(os.environ, TASK_FILE=str(tmp), TASK_ID=task.id, TASK_TYPE=task.type,
               SWITCHBOARD_ROOT=str(REPO_ROOT))
    try:
        r = subprocess.run(cmd, shell=True, input=text, capture_output=True, text=True,
                           env=env, cwd=REPO_ROOT, timeout=w.get("timeout_seconds", timeout))
        out = r.stdout if r.returncode == 0 else (r.stdout + "\n--- stderr ---\n" + r.stderr)
        return r.returncode == 0, out
    except subprocess.TimeoutExpired:
        return False, f"timed out after {w.get('timeout_seconds', timeout)}s"
    finally:
        tmp.unlink(missing_ok=True)


def process_once(queue, rules, dry_run=False, runner_id=None, env=None, state=None):
    settings = rules.get("settings") or {}
    max_tasks = settings.get("max_tasks_per_run", 5)
    timeout = settings.get("default_timeout_seconds", 1800)
    runner_id = runner_id or f"{socket.gethostname()}-{os.getpid()}"
    used = {}  # worker -> count this run (simple cost/concurrency cap)
    summary = []

    qname = getattr(queue, "name", "queue")
    tasks = queue.list_queued()
    log.info("[%s] found %d queued task(s)", qname, len(tasks))
    if state is not None and not dry_run:
        for t in tasks:
            digest.record(state, qname, t, "queued")
    for task in tasks[:max_tasks]:
        decision = routing.route(task, rules, env)
        # honour per-worker caps
        if decision["action"] == "run":
            capped = [c for c in decision["candidates"]
                      if used.get(c, 0) < (rules["workers"][c].get("max_per_run") or 10**6)]
            if not capped:
                log.info("[%s] all candidates hit their per-run cap; leaving queued", task.id)
                summary.append((task.id, "skipped", "cap"))
                continue
            decision["candidates"] = capped

        if dry_run:
            log.info("[dry-run] [%s] type=%s -> %s", task.id, task.type,
                     decision.get("candidates") or ("needs-human: " + decision["reason"]))
            summary.append((task.id, "dry-run", decision.get("candidates", decision.get("reason"))))
            continue

        if not queue.claim(task, runner_id):
            log.info("[%s] already claimed elsewhere; skipping", task.id)
            continue
        try:
            if decision["action"] == "needs-human":
                queue.write_result(task, "needs-human", "none", "", note=decision["reason"])
                if state is not None:
                    digest.record(state, qname, task, "needs-human", note=decision["reason"])
                log.info("[%s] needs-human: %s", task.id, decision["reason"])
                summary.append((task.id, "needs-human", decision["reason"]))
                continue
            final = None
            for worker in decision["candidates"]:
                queue.set_status(task, "running", worker=worker, started=_now())
                used[worker] = used.get(worker, 0) + 1
                log.info("[%s] running on %s (rule: %s)", task.id, worker, decision["rule"])
                ok, out = run_worker(worker, task, rules, timeout)
                if ok:
                    final = ("done", worker, out, "")
                    break
                log.warning("[%s] %s failed (exit non-zero or timeout)", task.id, worker)
                final = ("failed", worker, out, "all candidates failed")
            status, worker, out, note = final
            if status == "failed" and settings.get("escalate_failures_to_human", True):
                status = "needs-human"
            queue.write_result(task, status, worker, out, note)
            if state is not None:
                digest.record(state, qname, task, status, worker, note)
            log.info("[%s] %s via %s", task.id, status, worker)
            summary.append((task.id, status, worker))
        finally:
            queue.release(task)
    return summary


def run_all(queues, rules, dry_run=False, state_path=None, env=None):
    """Poll every queue in order (primary first). An unreachable queue is logged and skipped,
    so if Notion/GitHub is down the folder fallback still gets processed. The digest is then
    written to every queue that answered."""
    state = digest.load(state_path) if state_path else {"tasks": {}}
    summary, reachable = [], []
    for q in queues:
        try:
            summary += process_once(q, rules, dry_run=dry_run, env=env, state=state)
            reachable.append(q)
        except Exception as e:  # network down, auth expired, gh not logged in...
            log.error("[%s] unreachable, skipping this poll: %s", getattr(q, "name", q), e)
    if not dry_run:
        text = digest.render(state)
        for q in reachable:
            if hasattr(q, "write_digest"):
                try:
                    q.write_digest(text)
                except Exception as e:
                    log.warning("[%s] could not write digest: %s", q.name, e)
        if state_path:
            digest.save(state, state_path)
    return summary


def load_queues(path):
    cfg = mini_yaml.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    out = []
    for q in cfg.get("queues") or []:
        if q.get("enabled", True) is False:
            continue
        opts = {k: v for k, v in q.items() if k not in ("kind", "enabled", "name")}
        out.append(make_queue(q["kind"], **opts))
    return out


def _now():
    from .taskfile import now_iso
    return now_iso()


def main(argv=None):
    p = argparse.ArgumentParser(prog="switchboard", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--queue", choices=["folder", "github"], default="folder",
                   help="single queue (simple). For notion/mcp-notes/failover use --queues")
    p.add_argument("--queues", help="queue config file with a failover order (runner/queues.example.yml)")
    p.add_argument("--state", default="~/.agent-switchboard/state.json",
                   help="local state used to build the status digest")
    p.add_argument("--path", help="folder queue root (e.g. a folder inside your Obsidian vault)")
    p.add_argument("--repo", help="owner/name for the github queue")
    p.add_argument("--rules", default=str(REPO_ROOT / "routing" / "rules.yml"))
    p.add_argument("--dry-run", action="store_true", help="show routing decisions; change nothing")
    p.add_argument("--loop", type=int, default=0, metavar="SECONDS",
                   help="keep polling every N seconds (default: run once and exit)")
    p.add_argument("--log-file", help="also append logs here")
    a = p.parse_args(argv)

    handlers = [logging.StreamHandler(sys.stderr)]
    if a.log_file:
        Path(a.log_file).expanduser().parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(Path(a.log_file).expanduser()))
    logging.basicConfig(level=logging.INFO, handlers=handlers,
                        format="%(asctime)s %(levelname)s %(message)s")

    rules = mini_yaml.loads(Path(a.rules).read_text(encoding="utf-8"))
    queues = load_queues(a.queues) if a.queues else [make_queue(a.queue, path=a.path, repo=a.repo)]
    while True:
        for row in run_all(queues, rules, dry_run=a.dry_run, state_path=a.state):
            print("\t".join(str(x) for x in row))
        if not a.loop:
            return 0
        time.sleep(a.loop)


if __name__ == "__main__":
    sys.exit(main())
