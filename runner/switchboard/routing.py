"""Pick a worker for a task. Plain first-match rules; see routing/decision-logic.md."""
import os
import platform
import shutil


def environment():
    return {"os": "macos" if platform.system() == "Darwin" else platform.system().lower(),
            "env": dict(os.environ)}


def worker_available(name, rules, env):
    """A worker is usable if it is defined, enabled, its OS needs are met,
    its required env vars are set, and its binary (if listed) is on PATH."""
    w = (rules.get("workers") or {}).get(name)
    if not w or w.get("enabled", True) is False:
        return False, "not defined or disabled"
    for req in w.get("requires") or []:
        if req in ("macos", "linux", "windows") and env["os"] != req:
            return False, f"needs {req}"
    for var in w.get("env") or []:
        if not env["env"].get(var):
            return False, f"missing env {var}"
    binary = w.get("binary")
    if binary and not shutil.which(binary):
        return False, f"'{binary}' not on PATH"
    return True, "ok"


def rule_matches(match, task):
    match = match or {}
    if "type" in match:
        types = match["type"] if isinstance(match["type"], list) else [match["type"]]
        if task.type not in types:
            return False
    if "tags_any" in match and not set(match["tags_any"]) & set(task.tags):
        return False
    if "tags_all" in match and not set(match["tags_all"]) <= set(task.tags):
        return False
    if "priority" in match:
        prios = match["priority"] if isinstance(match["priority"], list) else [match["priority"]]
        if task.meta.get("priority") not in prios:
            return False
    return True


def route(task, rules, env=None):
    """Return a decision dict:
      {"action": "run", "candidates": [...], "rule": name, "skipped": {...}}
      {"action": "needs-human", "reason": "...", "rule": name}
    """
    env = env or environment()
    settings = rules.get("settings") or {}

    # 1. Things a human must approve are never auto-run.
    if task.type in (settings.get("always_needs_human") or []):
        return {"action": "needs-human", "rule": "settings.always_needs_human",
                "reason": f"type '{task.type}' always needs a human"}

    # 2. Find the first rule that matches.
    chosen = None
    for rule in rules.get("rules") or []:
        if rule_matches(rule.get("match"), task):
            chosen = rule
            break
    if chosen is None:
        return {"action": "needs-human", "rule": None, "reason": "no rule matched"}
    if chosen.get("needs_human"):
        return {"action": "needs-human", "rule": chosen.get("name"),
                "reason": chosen.get("reason", "rule says a human decides")}

    # 3. Build the candidate list: optional task hint, then worker, then fallbacks.
    candidates = []
    hint = (task.meta.get("route") or {}).get("worker") if isinstance(task.meta.get("route"), dict) else None
    if hint and settings.get("allow_route_hints", True):
        candidates.append(hint)
    candidates.append(chosen["worker"])
    candidates += chosen.get("fallbacks") or []
    candidates = list(dict.fromkeys(c for c in candidates if c))  # dedupe, keep order

    # 4. Drop workers that can't run here.
    usable, skipped = [], {}
    for c in candidates:
        ok, why = worker_available(c, rules, env)
        (usable.append(c) if ok else skipped.__setitem__(c, why))
    if not usable:
        return {"action": "needs-human", "rule": chosen.get("name"),
                "reason": "no available worker: " + "; ".join(f"{k} ({v})" for k, v in skipped.items())}
    return {"action": "run", "candidates": usable, "rule": chosen.get("name"), "skipped": skipped}
