---
description: "scopeGuard implement gate: verify every task that carries an in-scope user story or requirement is checked off"
scripts:
  sh: bash scripts/bash/scopeguard.sh implement
  ps: scripts/powershell/scopeguard.ps1 implement
  py: scripts/python/scopeguard.py implement
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Goal

Deterministically report which in-scope user stories and requirements still have open tasks after implementation, so a feature is not declared done with scope silently missing. This command is offered as an optional `after_implement` hook and can be run any time.

The gate only reads the checkboxes in `tasks.md`; it does not judge code. Never tick a checkbox to make the gate pass — a task is checked only when its work is actually done.

## Steps

1. Run `{SCRIPT}` from the repository root. If the user input above names a feature directory, append `--feature-dir <that directory>`. Keep the exit code and the full output.

2. **Exit code 0 — PASS.** Report one line, for example `scopeGuard implement gate: PASS (all 10 in-scope items done, 1 waived)`. Done.

3. **Exit code 1 — FAIL.** Show the `[FAIL]` lines exactly as printed: each in-scope item with its open tasks. Tell the user the feature is not complete for those items and offer to continue implementing the open tasks. Do not change `tasks.md` checkboxes without doing the work.

4. **Exit code 2 — ERROR.** Show the message and the fix (for example no `tasks.md` yet).
