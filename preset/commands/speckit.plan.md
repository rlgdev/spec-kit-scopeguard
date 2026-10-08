---
description: Execute the implementation planning workflow using the plan template to generate design artifacts, with a mandatory scopeGuard scope gate that keeps every user story and requirement of spec.md in the plan.
strategy: wrap
handoffs:
  - label: Create Tasks
    agent: speckit.tasks
    prompt: Break the plan into tasks
    send: true
  - label: Create Checklist
    agent: speckit.checklist
    prompt: Create a checklist for the following domain...
---

> **scopeGuard is part of this command.** Besides the steps below, this command has two mandatory
> scopeGuard steps, described at the end of this document:
>
> - **(A) Scope inventory**: run it right after the Setup step, before you design anything.
> - **(B) Scope gate**: run it after `plan.md` and the design artifacts are written, and before the
>   Mandatory Post-Execution Hooks and the Completion Report.
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

- **The checker is not there**: the error says a file under `.specify/extensions/scopeguard/` does not exist
  (`No such file or directory`, `can't open file`, `is not recognized`, whatever the exit code), so scopeGuard is
  not installed in this project. Report `scopeGuard not installed - skipped (remove the preset: specify preset remove scopeguard-templates)`,
  skip step B and continue the command normally. Any other error (for example no `python` on PATH) is not this
  case: treat it as **Exit code 2**.
- **It prints `skipped`.** scopeGuard runs through hooks in this project. Continue normally and skip step B.
- **It prints the scope list.** It shows every user story and requirement ID of `spec.md`, plus the scope contract. This list is binding for the plan:
  - `plan.md` must end with a `## Scope Coverage` table holding exactly one row per printed ID.
  - Each row is either `covered` (the *Plan reference* says where the plan handles the item) or `deferred` (only when `spec.md` or the user puts the item out of scope, with the reason in the Reason column).
  - Never renumber, merge, rename or delete IDs in `spec.md`.
- **Exit code 2.** Tell the user scopeGuard could not run (show the message) and continue the command.

## scopeGuard (B): scope gate (mandatory, before the post-execution hooks and the Completion Report)

The script decides; you resolve. Exit codes: **0** pass (or skipped), **1** resolve, **3** escalate or stop, **2** setup error. Start with `N = 0`.

1. **Check.** Run the same checker with `plan --via inline --iteration N --feature-dir <FEATURE_DIR>` (for example `bash .specify/extensions/scopeguard/scripts/bash/scopeguard.sh plan --via inline --iteration N --feature-dir <FEATURE_DIR>`). Keep the exit code and the full output.

2. **Exit 0: pass.** Add one line to your Completion Report, for example `scopeGuard: PASS after N resolution iteration(s) (10 covered, 1 waived)`, and list waived items and warnings as printed. Continue with the Mandatory Post-Execution Hooks and the Completion Report.

3. **Exit 1: resolve.** The output lists every open item under `RESOLVE`, each with its text from `spec.md`. Resolve **all** of them, then set `N = N + 1` and go back to step 1.
   - **Missing user story or requirement:** plan it for real, from its spec text.
     - Work out what it needs: entities and fields (`data-model.md`), interfaces, endpoints or events (`contracts/`), decisions (`research.md`), a validation scenario (`quickstart.md`), project structure, and the Constitution Check.
     - Update those artifacts and `plan.md`, consistent with the existing design.
     - Add its `covered` row to `## Scope Coverage`, with a concrete plan reference.
   - **Placeholder or empty reference, deferral without a reason, unrecognized status, conflicting rows or unknown ID:** fix that row.
   - **Never defer an item just to make the gate pass.** If an item cannot be planned without information or a decision only the user can give, leave it open. The gate will escalate with a problem report.
   - Keep a short note of what you changed per item in each iteration.

4. **Exit 3: escalate or stop.** Stop resolving.
   - If the output says `AUTOCORRECT OFF`: report the listed violations to the user.
   - Otherwise:
     1. Open the problem report named in the output (`scopeguard-escalation-plan.md` in the feature directory).
     2. Replace every `TODO(agent)` with what you attempted for that item in each iteration, the blocker, and the concrete decision needed from the user.
     3. Report to the user: `scopeGuard: ESCALATED — <n> item(s) could not be included in the plan`, then each item's ID, title, blocker and decision needed, and the path of the report.
   - **The command ends here.** Do not run the after_plan hooks and do not write the Completion Report. Tell the user which hooks this skips, as the output lists them under `NOT RUN`. The plan is not complete.

5. **Exit 2: error.** Show the message and the fix, then continue with the Completion Report and say the scope gate did not run.
