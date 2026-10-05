---
description: Generate an actionable, dependency-ordered tasks.md for the feature based on available design artifacts, with a mandatory scopeGuard scope gate that keeps every in-scope user story and requirement of spec.md in the task list.
strategy: wrap
handoffs:
  - label: Analyze For Consistency
    agent: speckit.analyze
    prompt: Run a project analysis for consistency
    send: true
  - label: Implement Project
    agent: speckit.implement
    prompt: Start the implementation in phases
    send: true
---

> **scopeGuard is part of this command.** Besides the steps below, this command has two mandatory
> scopeGuard steps, described at the end of this document:
>
> - **(A) Scope inventory**: run it right after the Setup step, before you generate tasks.
> - **(B) Scope gate**: run it after `tasks.md` is written, and before the Mandatory Post-Execution
>   Hooks and the Completion Report.
>
> The command is complete only when step B passes. If step B escalates, the command ends with the
> escalation report instead of the Completion Report.

{CORE_TEMPLATE}

## scopeGuard (A): scope inventory (mandatory, right after Setup)

Run the scopeGuard checker from the repository root. Use the variant that matches the project's script type (`script` in `.specify/init-options.json`), and pass the FEATURE_DIR from Setup:

- `sh`: `bash .specify/extensions/scopeguard/scripts/bash/scopeguard.sh inventory --via inline --feature-dir <FEATURE_DIR>`
- `ps`: `.specify/extensions/scopeguard/scripts/powershell/scopeguard.ps1 inventory --via inline --feature-dir <FEATURE_DIR>`
- `py`: `python .specify/extensions/scopeguard/scripts/python/scopeguard.py inventory --via inline --feature-dir <FEATURE_DIR>`

What to do with the result:

- **It prints `skipped`.** scopeGuard runs through hooks in this project. Continue normally and skip step B.
- **It prints the scope list.** Every ID shown with a `[plan: ...]` status other than `deferred` must be carried by at least one task:
  - user stories by tasks labelled `[USn]`;
  - requirements by naming the ID in a task description, for example `(FR-003)`, or by a row in the `## Scope Coverage` table of `tasks.md`.
- **Exit code 2.** Tell the user scopeGuard could not run (show the message) and continue the command.

## scopeGuard (B): scope gate (mandatory, before the post-execution hooks and the Completion Report)

The script decides; you resolve. Exit codes: **0** pass (or skipped), **1** resolve, **3** escalate or stop, **2** setup error. Start with `N = 0`.

1. **Check.** Run the same checker with `tasks --via inline --iteration N --feature-dir <FEATURE_DIR>` (for example `bash .specify/extensions/scopeguard/scripts/bash/scopeguard.sh tasks --via inline --iteration N --feature-dir <FEATURE_DIR>`). Keep the exit code and the full output.

2. **Exit 0: pass.** Add one line to your Completion Report, for example `scopeGuard: PASS after N resolution iteration(s) (10 carried, 1 waived)`, and list waived items and warnings as printed. Continue with the Mandatory Post-Execution Hooks and the Completion Report.

3. **Exit 1: resolve.** The output lists every open item under `RESOLVE`, each with its text from `spec.md`. Resolve **all** of them, then set `N = N + 1` and go back to step 1.
   - **User story without tasks:** add a phase for it in priority order, in the existing format.
     - Use `## Phase X: User Story n - Title (Priority: Pn)` with **Goal** and **Independent Test**.
     - Add concrete tasks `- [ ] T### [P?] [USn] Description with exact file path` that deliver its acceptance scenarios, using the structure, data model and contracts from `plan.md`.
     - Continue the numbering from the highest existing task ID; never renumber existing tasks.
   - **Requirement without tasks:** name its ID in the task(s) that implement it, or add a task, or map it to existing task IDs in the `## Scope Coverage` table of `tasks.md`.
   - **Unknown story label, requirement ID or task ID:** correct it.
   - If `plan.md` lacks the design for an item, extend the plan for it first (with its Scope Coverage row), then add the tasks.
   - **Never defer an item just to make the gate pass.** If an item cannot be broken into tasks without a decision only the user can make, leave it open. The gate will escalate with a problem report.
   - Keep a short note of what you changed per item in each iteration.

4. **Exit 3: escalate or stop.** Stop resolving.
   - If the output says `AUTOCORRECT OFF`: report the listed violations to the user.
   - Otherwise:
     1. Open the problem report named in the output (`scopeguard-escalation-tasks.md` in the feature directory).
     2. Replace every `TODO(agent)` with what you attempted for that item in each iteration, the blocker, and the concrete decision needed from the user.
     3. Report to the user: `scopeGuard: ESCALATED — <n> item(s) could not be included in the task list`, then each item's ID, title, blocker and decision needed, and the path of the report.
   - **The command ends here.** Do not run the after_tasks hooks and do not write the Completion Report. The task list is not complete; do not start implementation.

5. **Exit 2: error.** Show the message and the fix, then continue with the Completion Report and say the scope gate did not run.
