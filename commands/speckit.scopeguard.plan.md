---
description: "scopeGuard plan gate: verify every user story and requirement in spec.md is accounted for in plan.md (covered, or deferred with a reason)"
scripts:
  sh: bash scripts/bash/scopeguard.sh plan
  ps: scripts/powershell/scopeguard.ps1 plan
  py: scripts/python/scopeguard.py plan
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Goal

Deterministically verify that the implementation plan did not silently drop scope. Every user story (`US1`, `US2`, ...) and every traced requirement ID (`FR-###`, `NFR-###`) defined in `spec.md` must have a row in the `## Scope Coverage` table of `plan.md`, with status `covered` (and where the plan handles it) or `deferred` (with a reason). This command runs automatically as the mandatory `after_plan` hook.

The verdict comes from the script, not from your judgement. Do not re-interpret it and never report the plan as complete while the script exits non-zero.

## Steps

1. Run `{SCRIPT}` from the repository root. If the user input above names a feature directory, append `--feature-dir <that directory>`. Keep the exit code and the full output.

2. **Exit code 0 — PASS.** Report one line, for example `scopeGuard plan gate: PASS (10 covered, 1 waived)`, then list waived items and warnings exactly as printed. Done.

3. **Exit code 1 — FAIL.** Show the user the `[FAIL]` lines exactly as printed. Then fix `plan.md` (never `spec.md`):
   - **Missing item**: read it in `spec.md`, make the plan genuinely handle it (research, data model, contracts, project structure — whatever it needs) and add a `covered` row to the Scope Coverage table that says where. The fix block printed at the end of the output shows the rows to add.
   - **Do not defer to pass the gate.** Mark an item `deferred` only when `spec.md` or the user explicitly puts it out of scope; otherwise ask the user and wait for the answer. A deferred row needs the reason in the Reason column.
   - **Deferred without a reason / unrecognized status / conflicting rows**: correct that row.
   - **Unknown ID** (referenced in the plan but not defined in `spec.md`): remove or correct the row; do not add the ID to `spec.md`.
   - Never renumber, merge, rename or delete IDs in `spec.md`, and do not touch rows of items that already pass.
   - Re-run `{SCRIPT}`. Repeat at most 3 times. If it still fails, stop and tell the user exactly which items remain open and why. Do not continue as if the plan were complete.

4. **Exit code 2 — ERROR.** A setup problem (no `plan.md`, feature not found, bad config). Show the message and the fix, for example re-running with `--feature-dir specs/<feature>`.
