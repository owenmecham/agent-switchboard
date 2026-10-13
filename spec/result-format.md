# Result format

When a worker finishes, the runner appends a `## Result` section to the task and updates the
frontmatter `status` and `worker`. On GitHub, the same section is posted as an issue comment
and the `switchboard:<status>` label is swapped.

```markdown
## Result

- status: done                 # done | failed | needs-human
- worker: claude-code          # who produced it ("none" if no worker ran)
- finished: 2026-01-15T09:03:12+00:00
- note: all candidates failed  # optional, why it ended this way

```text
...whatever the worker printed...
```
```

Rules:
- The frontmatter `status` is the truth. The Result section is for humans and for Grok to read.
- A retried task gets a *second* Result section. Read the last one.
- A worker's stdout is the result. Failed workers also include stderr after `--- stderr ---`.
- Code workers should put links (branch, PR URL) in their output so Grok can pass them on.
