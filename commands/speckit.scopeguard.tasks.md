---
description: "scopeGuard tasks gate: verify every in-scope user story and requirement from spec.md is carried by at least one task in tasks.md"
scripts:
  sh: bash scripts/bash/scopeguard.sh tasks
  ps: scripts/powershell/scopeguard.ps1 tasks
  py: scripts/python/scopeguard.py tasks
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Goal

Deterministically verify that task generation did not silently drop scope. Every user story and traced requirement ID in `spec.md` that `plan.md` does not mark `deferred` must be carried by at least one task in `tasks.md`:

- a user story by tasks labelled `[USn]` (or listed under a `User Story n` phase heading);
- a requirement by naming its ID in a task description (for example `(FR-003)`) or by a row in the `## Scope Coverage` table of `tasks.md` that maps it to existing task IDs.

This command runs automatically as the mandatory `after_tasks` hook. The verdict comes from the script; never report the task list as complete while it exits non-zero.

## Steps

1. Run `{SCRIPT}` from the repository root. If the user input above names a feature directory, append `--feature-dir <that directory>`. Keep the exit code and the full output.

2. **Exit code 0 — PASS.** Report one line, for example `scopeGuard tasks gate: PASS (10 carried, 1 waived)`, then list waived items and warnings exactly as printed. Done.

3. **Exit code 1 — FAIL.** Show the user the `[FAIL]` lines exactly as printed. Then fix `tasks.md` (never `spec.md`):
   - **Story without tasks**: add a phase for that story in priority order, with concrete tasks labelled `[USn]`, following the existing format (`- [ ] T### [P?] [USn] Description with file path`). Continue the task numbering; do not renumber existing tasks.
   - **Requirement without tasks**: name the requirement ID in the description of the task(s) that implement it, or add a task for it, or map it in the `## Scope Coverage` table to the existing task IDs that deliver it.
   - **Do not defer to pass the gate.** Only the user (or `spec.md` / `plan.md`) can put an item out of scope. If you think an item should be deferred, ask the user; a deferred row needs a reason.
   - **Unknown IDs or task IDs**: correct the label, mention or table row.
   - Re-run `{SCRIPT}`. Repeat at most 3 times. If it still fails, stop and tell the user exactly which items remain open.

4. **Exit code 2 — ERROR.** A setup problem (no `tasks.md`, feature not found, bad config). Show the message and the fix.
