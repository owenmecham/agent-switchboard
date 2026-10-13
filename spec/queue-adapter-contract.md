# Queue adapter contract

A queue adapter is any small class with these five methods. The runner only talks to the queue
through them, so adding Notion, Cloud Brain, a database, or email is just a new class in
`runner/switchboard/queues.py`.

| method | must do |
|---|---|
| `list_queued() -> [Task]` | Return tasks whose status is `queued`. Skip things that aren't valid tasks. |
| `claim(task, runner_id) -> bool` | Take the task **at most once** across all runners. Return False if someone else got it. Then set status `claimed`. |
| `set_status(task, status, **fields)` | Save the new status (and any extra fields) where Grok can see it. |
| `write_result(task, status, worker, output, note="")` | Store the result ([format](result-format.md)) and set the final status. |
| `release(task)` | Clean up any lock. Always called, even after errors. |
| `write_digest(markdown)` *(optional)* | Overwrite the one status note/issue/page ([status-digest.md](status-digest.md)). |

If `list_queued()` raises (network down, auth expired), the runner logs the queue as
unreachable and moves on to the next queue in the failover list.

A `Task` has `meta` (the frontmatter dict), `body` (Markdown), and `ref` (where it lives:
file path, issue number, page id...).

## Built-in adapters

| kind | where tasks live | claim | result goes | digest |
|---|---|---|---|---|
| `folder` | `<root>/tasks/*.md` | lock file (exclusive create) | appended `## Result` | `<root>/status.md` |
| `github` | issues labeled `switchboard:queued` | label swap | issue comment | issue labeled `switchboard:status` |
| `notion` | database rows (`Status` select) | re-check then set (not atomic) | blocks appended to the page + `Worker` property | a page you pick (`status_page_id`) |
| `mcp-notes` | notes in a folder on an MCP notes server | find/replace `status: queued` → `status: claimed` (fails if already changed) | appended `## Result` | a note (`write` tool) |

Config for all four: `runner/queues.example.yml`.

## How the folder and GitHub adapters claim

- **folder**: creates `.locks/<id>.lock` with an exclusive create (it fails if the file exists),
  then re-reads the task to be sure it's still `queued`. Writes go to a temp file followed by an
  atomic rename, so Obsidian/iCloud/Dropbox never sync half a file. Caveat: two *different
  computers* sharing one synced folder can still race, because sync is slow. Run one runner per folder.
- **github**: checks for the `switchboard:queued` label, then swaps it for `switchboard:claimed`.
  This isn't atomic. The example Actions workflow uses `concurrency:` so only one runner runs.

## Checklist for a new adapter

- [ ] Two runners can't both process one task (or document why it's fine)
- [ ] Grok can read the status and result through some connector it has
- [ ] A test like `tests/test_switchboard.py::FolderRoundTrip`
