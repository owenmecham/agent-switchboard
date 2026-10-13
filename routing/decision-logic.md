# How the runner picks a worker

Plain rules, read top to bottom. No magic.

1. **Hard stops first.** If the task's `type` is in `settings.always_needs_human`
   (for example `send`, `merge`, `purchase`), the task is set to `needs-human`. Nothing runs.
2. **First match wins.** Rules are checked in order. A rule's `match` can use:
   - `type`: one type or a list (`[code, bugfix]`)
   - `tags_any`: at least one of these tags is on the task
   - `tags_all`: all of these tags are on the task
   - `priority`: one or a list
   - `{}`: matches everything. Put it last as a catch-all.
3. **A rule can say "a human decides".** `needs_human: true` plus a `reason`.
4. **Build the candidate list.** Order: the task's own hint (`route: worker: codex`, if
   `allow_route_hints` is on), then the rule's `worker`, then its `fallbacks`.
5. **Drop what can't run here.** A worker is skipped if it's `enabled: false`, needs a
   different OS (`requires: [macos]` on a Linux/GitHub Actions runner), is missing an env
   var listed in `env`, or its `binary` isn't installed. If nothing is left, the task goes
   to `needs-human` with the reasons listed.
6. **Caps.** `max_tasks_per_run` limits tasks per poll. A worker's `max_per_run` limits
   how often one worker runs per poll. That's a simple guard for cost and concurrency. If every
   candidate is capped, the task stays `queued` for the next poll.
7. **Try in order.** Run the first candidate. On a non-zero exit or timeout, try the next one.
   If all fail, the task becomes `failed`, or `needs-human` if `escalate_failures_to_human`.

Failover for the *queue itself* (GitHub down, so use the notes folder) is a different thing.
See the README's "Failover" section.
