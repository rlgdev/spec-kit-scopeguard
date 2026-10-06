---
description: "scopeGuard: list every user story and requirement ID defined in spec.md and the scope contract that plan.md and tasks.md must satisfy"
scripts:
  sh: bash scripts/bash/scopeguard.sh inventory
  ps: scripts/powershell/scopeguard.ps1 inventory
  py: scripts/python/scopeguard.py inventory
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Goal

Put the complete, deterministic list of scope items (user stories `US1`, `US2`, ... and requirement IDs such as `FR-001`) in front of whoever writes the next artifact, so nothing is dropped by accident. This command is the `before_plan` and `before_tasks` hook when `integration: hooks` is configured; with the default `integration: inline` (with the scopeguard-templates preset) the same inventory runs inside `/speckit.plan` and `/speckit.tasks` and this command prints `skipped`. It can also be run by hand at any time. It only reads files.

## Steps

1. Run `{SCRIPT}` from the repository root. If the user input above names a feature directory, append `--feature-dir <that directory>`. If this command is running as a Spec Kit hook (another command emitted `EXECUTE_COMMAND: speckit.scopeguard.inventory`), also append `--via hook`; if the output then says `skipped`, the inventory runs inline inside `/speckit.plan` and `/speckit.tasks` — say nothing more and continue.
2. If the script exits with code 2, show its error message and how to fix it (for example `--feature-dir specs/<feature>`), then stop.
3. Show the inventory to the user as printed (IDs, titles, priorities and any `[plan: ...]` status).
4. Treat the printed **SCOPE CONTRACT** as binding for the command that is about to run:
   - **Before planning**: `plan.md` must end up with a `## Scope Coverage` table holding exactly one row per printed ID. If the script printed a starting table, use it. Fill the *Plan reference* column with where the plan handles each item (section, data-model entity, contract, component).
   - **Before task generation**: every ID that the plan does not mark `deferred` must be carried by at least one task — user stories by tasks labelled `[USn]`, requirements by naming the ID in a task description (for example `(FR-003)`) or in the `## Scope Coverage` table of `tasks.md`.
   - An item may be marked `deferred` only when `spec.md` or the user explicitly puts it out of scope, and the reason must be written in the Reason column. If you think something should be deferred, ask the user first.
   - Never renumber, merge, rename or delete IDs in `spec.md`.
5. Continue with the calling command. Warnings (for example unresolved `[NEEDS CLARIFICATION]` markers) are informational; mention them once.
