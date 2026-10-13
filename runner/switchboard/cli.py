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

from . import mini_yaml, routing
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


def process_once(queue, rules, dry_run=False, runner_id=None, env=None):
    settings = rules.get("settings") or {}
    max_tasks = settings.get("max_tasks_per_run", 5)
    timeout = settings.get("default_timeout_seconds", 1800)
    runner_id = runner_id or f"{socket.gethostname()}-{os.getpid()}"
    used = {}  # worker -> count this run (simple cost/concurrency cap)
    summary = []

    tasks = queue.list_queued()
    log.info("found %d queued task(s)", len(tasks))
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
            log.info("[%s] %s via %s", task.id, status, worker)
            summary.append((task.id, status, worker))
        finally:
            queue.release(task)
    return summary


def _now():
    from .taskfile import now_iso
    return now_iso()


def main(argv=None):
    p = argparse.ArgumentParser(prog="switchboard", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--queue", choices=["folder", "github"], default="folder")
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
    queue = make_queue(a.queue, path=a.path, repo=a.repo)
    while True:
        for row in process_once(queue, rules, dry_run=a.dry_run):
            print("\t".join(str(x) for x in row))
        if not a.loop:
            return 0
        time.sleep(a.loop)


if __name__ == "__main__":
    sys.exit(main())
