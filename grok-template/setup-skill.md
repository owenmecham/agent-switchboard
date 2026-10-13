# Switchboard setup interview (paste this into a new Grok chat)

---

You are helping me set up **agent-switchboard** (a pattern for using you, Grok, as a coordinator
that hands jobs to other AI tools). The reference repo is
https://github.com/owenmecham/agent-switchboard. Read its README, `routing/rules.example.yml`,
and `grok-template/system-prompt.md` if you can browse. Otherwise I'll paste them.

Work in **stages**. Ask **one small group of questions at a time**, in plain language, and wait
for my answers. Assume I'm not a programmer unless I say I am. Prefer what *I* have over the
defaults. Explain any jargon the first time you use it.

## Stage 1: Interview
Ask about:
1. **Tools I have**: which AI subscriptions, apps, or API keys (Claude / Claude Code, ChatGPT /
   Codex, Google Antigravity or Gemini, Cursor, DeepSeek, Grok API, others). Which do I
   actually like for what?
2. **Computer**: Mac, Windows, Linux? Is it on most of the day? Am I OK running something on a
   schedule there, or should everything run in the cloud (GitHub Actions)?
3. **Notes**: where do my notes live (Obsidian, Notion, Apple Notes, Google Drive, Cloud Brain,
   none)? Is the folder synced? Can you, Grok, read/write it through a connector?
4. **GitHub**: do I have an account? Do I write code? Is `gh` installed?
5. **Kinds of jobs** I'd hand off. Get 3 to 6 real examples from me and name a `type` for each.
6. **Limits**: what must *never* happen automatically? Monthly spend I'm comfortable with?

Then summarize back what you heard as a short table and ask me to confirm.

## Stage 2: Design my routing
- Propose a queue choice (folder, GitHub, or both) with one sentence on why.
- Propose my `routing/rules.yml`: for each job type, a worker plus 1 or 2 fallbacks, with
  `always_needs_human` covering anything from my "never automatic" list. Only include workers I
  have. Disable or remove the rest.
- Show it as a plain table first. After I say OK, give me the full YAML file. Keep to the
  simple format in rules.example.yml (key: value, [a, b] lists).

## Stage 3: Install the runner, step by step
Give one step at a time and wait for "done" or an error before moving on. Cover:
1. Getting the repo (`git clone` or "Download ZIP").
2. Saving my rules as `routing/rules.yml`.
3. Running `make demo` (or `./scripts/demo.sh`) to prove it works with the fake worker.
4. Making my queue folder (e.g. `<vault>/agent-switchboard/tasks`) or GitHub repo + labels
   (`switchboard:queued`, `claimed`, `running`, `done`, `failed`, `needs-human`).
5. Editing each worker script I'll use in `runner/workers/` and storing keys **in the Keychain
   or environment, never in files**. Show me the exact `security add-generic-password` command.
6. A dry run against my real queue:
   `cd runner && python3 -m switchboard --queue folder --path <my folder> --rules ../routing/rules.yml --dry-run`
7. Scheduling it: on a Mac, fill in `runner/launchd/com.example.agent-switchboard.plist` with
   my paths and load it. Otherwise, set up `runner/github-actions/switchboard.yml` and the repo
   secrets.
If I hit an error, ask me to paste it and fix one thing at a time.

## Stage 4: Fill in my coordinator prompt
Fill every `{{PLACEHOLDER}}` in `grok-template/system-prompt.md` with my answers and give me the
finished text to paste into my Grok custom instructions. Then run a first real task together:
you write it, I let the runner pick it up, and you read the result back.

## Rules for you during setup
- Never ask me to paste API keys or passwords into this chat.
- If something I want is risky (auto-sending email, auto-merging code), say so and suggest
  `needs-human` instead.
- Keep each message short.
