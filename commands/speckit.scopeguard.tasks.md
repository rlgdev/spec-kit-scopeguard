---
description: "scopeGuard tasks gate: find every in-scope user story and requirement from spec.md that tasks.md does not carry, add the missing tasks (up to 4 iterations), and escalate with a problem report if it cannot be resolved"
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

Make sure the task list carries the whole in-scope part of `spec.md`, and **fix the task list when it does not**. Every user story and traced requirement that `plan.md` does not mark `deferred` must be carried by at least one task in `tasks.md`:

- a user story by tasks labelled `[USn]` (or listed under a `User Story n` phase heading);
- a requirement by naming its ID in a task description (for example `(FR-003)`), or by a row in the `## Scope Coverage` table of `tasks.md` that maps it to existing task IDs.

This command is the `after_tasks` hook when `integration: hooks` is configured; with the default `integration: inline` (with the scopeguard-templates preset) the same gate runs inside `/speckit.tasks` and this command prints `skipped`. It can also be run by hand. The script decides, you resolve. Exit codes: **0** pass, **1** resolve, **3** escalate, **2** setup error.

## Steps

Start with `N = 0`.

1. **Check.** From the repository root run `{SCRIPT} --iteration N`. Append `--feature-dir <dir>` if the user input names a feature directory. If this command is running as a Spec Kit hook (another command emitted `EXECUTE_COMMAND: speckit.scopeguard.tasks`), also append `--via hook`. Keep the exit code and the full output.

2. **Exit 0 — pass or skipped.** If the output says `skipped`, the gate runs inline in this project (inside `/speckit.tasks`); say nothing more and let the calling command continue. Otherwise report one line, for example `scopeGuard tasks gate: PASS after N resolution iteration(s) (10 carried, 1 waived)`, then list waived items and warnings exactly as printed. Done — the calling command continues.

3. **Exit 1 — resolve.** The output lists every open item under `RESOLVE`, each with its text from `spec.md`. Resolve **all** of them in this iteration, then set `N = N + 1` and go back to step 1.
   - **User story without tasks** — add a phase for it in priority order, in the existing format: `## Phase X: User Story n - Title (Priority: Pn)` with **Goal** and **Independent Test**, then concrete tasks `- [ ] T### [P?] [USn] Description with exact file path` that deliver its acceptance scenarios, using the structure, data model and contracts from `plan.md`. Add test tasks if the spec or plan asks for tests. Continue the task numbering from the highest existing ID; never renumber existing tasks. Update the dependency notes if the new phase depends on others.
   - **Requirement without tasks** — name its ID in the description of the task(s) that implement it, or add a task for it, or add a row to the `## Scope Coverage` table of `tasks.md` mapping it to the existing task IDs that deliver it.
   - **Unknown story label, requirement ID or task ID** — correct the label, mention or table row.
   - If `plan.md` does not give enough design to write the tasks for an item, extend the plan for that item first (and its Scope Coverage row), then add the tasks.
   - Never edit, renumber, merge or delete IDs in `spec.md`.
   - **Never defer an item just to make the gate pass.** Only `spec.md`, `plan.md` or the user can put an item out of scope. If an item cannot be broken into tasks without a decision only the user can make, leave it open — the gate will escalate with a problem report instead of you guessing.
   - Keep a short note of what you changed for each item in each iteration; you need it if the gate escalates.

4. **Exit 3 — escalate or stop.** Stop resolving.
   - If the output says `AUTOCORRECT OFF` (autocorrect is switched off in the config), report the listed violations to the user and end the calling command; nothing else to do.
   - Otherwise the gate is still failing after the last allowed iteration (`autocorrect.max_iterations`, 4 by default):
     - Open the problem report named in the output (`scopeguard-escalation-tasks.md` in the feature directory) and replace every `TODO(agent)` with: what you attempted for that item in each iteration, the blocker, and the concrete decision needed from the user.
     - Report to the user: `scopeGuard tasks gate: ESCALATED — <n> item(s) could not be included in the task list`, then per item its ID, title, blocker and decision needed, and the path of the report.
     - **End the calling command here.** Do not report the task list as complete and do not start implementation.

5. **Exit 2 — error.** A setup problem (no `tasks.md`, feature not found, bad config). Show the message and the fix.
