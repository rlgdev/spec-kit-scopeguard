---
description: "scopeGuard compare: compare scope coverage of two feature directories, e.g. two runs of the same spec in a lab"
scripts:
  sh: bash scripts/bash/scopeguard.sh compare
  ps: scripts/powershell/scopeguard.ps1 compare
  py: scripts/python/scopeguard.py compare
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Goal

Compare two feature directories built from the same specification (for example two lab runs, two agents, or two models) item by item: which user stories and requirements each run planned, broke into tasks and implemented. Informational only; nothing is modified.

## Steps

1. Take the two feature directories from the user input (for example `../run-a/specs/001-board specs/001-board`). If they are missing, ask the user for both paths and stop until you have them. Optional labels can be given as `--labels name-a,name-b`.
2. Run `{SCRIPT} <dir A> <dir B> [--labels a,b]` from the repository root. Add `--out <file>` if the user wants the comparison saved.
3. Show the printed Markdown comparison as is.
4. Summarize in at most three lines: coverage per phase for each run and the IDs marked as differing.
5. If the script exits with code 2, show the error (for example a directory without `spec.md`).
