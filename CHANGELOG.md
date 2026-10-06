# Changelog

All notable changes to scopeGuard are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed

- Python 3.9 is now the stated minimum everywhere (README, `extension.yml`, launchers, engine docstring) and the
  engine refuses older interpreters like the siblings; CI never tested 3.8 and CONTRIBUTING already said 3.9.
- The `scopeguard-sdd` workflow carries the extension's version (0.4.0; it had stayed at 0.1.0) and
  `tools/build.py --check` keeps the two equal, as in archiGuard.

### Fixed

- `tools/build.py` marks every archive entry as made on Unix (`create_system = 3`), so an archive built on Windows
  has the same sha256 as one built on Linux/macOS and keeps the launchers' executable bit.
- The bash and PowerShell launchers reject the Windows Store `python3` alias stub (it prints an install hint and
  exits 0) with the same marker check auditGuard and Guardians use; the header comment already promised it.
- Unknown keys in `scopeguard-config.yml` / `local-config.yml` (top level and inside a section) and a section
  that is not a mapping are now a config error (exit 2) that names the key, instead of silently falling back
  to the default (or, for `plan: false`, a traceback) - as in archiGuard, auditGuard and Guardians.
- `workflows/scopeguard-sdd/workflow.yml` declares `requires.speckit_version: ">=0.12.17"`, the same floor as the
  extension and the preset (it said `>=0.8.5` since 0.1.0).
- The `inventory`, `plan` and `tasks` command files no longer say the command "runs automatically" as a mandatory
  hook: with the default `integration: inline` those hooks are off and the step runs inside `/speckit.plan` and
  `/speckit.tasks` (wording as in archiGuard's command files).
- `config-template.yml`: the `integration: hooks` comment names all four hooks the mode switches on
  (`before_plan` / `before_tasks` run `/speckit.scopeguard.inventory`, `after_plan` / `after_tasks` run the
  plan and tasks gates), as the README and `configure` already did. The README states that exit `3` also ends
  the resolution loop at the first failing check when autocorrect is off.

### Added

- `pytest.ini` (tests under `tests/`, no cache directory) as in the siblings.
- `tools/build.py --check` (CI): versions equal, the files the manifests name exist, the catalog `provides` counts
  match the manifests. The CI `lint` job runs it with pyflakes and shellcheck, like the siblings.
- Repository governance for corporate use: `CODEOWNERS`, `SECURITY.md` (private vulnerability reporting),
  `CONTRIBUTING.md` (the family's conventions and release steps), Dependabot for the GitHub Actions.
- The README points to the Guardians bundle and its getting-started guide.
- GitHub Action: `engine` input (`installed` = the scopeGuard the project installed under `.specify/extensions/scopeguard`,
  falling back to the action's own copy, default; `action` = the action's own copy), like the archiGuard and auditGuard actions.
- `tools/e2e-speckit.sh`: the Spec Kit end-to-end check (install from the built archives, rendered skills, configure, the
  example feature through the gate) as a script runnable locally, as in the siblings; CI runs and shellchecks it. It falls
  back to `specify init` without `--non-interactive` for Spec Kit 0.12.17.
- CI runs the tests once more with PyYAML installed (ubuntu, Python 3.13), as archiGuard does: the engine prefers
  PyYAML when importable and the `configure` test checks the rewritten `extensions.yml` with it.
- The preset declares `requires.extensions: scopeguard >=0.4.0`: Spec Kit >=1.1.1 warns after `specify preset add`
  when the extension is missing (the wrapped steps do nothing without it); older Spec Kit versions ignore the key.

## [0.4.0] - 2026-10-06

### Added

- **Configurable story key.** `ids.story_key` (default `US`) and `ids.story_name` (default
  `User Story` for `US`). With `story_key: UC` scopeGuard traces use cases: headings
  `### UC-001 - ...` or `### Use Case 1 - ...`, Scope Coverage rows, task labels `[UC-001]` and
  tasks.md phase titles. `ids.story_pattern` is now derived from the key unless you set it. The
  key cannot also be a requirement prefix.
- **`integration: embedded`.** No hooks and no inline steps: `configure` switches every scopeGuard
  hook off (implement included), the inline steps and hook commands print `skipped`, and the gates
  run only when another tool calls the command line, for example archiGuard's gate runner. `configure`
  warns when the scopeguard-templates preset is installed next to it.

### Changed

- Messages, the inventory and the reports name the configured story kind (for example "2 use cases",
  "traced prefixes: UC, BR") instead of always "user stories".
- The task skeleton for a story without tasks shows the story's own label (for example `[US3]`)
  instead of `[US?]`.

## [0.3.0] - 2026-10-05

### Added

- **Inline integration (new default).** The scopeguard-templates preset wraps `/speckit.plan` and
  `/speckit.tasks` with two mandatory steps: the scope inventory right after Setup, and the scope
  gate (with autocorrect) before the post-execution hooks and the Completion Report. The gate is
  now part of the regular Spec Kit commands, not a separate command.
- One config file, `scopeguard-config.yml`, with new top-level settings:
  - `integration: inline | hooks`
  - `autocorrect.enabled`: `false` means the gate reports the gaps and stops the command.
  - `autocorrect.max_iterations` (default 4).

  Environment overrides: `SCOPEGUARD_INTEGRATION`, `SCOPEGUARD_AUTOCORRECT`,
  `SCOPEGUARD_MAX_ITERATIONS`. `local-config.yml` (Spec Kit convention) is read for personal
  overrides.
- `configure` command (`/speckit.scopeguard.configure` and `scopeguard.sh configure [--dry-run]`).
  It applies the config by switching the scopeGuard hooks on or off in `.specify/extensions.yml`
  (formatting preserved, other extensions untouched), and prints the settings in force.
- `--via inline|hook`: the inline steps and the hook commands check the configured integration at
  run time, and the one that is not configured is skipped. The gate never runs twice, even before
  `configure` is run.
- Fallback: `integration: inline` without the preset (or with the preset disabled) runs through the
  hooks, and `configure` says what to install.

### Changed

- `remediation.max_iterations` is now `autocorrect.max_iterations`. The old key is still read.
- The preset now also provides the two command wraps. Its description changed to match.

## [0.2.0] - 2026-10-05

### Added

- Resolution loop for the plan and tasks gates. The gate commands now resolve what is missing
  instead of only reporting it:
  - **Plan gate:** the agent designs each missing story or requirement into the plan and adds its coverage row.
  - **Tasks gate:** the agent adds `[USn]` phases and tasks, or names the requirement in a task.

  After each resolution the gate re-checks.
- `--iteration N` and `remediation.max_iterations` (default 4). When a gate still fails after
  the last allowed iteration it exits `3` (escalate) and writes `scopeguard-escalation-<gate>.md`
  into the feature directory. For each unresolved item the report holds:
  - its spec text;
  - its iteration history;
  - fields the agent completes: what was attempted, the blocker, and the decision needed from the user.

  The agent then reports back to the user and stops the calling command.
- `RESOLVE` block in the gate output with each open item's text from `spec.md`, and
  `spec_excerpt` in the JSON output.
- Per-gate iteration history in `<feature>/.scopeguard/history-<gate>.json`. A stale
  escalation report is removed once the gate passes.

### Changed

- Extension effect is now `read-write`: the plan and tasks gates edit `plan.md`, `tasks.md` and the plan's design artifacts.

## [0.1.0] - 2026-10-05

### Added

- Deterministic engine (`scripts/python/scopeguard.py`, standard library only) that extracts
  user stories (`US1`, ...) and requirement IDs (`FR-001`, `NFR-001`, optional `SC-001`) from
  `spec.md` and checks them phase by phase.
- Gates: `plan` (every item has a row in plan.md's Scope Coverage table), `tasks` (every
  in-scope item is carried by a task), `implement` (every carrying task is checked off).
  Verdicts: pass / violation / waived. Exit codes 0 / 1 / 2.
- Spec Kit extension `scopeguard` with commands `inventory`, `plan`, `tasks`, `implement`,
  `report`, `compare` and hooks `before_plan`, `after_plan`, `before_tasks`, `after_tasks`
  (mandatory) and `after_implement` (optional).
- Spec Kit preset `scopeguard-templates` that appends a Scope Coverage table to the plan and
  tasks templates.
- `report` (coverage matrix across phases, `--save` into the feature directory) and `compare`
  (two runs of the same spec side by side) for lab measurements.
- Bash and PowerShell launchers that find Python on PATH, the Python bundled with
  `specify-cli`, or fall back to `uv run`.
- GitHub Action (`uses: rlgdev/spec-kit-scopeguard@v0.1.0`) with job-summary output.
- Example Spec Kit workflow with hard scope gates between phases.
