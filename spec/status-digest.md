# Status digest convention

Grok check-ins should be cheap. Instead of opening every task, Grok reads **one** thing:
the status digest. The runner rewrites it after every poll.

| queue | where the digest lives |
|---|---|
| folder | `<queue root>/status.md` |
| github | the open issue labeled `switchboard:status` (created on first run) |
| notion | the page set as `status_page_id` |
| mcp-notes | a note titled `switchboard status` (via the `write` tool mapping) |

Format (Markdown with a small header Grok can check first):

```markdown
---
type: switchboard-status
updated: 2026-01-15T09:05:00+00:00
open: 1           # queued + claimed + running
needs_human: 1    # in the last 48h
---

# Switchboard status

## Open
| id | title | status | queue | updated |
|---|---|---|---|---|
| 2026-01-15-005 | Fix login | running via claude-code | github | ... |

## Finished (last 48h)
| id | title | status | queue | updated |
|---|---|---|---|---|
| 2026-01-15-001 | Compare desks | done via grok | folder | ... |
| 2026-01-15-003 | Email landlord | needs-human (type 'send' always needs a human) | folder | ... |
```

How a check-in uses it:
1. Read the digest. If `updated` is old (more than about 3 poll intervals), say the runner looks stopped.
2. For each task Grok is watching: if it's in **Finished**, open that one task to read the Result,
   then report. If it's still in **Open**, stay quiet (or give a one-line "still running").
3. When nothing Grok is watching is still open, stop the check-in.

The runner builds the digest from a small local state file (`--state`, default
`~/.agent-switchboard/state.json`), so the digest covers every queue in the failover list,
and each reachable queue gets a copy.
