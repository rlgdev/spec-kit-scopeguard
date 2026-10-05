---
description: "scopeGuard report: coverage matrix of every user story and requirement across plan, tasks and implement"
scripts:
  sh: bash scripts/bash/scopeguard.sh report --save
  ps: scripts/powershell/scopeguard.ps1 report --save
  py: scripts/python/scopeguard.py report --save
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Goal

Show, for one feature, where every scope item stands in each phase (plan, tasks, implement) with coverage percentages, and save the same Markdown report as `scopeguard-report.md` in the feature directory. Informational only: this command always exits 0 and modifies nothing except that report file.

## Steps

1. Run `{SCRIPT}` from the repository root. If the user input above names a feature directory, append `--feature-dir <that directory>`; if it asks for every feature, append `--all`.
2. Show the printed Markdown report as is.
3. Summarize in at most three lines: per-phase coverage and the IDs marked `MISSING`, `INVALID` or `OPEN`. Point to the saved `scopeguard-report.md`.
4. If the script exits with code 2, show the error and the fix.
