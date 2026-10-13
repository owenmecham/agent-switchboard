# Walkthrough: one task through a notes folder (Obsidian)

Setup: your vault has a folder `agent-switchboard/tasks`. A Mac runs the runner every 5 minutes
via launchd. Grok can write to the vault (through a notes connector, or you paste the file in).

## 1. You ask Grok
> "Can you get someone to compare three standing desks under $500?"

## 2. Grok writes the task
Grok saves `agent-switchboard/tasks/2026-01-15-001-research-standing-desks.md`:

```markdown
---
id: 2026-01-15-001
title: Compare three standing desks under $500
type: research
priority: normal
requested_by: grok
created: 2026-01-15T09:00:00+00:00
tags: [home-office]
status: queued
---

## Task
Find three well-reviewed standing desks under $500 ...
```
Grok replies: *"Queued as 2026-01-15-001. Your rules send research to grok (fallback deepseek)."*

## 3. The runner picks it up
On its next tick the runner logs:
```
INFO found 1 queued task(s)
INFO [2026-01-15-001] running on grok (rule: research goes to grok)
INFO [2026-01-15-001] done via grok
```
While it works, the note's status changes `queued → claimed → running`. You can watch it happen
in Obsidian's Properties panel.

## 4. The result lands in the same note
```markdown
status: done
worker: grok
...
## Result

- status: done
- worker: grok
- finished: 2026-01-15T09:03:12+00:00

```text
| Desk | Price | Height | Pro | Con | ...
```
```

## 5. Grok reports back
> You: "Anything back?"
> Grok: "Yes. 2026-01-15-001 is done. Top pick: ... Full table is in the note."

## Try it without any accounts
`make demo` does exactly this with the fake `echo` worker. Output is shown in the repo's
top-level README section "Try it in 30 seconds".
