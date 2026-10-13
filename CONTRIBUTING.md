# Contributing

Thanks! This repo is meant to stay small and easy to read, so:

- **Keep the runner standard-library Python.** No new dependencies without a strong reason.
- **New worker?** Add a short script in `runner/workers/`, mark it `EXAMPLE - edit me`, and read
  keys from env/Keychain via `_common.sh`. Never commit a key.
- **New queue (Notion, Cloud Brain, ...)?** Follow `spec/queue-adapter-contract.md` and add a test.
- Run `make test && make demo` before opening a PR.
- Plain, friendly wording in docs. Assume the reader isn't a programmer.
