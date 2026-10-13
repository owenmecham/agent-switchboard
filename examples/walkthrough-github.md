# Walkthrough: one code task through GitHub

Setup: a private repo `you/my-app`, the `gh` CLI logged in, labels
`switchboard:queued|claimed|running|done|failed|needs-human`, and a runner (launchd on your Mac
so Claude Code can use your local checkout, or the Actions workflow for API-only workers).

Create the labels once:
```bash
for s in queued claimed running done failed needs-human; do
  gh label create "switchboard:$s" --repo you/my-app; done
```

## 1. You ask Grok
> "The settings button is too small on phones. Have Claude Code fix it."

## 2. Grok opens an issue
Title `Make the settings button bigger`, label `switchboard:queued`, body:
```markdown
---
id: 2026-01-15-004
title: Make the settings button bigger
type: bugfix
priority: low
requested_by: grok
created: 2026-01-15T09:15:00+00:00
tags: [ui]
route:
  worker: claude-code
repo_path: ~/code/my-app
status: queued
---

## Task
Make the settings button at least 44px tall on phones. Work on a new branch, push it,
and open a PR. Do not merge. Print the PR URL at the end.
```
(Typing this by hand? `gh issue create --repo you/my-app --label switchboard:queued --title "..." --body-file task.md`)

## 3. The runner
```bash
cd runner && python3 -m switchboard --queue github --repo you/my-app --rules ../routing/rules.yml
```
- swaps the label to `switchboard:claimed`, then `switchboard:running`, and comments who took it
- the route hint says `claude-code` (tags `[ui]` would otherwise pick antigravity on a Mac)
- runs `runner/workers/claude.sh`, which `cd`s into `repo_path` and runs `claude -p ...`

## 4. Result comment on the issue
```markdown
## Result
- status: done
- worker: claude-code
- finished: 2026-01-15T09:31:40+00:00

```text
Increased .settings-btn min-height to 44px ... PR: https://github.com/you/my-app/pull/12
```
```
Label is now `switchboard:done`.

## 5. Grok reports back, and you merge
Grok (reading via its GitHub connector): *"#4 is done. Claude Code opened PR #12. Want a
DeepSeek review first?"* If you say yes, Grok queues a `type: review` task. **You** click merge.
