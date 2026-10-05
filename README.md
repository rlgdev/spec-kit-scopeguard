# scopeGuard for Spec Kit

[![CI](https://github.com/rlgdev/spec-kit-scopeguard/actions/workflows/ci.yml/badge.svg)](https://github.com/rlgdev/spec-kit-scopeguard/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**Deterministic scope gates for [GitHub Spec Kit](https://github.com/github/spec-kit).**
No user story or requirement from `spec.md` can be dropped silently by `/speckit.plan`,
`/speckit.tasks` or `/speckit.implement`.

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

| Phase | Hook (automatic) | Gate | Passes when |
|-------|------------------|------|-------------|
| before plan | `before_plan` → `/speckit.scopeguard.inventory` | – | prints every scope ID and the scope contract for the planner |
| after plan | `after_plan` → `/speckit.scopeguard.plan` | **plan** | every ID has a row in plan.md's `## Scope Coverage` table: `covered` (with where), or `deferred` (with a reason) |
| before tasks | `before_tasks` → `/speckit.scopeguard.inventory` | – | prints the in-scope IDs (not deferred by the plan) |
| after tasks | `after_tasks` → `/speckit.scopeguard.tasks` | **tasks** | every in-scope story has `[USn]` tasks and every in-scope requirement is named by a task or mapped in tasks.md's coverage table |
| after implement | `after_implement` (optional) → `/speckit.scopeguard.implement` | **implement** | every task that carries an in-scope item is checked off |

Each item gets a verdict: **pass**, **violation** or **waived** (deferred with a reason, always shown).
Exit codes: `0` pass, `1` violations, `2` setup error.

When a gate fails inside `/speckit.plan` or `/speckit.tasks`, the agent gets the missing IDs and the
exact rows to add. It is told to fix the plan or task list, never `spec.md`, and to defer
nothing without asking you. Then it re-runs the gate, at most three times.

## Install

Requires Spec Kit (`specify-cli`) 0.12.17 or newer. The checker is a single Python file
(standard library only, Python 3.8+). If `python` is not on `PATH`, the launchers use the
Python that ships with `specify-cli`, or `uv`.

From your Spec Kit project root:

```bash
# 1. the extension: commands, hooks and the checker
specify extension add scopeguard --from https://github.com/rlgdev/spec-kit-scopeguard/releases/download/v0.1.0/scopeguard.zip

# 2. the preset (recommended): adds the "Scope Coverage" tables to the plan and tasks templates
specify preset add --from https://github.com/rlgdev/spec-kit-scopeguard/releases/download/v0.1.0/scopeguard-preset.zip
```

Use `releases/latest/download/...` instead of `releases/download/v0.1.0/...` to always get the
newest release.

<details>
<summary>Install through a catalog (for teams)</summary>

```bash
specify extension catalog add https://raw.githubusercontent.com/rlgdev/spec-kit-scopeguard/main/catalog/extensions.json --name scopeguard --install-allowed
specify extension add scopeguard

specify preset catalog add https://raw.githubusercontent.com/rlgdev/spec-kit-scopeguard/main/catalog/presets.json --name scopeguard --install-allowed
specify preset add scopeguard-templates
```

</details>

Check it worked: `specify extension list` shows **scopeGuard**, and `.specify/extensions.yml`
lists the five hooks. Then use Spec Kit as usual. The gates run by themselves.

## What a failure looks like

From [`examples/missing-story`](examples/missing-story). The plan in this example skipped user story 3:

```text
$ bash .specify/extensions/scopeguard/scripts/bash/scopeguard.sh plan
scopeGuard 0.1.0 | gate: plan | feature: specs/001-team-board
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

## Commands

| Command | What it does |
|---------|--------------|
| `/speckit.scopeguard.inventory` | Lists every user story and requirement ID in `spec.md` and the scope contract. Prints a ready-made coverage table if the plan has none yet. |
| `/speckit.scopeguard.plan` | Plan gate. |
| `/speckit.scopeguard.tasks` | Tasks gate. |
| `/speckit.scopeguard.implement` | Implement gate. |
| `/speckit.scopeguard.report` | Coverage matrix for every item across plan / tasks / implement. Also saved as `scopeguard-report.md` in the feature directory. |
| `/speckit.scopeguard.compare` | Compares two feature directories, for example two runs of the same spec, item by item. |

With skills-based integrations (such as Claude Code in Spec Kit 1.x) these appear as
`/speckit-scopeguard-plan` and so on.

The same checker runs without an agent, for scripts and CI:

```bash
bash .specify/extensions/scopeguard/scripts/bash/scopeguard.sh <command> [options]    # macOS / Linux / Git Bash
pwsh .specify/extensions/scopeguard/scripts/powershell/scopeguard.ps1 <command> [options]  # Windows PowerShell
python .specify/extensions/scopeguard/scripts/python/scopeguard.py <command> [options]
```

Commands: `inventory`, `plan`, `tasks`, `implement`, `check` (every gate whose artifact exists; add
`--implement` to include that gate), `report`, `compare DIR_A DIR_B`.
Options: `--feature-dir specs/<feature>`, `--all`, `--json`, `--format md`, `--out FILE [--append]`,
`--save`, `--verbose`, `--report-only`, `--config FILE`.

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

`specify extension add` creates `.specify/extensions/scopeguard/scopeguard-config.yml`.
Every key is optional. See [`config-template.yml`](config-template.yml) for the full list. The
ones you are most likely to change:

```yaml
mode: enforce                      # report = never fail, only measure
ids:
  requirement_prefixes: [FR, NFR]  # add SC to trace Success Criteria too
plan:
  check_requirements: true         # false = only user stories must be in the plan table
  require_section: true            # false = fall back to "ID mentioned anywhere in plan.md"
unknown_ids: violation             # IDs in plan/tasks that spec.md does not define
features:
  exclude: ["001-*"]               # skip features planned before scopeGuard (for --all)
```

Personal overrides go in `scopeguard-config.local.yml` next to it. `SCOPEGUARD_MODE=report`
switches one run to report mode.

## CI

Use it as a GitHub Action. It fails the job when any feature in `specs/` has a scope gap, and
writes the report to the job summary:

```yaml
- uses: actions/checkout@v4
- uses: rlgdev/spec-kit-scopeguard@v0.1.0
  with:
    command: check        # check | plan | tasks | implement | report
    features: all         # or specs/001-my-feature
    implement: "false"    # "true" = also require all carrying tasks to be done
```

On other CI systems: `python .specify/extensions/scopeguard/scripts/python/scopeguard.py check --all`.

## Hard stops with the workflow engine

[`workflows/scopeguard-sdd`](workflows/scopeguard-sdd/workflow.yml) is the standard
specify → plan → tasks → implement workflow with shell-step scope gates in between. The run
stops at the first gap. Fix the plan and run `specify workflow resume <run_id>`.

```bash
specify workflow add --from https://raw.githubusercontent.com/rlgdev/spec-kit-scopeguard/main/workflows/scopeguard-sdd/workflow.yml
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
- IDs come from the standard Spec Kit spec format (`### User Story N - Title (Priority: Pn)`,
  `- **FR-001**: ...`). Other heading styles can be matched with `ids.story_pattern`.

## Uninstall

```bash
specify extension remove scopeguard
specify preset remove scopeguard-templates
```

## Development

```bash
python -m pytest -q          # engine tests
python tools/build.py        # dist/scopeguard.zip, dist/scopeguard-preset.zip, dist/SHA256SUMS
```

To release, bump the version in `extension.yml`, `preset/preset.yml` and
`scripts/python/scopeguard.py`, add a CHANGELOG entry, and push a `vX.Y.Z` tag. The release
workflow builds the archives and attaches them to the GitHub release.

## License

[MIT](LICENSE)
