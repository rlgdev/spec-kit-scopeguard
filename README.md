# scopeGuard for Spec Kit

[![CI](https://github.com/rlgdev/spec-kit-scopeguard/actions/workflows/ci.yml/badge.svg)](https://github.com/rlgdev/spec-kit-scopeguard/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

> Part of the **Guardians** family for Spec Kit (scopeGuard · archiGuard · auditGuard). Install the three together with the [Guardians bundle](https://github.com/rlgdev/spec-kit-guardians) and start with its [getting-started guide](https://github.com/rlgdev/spec-kit-guardians/blob/main/docs/getting-started.md).

**Deterministic scope gates for [GitHub Spec Kit](https://github.com/github/spec-kit).**
No user story or requirement from `spec.md` can be dropped silently by `/speckit.plan`,
`/speckit.tasks` or `/speckit.implement`. The scope gate runs as a mandatory step inside
`/speckit.plan` and `/speckit.tasks`. When an item is missing, the agent puts it back into the plan or
task list. If that still fails after the configured number of iterations (default 4), the agent
stops and hands you a problem report. All of this is set in one config file.

## Why

When an agent turns a specification into a plan, it can quietly leave out a whole user story. Spec Kit
does not notice:

- the core plan template has no section that lists the spec's user stories, so the plan never
  has to account for them;
- `/speckit.analyze` runs only after `tasks.md` exists, and it is a prompt: it can only report what
  the model happened to load.

scopeGuard reads the IDs from `spec.md`, which are user stories (`US1`, `US2`, ...) and requirements
(`FR-001`, `NFR-001`, optionally `SC-001`). After each phase it checks them with plain parsing
and set arithmetic, with no LLM in the loop. Anything missing fails the gate. Anything deliberately
left out has to be written down as a deferral with a reason.

## How it works

By default (`integration: inline`) scopeGuard is part of the regular Spec Kit commands. The
preset wraps `/speckit.plan` and `/speckit.tasks` with two mandatory steps, so there is no
separate command to run:

| Command | Step | What happens |
|---------|------|--------------|
| `/speckit.plan` | **(A) scope inventory**, right after Setup | prints every scope ID and the scope contract the plan must satisfy |
| `/speckit.plan` | **(B) scope gate**, before the post-execution hooks and the Completion Report | every ID needs a row in plan.md's `## Scope Coverage` table: `covered` (with where), or `deferred` (with a reason). Missing items are fixed (autocorrect) |
| `/speckit.tasks` | **(A) scope inventory**, right after Setup | prints the in-scope IDs (not deferred by the plan) |
| `/speckit.tasks` | **(B) scope gate**, before the post-execution hooks and the Completion Report | every in-scope story has `[USn]` tasks and every in-scope requirement is named by a task or mapped in tasks.md's coverage table. Missing items are fixed (autocorrect) |
| after `/speckit.implement` | optional hook → `/speckit.scopeguard.implement` | every task that carries an in-scope item is checked off |

With `integration: hooks` the same gates run as separate scopeGuard commands
(`/speckit.scopeguard.inventory`, `/speckit.scopeguard.plan`, `/speckit.scopeguard.tasks`). Spec Kit's
`before_plan`, `after_plan`, `before_tasks` and `after_tasks` hooks trigger them.
[Configuration](#configuration) shows how to switch.

Each item gets a verdict: **pass**, **violation** or **waived** (deferred with a reason, always shown).
Exit codes: `0` pass, `1` violations to resolve, `2` setup error, `3` escalated (still failing
after the last allowed iteration, or the first failing check with `autocorrect.enabled: false`; only
inside the resolution loop, with `--iteration`).

### Resolve, re-check, escalate

The plan and tasks gates do more than report. With autocorrect on (the default) they run a
bounded loop:

1. **Check.** The script lists every missing or invalid item under `RESOLVE`, with that item's text from `spec.md`.
2. **Resolve.** The agent adds the missing item to the artifact.
   - **Plan gate:** it designs the item into the plan (data model, contracts, research, structure) and adds its `covered` row.
   - **Tasks gate:** it adds a phase with `[USn]` tasks for the story, or names the requirement in a task.

   It never edits `spec.md`, and it never defers an item without a reason from the spec or from you.
3. **Re-check** with the next `--iteration`. The loop repeats until the gate passes, for at most
   `autocorrect.max_iterations` (default **4**) resolve-and-recheck iterations.
4. **Escalate.** If items are still open after the last iteration, the script exits `3` and
   writes `scopeguard-escalation-<gate>.md` into the feature directory. The agent then completes
   the report: for each unresolved item, what it tried, the blocker, and the decision it needs from you.
   It reports this back to you and stops the command, instead of looping or claiming success.

If an item can only be included with information or a decision that only you can give, the agent
leaves it open, so you get a problem report instead of a guess. With `autocorrect.enabled: false`
the gate does not fix anything: it reports the gaps and stops the command at the first failing
check. Iteration history is kept in
`<feature>/.scopeguard/history-<gate>.json`.
[`examples/escalation`](examples/escalation) shows a real case, a story that conflicts with the
constitution, along with the problem report an agent produced for it.

## Install

Requires Spec Kit (`specify-cli`) 0.12.17 or newer. The checker is a single Python file
(standard library only, Python 3.9+). If `python` is not on `PATH`, the launchers use the
Python that ships with `specify-cli`, or `uv`.

From your Spec Kit project root:

```bash
# 1. the extension: the checker, its commands and hooks, and the config file
specify extension add scopeguard --from https://github.com/rlgdev/spec-kit-scopeguard/releases/download/v0.4.1/scopeguard.zip

# 2. the preset: makes the gate a step of /speckit.plan and /speckit.tasks,
#    and adds the "Scope Coverage" tables to the plan and tasks templates
specify preset add --from https://github.com/rlgdev/spec-kit-scopeguard/releases/download/v0.4.1/scopeguard-preset.zip

# 3. apply the config (default: gates inline in /speckit.plan and /speckit.tasks, scopeGuard hooks off)
bash .specify/extensions/scopeguard/scripts/bash/scopeguard.sh configure
#    Windows: .specify/extensions/scopeguard/scripts/powershell/scopeguard.ps1 configure
#    or, inside your agent: /speckit.scopeguard.configure
```

Spec Kit asks you to confirm the extension install from a URL (step 1); answer `y`. The preset install (step 2) does not ask. Use `releases/latest/download/...`
instead of `releases/download/v0.4.1/...` to always get the newest release.

<details>
<summary>Install through a catalog (for teams)</summary>

```bash
specify extension catalog add https://raw.githubusercontent.com/rlgdev/spec-kit-scopeguard/main/catalog/extensions.json --name scopeguard --install-allowed
specify extension add scopeguard

specify preset catalog add https://raw.githubusercontent.com/rlgdev/spec-kit-scopeguard/main/catalog/presets.json --name scopeguard --install-allowed
specify preset add scopeguard-templates
```

</details>

To upgrade an existing install:

1. Add `--force` to the extension command.
2. Run `specify preset remove scopeguard-templates` before adding the new preset.
3. Run step 3 again.

Your `scopeguard-config.yml` is kept. A v0.2 `remediation.max_iterations` setting is still read.

Check it worked: `configure` prints `integration: inline`, and the hook table shows the plan and tasks
hooks `off`. Then use Spec Kit as usual: `/speckit.plan` and `/speckit.tasks` now include the scope
gate. If you skip step 3, the gates still run once, inline. The hooks then only print `skipped`.

## What a failure looks like

From [`examples/missing-story`](examples/missing-story). The plan in this example skipped user story 3:

```text
$ bash .specify/extensions/scopeguard/scripts/bash/scopeguard.sh plan
scopeGuard 0.4.1 | gate: plan | feature: specs/001-team-board
spec scope: 4 user stories, 7 requirements

  [FAIL]   US3      Share a board with teammates (P2)
             -> missing from plan.md 'Scope Coverage' - silently dropped from scope
  [FAIL]   FR-004   System MUST let the board owner invite teammates by e-mai...
             -> missing from plan.md 'Scope Coverage' - silently dropped from scope
  [FAIL]   FR-007   System MUST keep a per-card history of column changes.
             -> deferred without a reason (a waiver must say why)  (plan.md:56)
  [PASS]   8 item(s) accounted for (use --verbose to list)

RESULT: FAIL | 3 violation(s), 8 pass, 0 waived, 0 warning(s) | coverage 8/11 in-scope items (72.7%)

To fix, account for each missing item in plan.md "## Scope Coverage":
  | US3 | Share a board with teammates (P2) | covered | <where the plan handles it> | |
  | FR-004 | System MUST let the board owner invite teammates by e-mail and revo... | covered | <where the plan handles it> | |
```

Inside `/speckit.plan` and `/speckit.tasks` (or the hooks) the gate runs with `--iteration N`. It then also prints each open item's spec text
under `RESOLVE`, plus the next step (`re-run this gate with --iteration N+1`, or `ESCALATE` with
the path of the problem report).

## Commands

| Command | What it does |
|---------|--------------|
| `/speckit.scopeguard.inventory` | Lists every user story and requirement ID in `spec.md` and the scope contract. Prints a ready-made coverage table if the plan has none yet. |
| `/speckit.scopeguard.plan` | Plan gate as a separate command: resolves missing items in the plan, escalates after the autocorrect limit. The hook in `integration: hooks`; can also be run by hand. |
| `/speckit.scopeguard.tasks` | Tasks gate as a separate command: adds tasks for missing items, escalates after the autocorrect limit. |
| `/speckit.scopeguard.implement` | Implement gate. |
| `/speckit.scopeguard.report` | Coverage matrix for every item across plan / tasks / implement. Also saved as `scopeguard-report.md` in the feature directory. |
| `/speckit.scopeguard.compare` | Compares two feature directories, for example two runs of the same spec, item by item. |
| `/speckit.scopeguard.configure` | Shows and applies the config: inline or hooks, autocorrect, gates. |

With skills-based integrations (such as Claude Code in Spec Kit 1.x) these appear as
`/speckit-scopeguard-plan` and so on.

The same checker runs without an agent, for scripts and CI:

```bash
bash .specify/extensions/scopeguard/scripts/bash/scopeguard.sh <command> [options]    # macOS / Linux / Git Bash
pwsh .specify/extensions/scopeguard/scripts/powershell/scopeguard.ps1 <command> [options]  # Windows PowerShell
python .specify/extensions/scopeguard/scripts/python/scopeguard.py <command> [options]
```

Commands: `inventory`, `plan`, `tasks`, `implement`, `check` (every gate whose artifact exists; add
`--implement` to include that gate), `report`, `compare DIR_A DIR_B`, `configure [--dry-run]`.
Options: `--feature-dir specs/<feature>`, `--all`, `--json`, `--format md`, `--out FILE [--append]`,
`--save`, `--verbose`, `--report-only`, `--config FILE`, `--iteration N` (resolution loop; exit `3` and
a problem report once `N` reaches `autocorrect.max_iterations`), `--via inline|hook` (used by the inline
steps and the hooks; the call is skipped when the config says the other one runs the gate).

The active feature is found the same way Spec Kit finds it: `SPECIFY_FEATURE_DIRECTORY`, then
`.specify/feature.json`, then the git branch name, then the only directory under `specs/`.

## The Scope Coverage tables

**plan.md** (added by the preset; the inventory prints a starting version). One row per ID, no
exceptions:

```markdown
## Scope Coverage

| ID | Title | Status | Plan reference | Reason (required if deferred) |
|----|-------|--------|----------------|-------------------------------|
| US1 | Create a board and add cards (P1) | covered | data-model.md Board, Card; contracts/boards.yaml | |
| US3 | Share a board with teammates (P2) | covered | contracts/invitations.yaml | |
| FR-007 | Per-card history | deferred | | PO decision 2026-10-05: phase 2 |
```

- Status `covered` (also accepted: `planned`, `in scope`, `yes`, ✅) or `deferred` (also `out of scope`,
  `excluded`, `postponed`). `partial` counts as covered, with a warning.
- A deferral without a reason is a violation. So is a `<placeholder>` plan reference, a row for an ID that
  `spec.md` does not define, or the same ID marked both covered and deferred. An empty plan reference
  is a warning (a violation with `plan.require_reference_for_covered: true`).
- One row may list several IDs (`FR-001, FR-002`).

**tasks.md**: user stories are carried by Spec Kit's normal `[USn]` labels. Tasks under a
`Phase N: User Story n` heading count even without a label. Requirements are carried by naming
the ID in a task (`- [ ] T012 [US1] Card CRUD in api/cards.ts (FR-002)`) or by a row in the
optional `## Scope Coverage` table of tasks.md (`| FR-002 | ... | covered | T009, T012 | |`).
Items the plan deferred are waived automatically.

## Configuration

All settings live in one file, `.specify/extensions/scopeguard/scopeguard-config.yml`. It is
created when you install the extension. Every key is optional; the full list with comments is in
[`config-template.yml`](config-template.yml). The main switches:

```yaml
# Where the gate runs:
#   inline   = mandatory step inside /speckit.plan and /speckit.tasks (default; needs the preset)
#   hooks    = separate scopeGuard commands triggered by Spec Kit hooks
#   embedded = only when another tool calls scopeGuard's command line (e.g. archiGuard)
integration: inline

autocorrect:
  enabled: true          # false = the gate only reports what is missing and stops the command
  max_iterations: 4      # fix-and-recheck iterations before escalating with a problem report

mode: enforce            # report = never stop or fail, only measure (labs, trials)

plan:
  enabled: true          # switch a gate off completely
  check_requirements: true   # false = only user stories must be in the plan table
tasks:
  enabled: true
implement:
  enabled: true          # the optional after_implement check

ids:
  story_key: US                     # or UC: use cases (UC-001, task labels [UC-001]) instead of user stories
  story_name: null                  # e.g. "Use Case" for headings like "### Use Case 2 - ..."
  requirement_prefixes: [FR, NFR]   # add SC to trace Success Criteria too
unknown_ids: violation              # IDs in plan/tasks that spec.md does not define
features:
  exclude: ["001-*"]                # skip features planned before scopeGuard (for --all)
```

Most settings take effect on the next run. A key scopeGuard does not know (a typo, a setting of another
version) is an error: the gate exits `2` and names the key. After changing `integration`, or switching a gate on or
off, run `configure`. It switches the matching scopeGuard hooks on or off in
`.specify/extensions.yml`, and prints what is in force:

```text
$ bash .specify/extensions/scopeguard/scripts/bash/scopeguard.sh configure
scopeGuard 0.4.1 | configure
config: .specify/extensions/scopeguard/scopeguard-config.yml

  integration   : inline
  autocorrect   : on, max 4 iteration(s), then escalate
  gates         : plan on, tasks on, implement on
  mode          : enforce

  /speckit.plan and /speckit.tasks run the scope gate as a mandatory step of their own.

  Hooks in .specify/extensions.yml:
    before_plan      speckit.scopeguard.inventory     off   (was on)
    after_plan       speckit.scopeguard.plan          off   (was on)
    before_tasks     speckit.scopeguard.inventory     off   (was on)
    after_tasks      speckit.scopeguard.tasks         off   (was on)
    after_implement  speckit.scopeguard.implement     on
```

Use `--dry-run` to preview. Inside the agent, `/speckit.scopeguard.configure use hooks` (or
`6 iterations`, `autocorrect off`) edits the file and applies it in one go.

Two safety nets mean the config is never silently out of sync with the installed commands:

- **The gate runs exactly once.** The inline steps and the hook commands check the config at run
  time, and the one that is not configured prints `skipped`. This holds even if you forget to run
  `configure`, or a reinstall turns the hooks back on.
- **Inline needs the preset.** If you choose `inline` but the scopeguard-templates preset is not
  installed or is disabled, scopeGuard falls back to the hooks, and `configure` tells you what to
  install.

### Embedded in another tool

With `integration: embedded`, scopeGuard has no hooks and no inline steps of its own: `configure`
switches every scopeGuard hook off, and the inline steps and hook commands print `skipped`. The gates
run only when another tool calls the command line (`scopeguard.py plan --feature-dir ... --json`), as
[archiGuard](https://github.com/rlgdev/spec-kit-archiguard) does for its scope gate. That tool then owns
the iteration budget and the escalation. Do not install the scopeguard-templates preset with it.

### Use cases instead of user stories

The story key is configurable. With `ids.story_key: UC` (and `story_name: Use Case` if the spec also
writes the long form), scopeGuard traces use cases: headings `### UC-001 - Place an order` or
`### Use Case 1 - ...`, Scope Coverage rows `UC-001`, task labels `[UC-001]`, and tasks.md phase titles
`Phase 3: UC-001 - ...`. `UC-001`, `UC-1` and `Use Case 1` are the same item.

Personal overrides go in `local-config.yml` next to the config file. For a single run you can use
the environment variables `SCOPEGUARD_INTEGRATION`, `SCOPEGUARD_AUTOCORRECT`,
`SCOPEGUARD_MAX_ITERATIONS` and `SCOPEGUARD_MODE`.

## CI

Use it as a GitHub Action. It fails the job when any feature in `specs/` has a scope gap, and
writes the report to the job summary:

```yaml
- uses: actions/checkout@v5
- uses: rlgdev/spec-kit-scopeguard@v0.4.1
  with:
    command: check        # check | plan | tasks | implement | report
    features: all         # or specs/001-my-feature
    implement: "false"    # "true" = also require all carrying tasks to be done
```

By default (`engine: installed`) the action runs the scopeGuard the project installed under
`.specify/extensions/scopeguard`, so CI runs the same version as the developers, and falls back to its
own copy when the project has none; `engine: action` always uses the action's own copy.

On other CI systems: `python .specify/extensions/scopeguard/scripts/python/scopeguard.py check --all`.

## Hard stops with the workflow engine

[`workflows/scopeguard-sdd`](workflows/scopeguard-sdd/workflow.yml) is the standard
specify → plan → tasks → implement workflow with shell-step scope gates in between. The run
stops at the first gap. Fix the plan and run `specify workflow resume <run_id>`.

```bash
specify workflow add scopeguard-sdd --from https://raw.githubusercontent.com/rlgdev/spec-kit-scopeguard/main/workflows/scopeguard-sdd/workflow.yml
specify workflow run scopeguard-sdd -i spec="..."
# Windows: add -i scopeguard="pwsh -File .specify/extensions/scopeguard/scripts/powershell/scopeguard.ps1"
```

## Comparing runs (spec-to-app labs)

Build the same spec twice (two people, two agents or two models) and compare scope coverage
item by item, instead of comparing plans by hand:

```bash
bash .specify/extensions/scopeguard/scripts/bash/scopeguard.sh compare \
  ../run-a/specs/001-team-board ../run-b/specs/001-team-board --labels run-a,run-b --out compare.md
```

The output gives coverage per phase for each run, plus a table of every ID showing where the runs
differ (`MISSING`, `INVALID`, `OPEN`, `waived`, `ok`). Run `report --save` in each run to keep a
per-run record. To measure without blocking anyone, set `mode: report`.

## What scopeGuard does and does not prove

- It proves that **every scope item is accounted for** at each phase, and that every omission
  is either a violation or a deferral with a reason.
- It does **not** judge whether the plan handles an item *well*, or whether a ticked task is really
  done. A `covered` row whose reference points nowhere still needs a human reviewer. The
  *Plan reference* column makes that review quick.
- The resolving is done by the agent, following the gate command. The checker verifies the
  result after every iteration and enforces the iteration limit, so the loop cannot run forever
  or end in a claimed success while items are still missing.
- IDs come from the standard Spec Kit spec format (`### User Story N - Title (Priority: Pn)`,
  `- **FR-001**: ...`). Another story key (`ids.story_key`, e.g. `UC`) or heading style
  (`ids.story_pattern`) can be configured.

## Uninstall

```bash
specify extension remove scopeguard
specify preset remove scopeguard-templates
```

## Development

```bash
python -m pytest -q            # engine tests
python tools/build.py --check  # versions, manifests and catalogs agree (CI)
python tools/build.py          # dist/scopeguard.zip, dist/scopeguard-preset.zip, dist/SHA256SUMS
bash tools/e2e-speckit.sh      # install into a fresh Spec Kit project and drive it (needs `specify`)
```

To release, bump the version in `extension.yml`, `preset/preset.yml`, the workflow,
`scripts/python/scopeguard.py` and `catalog/*.json`, add a CHANGELOG entry, then push a `vX.Y.Z`
tag or publish a release with that tag in the GitHub UI. The release workflow builds the
archives and attaches them to the release.

[CONTRIBUTING.md](CONTRIBUTING.md) has the conventions and the release steps of the family.

## License

[MIT](LICENSE)
