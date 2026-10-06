---
description: "scopeGuard plan gate: find every user story and requirement from spec.md that plan.md left out, resolve it in the plan (up to 4 iterations), and escalate with a problem report if it cannot be resolved"
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

Make sure the implementation plan covers the whole scope of `spec.md`, and **fix the plan when it does not**. Every user story (`US1`, `US2`, ...) and every traced requirement (`FR-###`, `NFR-###`) must be planned and listed in the `## Scope Coverage` table of `plan.md`: `covered` (with where the plan handles it) or `deferred` (with a reason that comes from `spec.md` or the user). This command is the `after_plan` hook when `integration: hooks` is configured; with the default `integration: inline` (with the scopeguard-templates preset) the same gate runs inside `/speckit.plan` and this command prints `skipped`. It can also be run by hand.

The script decides, you resolve. Never re-interpret its verdict. Exit codes: **0** pass, **1** resolve, **3** escalate, **2** setup error.

## Steps

Start with `N = 0`.

1. **Check.** From the repository root run `{SCRIPT} --iteration N`. Append `--feature-dir <dir>` if the user input names a feature directory. If this command is running as a Spec Kit hook (another command emitted `EXECUTE_COMMAND: speckit.scopeguard.plan`), also append `--via hook`. Keep the exit code and the full output.

2. **Exit 0 — pass or skipped.** If the output says `skipped`, the gate runs inline in this project (inside `/speckit.plan`); say nothing more and let the calling command continue. Otherwise report one line, for example `scopeGuard plan gate: PASS after N resolution iteration(s) (10 covered, 1 waived)`, then list waived items and warnings exactly as printed. Done — the calling command continues.

3. **Exit 1 — resolve.** The output lists every open item under `RESOLVE`, each with its text from `spec.md`. Resolve **all** of them in this iteration, then set `N = N + 1` and go back to step 1.
   - **Missing user story or requirement** — plan it for real, from its spec text:
     1. Work out what the plan needs for it: entities and fields (`data-model.md`), interfaces, endpoints or events (`contracts/`), technology or approach decisions (`research.md`), a validation scenario (`quickstart.md`), project structure, and its effect on the Constitution Check.
     2. Update those artifacts and `plan.md`, consistent with the design that already exists.
     3. Add its row to `## Scope Coverage`: `| ID | Title | covered | <the sections or files you added or changed> | |`.
   - **Placeholder or empty plan reference** — replace it with the concrete place in the plan.
   - **Deferred without a reason, unrecognized status, conflicting rows** — fix the row. A deferral reason may only come from `spec.md` or the user.
   - **Unknown ID** (in the plan but not defined in `spec.md`) — remove or correct the row.
   - Never edit, renumber, merge or delete IDs in `spec.md`, and do not touch rows of items that already pass.
   - **Never defer an item just to make the gate pass.** If an item cannot be planned without information or a decision only the user can give, leave it open — the gate will escalate with a problem report instead of you guessing.
   - Keep a short note of what you changed for each item in each iteration; you need it if the gate escalates.

4. **Exit 3 — escalate or stop.** Stop resolving.
   - If the output says `AUTOCORRECT OFF` (autocorrect is switched off in the config), report the listed violations to the user and end the calling command; nothing else to do.
   - Otherwise the gate is still failing after the last allowed iteration (`autocorrect.max_iterations`, 4 by default):
     - Open the problem report named in the output (`scopeguard-escalation-plan.md` in the feature directory) and replace every `TODO(agent)` with: what you attempted for that item in each iteration, the blocker (missing information, conflict with the constitution or another requirement, technical constraint, ...), and the concrete decision needed from the user.
     - Report to the user: `scopeGuard plan gate: ESCALATED — <n> item(s) could not be included in the plan`, then per item its ID, title, blocker and decision needed, and the path of the report.
     - **End the calling command here.** Do not report the plan as complete and do not continue to task generation.

5. **Exit 2 — error.** A setup problem (no `plan.md`, feature not found, bad config). Show the message and the fix, for example re-running with `--feature-dir specs/<feature>`.
