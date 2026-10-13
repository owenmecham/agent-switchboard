#!/usr/bin/env bash
# Fake worker for demos and tests. Echoes the task title back. Safe to run anywhere.
set -euo pipefail
title="$(grep -m1 '^title:' "$TASK_FILE" | sed 's/^title: *//; s/^"//; s/"$//')"
echo "echo-worker handled task $TASK_ID ($TASK_TYPE): $title"
echo "If this were a real worker, the answer would be here."
