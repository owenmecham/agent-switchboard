#!/usr/bin/env bash
# End-to-end demo: copies the sample vault to a temp dir, shows a dry run,
# runs for real with the fake echo worker, then prints what came back.
set -euo pipefail
cd "$(dirname "$0")/.."
work="$(mktemp -d)"
cp -R examples/demo-vault/agent-switchboard "$work/"
Q="$work/agent-switchboard"
run() { (cd runner && python3 -m switchboard --queue folder --path "$Q" --rules ../routing/rules.demo.yml --state "$work/state.json" "$@"); }

echo "== 1. Grok has written 4 tasks into $Q/tasks"
ls "$Q/tasks"
echo; echo "== 2. Dry run (nothing changes)"
run --dry-run
echo; echo "== 3. Real run (fake echo worker)"
run
echo; echo "== 4. Statuses now (this is what Grok reads back)"
grep -H '^status:' "$Q"/tasks/*.md | sed "s|$Q/tasks/||"
echo; echo "== 5. One full result file"
cat "$Q/tasks/2026-01-15-002-review-pr.md"
echo; echo "== 6. The status digest a Grok check-in reads ($Q/status.md)"
cat "$Q/status.md"
echo; echo "== 7. Second run finds nothing left to do"
run
fails=0
grep -q '^status: done' "$Q/tasks/2026-01-15-001-research-standing-desks.md" || fails=1
grep -q '^status: done' "$Q/tasks/2026-01-15-002-review-pr.md" || fails=1
grep -q '^status: needs-human' "$Q/tasks/2026-01-15-003-email-landlord.md" || fails=1
grep -q '^status: done' "$Q/tasks/2026-01-15-004-ui-tweak.md" || fails=1
grep -q "needs_human: 1" "$Q/status.md" || fails=1
[ $fails = 0 ] && echo "DEMO PASSED" || { echo "DEMO FAILED"; exit 1; }
