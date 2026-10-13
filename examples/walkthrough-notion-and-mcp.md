# Walkthrough: Notion as the main queue, folder as the fallback

## Notion setup (once)
1. Create a database with the properties `Name` (title), `Task ID` (text), `Status` (select:
   queued, claimed, running, done, failed, needs-human), `Type` (select), `Priority` (select),
   `Tags` (multi-select), `Worker` (text). Optionally create a page called "Switchboard status".
2. Create an internal integration at notion.so/my-integrations and share the database (and the
   status page) with it.
3. Store the token: `security add-generic-password -a "$USER" -s NOTION_TOKEN -w` (Mac), or set
   `NOTION_TOKEN` in the environment.
4. Copy `runner/queues.example.yml` to `runner/queues.yml`. Set `database_id` and
   `status_page_id`, set `enabled: true`, and keep the folder queue last.
5. Run `cd runner && python3 -m switchboard --queues queues.yml --rules ../routing/rules.yml --dry-run`.

## A round trip
- Grok adds a row: Name "Compare standing desks", Type `research`, Status `queued`, with the
  instructions in the page body. It also creates a check-in routine every 20 min.
- The runner polls Notion → claimed → running → done. It appends a **Result** heading,
  bullets, and the output as code blocks to the page, and fills in `Worker`.
- The runner rewrites the "Switchboard status" page (the digest).
- Grok's next check-in reads that page, sees the task under Finished, opens the row, reports to
  you, and deletes the routine.

## When Notion is down
The runner logs `[notion] unreachable, skipping this poll` and still processes the folder queue.
Grok, following its prompt, writes the task as a Markdown file into the folder instead and says so.

## MCP notes server (e.g. Cloud Brain)
Same flow. Tasks are notes in a folder (e.g. `agent-switchboard/tasks`) whose content starts
with the normal task frontmatter. Grok writes them with its notes connector. The runner reaches
the same server over MCP HTTP, using the tool mapping in `queues.yml`:

| runner needs | maps to (example) |
|---|---|
| list | `list_directory {path: "{folder}"}` |
| read | `read_note {file_path: "{path}"}` |
| claim / status | `edit_note {operation: find_replace}` (must fail if the text is gone) |
| result | `edit_note {operation: append}` |
| digest | `write_note {title, folder, content}` |

Check your server's tool schemas and adjust. If your server can't be reached from the
runner's machine (or needs OAuth that a script can't do), use the **sync alternative**: export
or sync those notes to a local folder and use the `folder` queue.
