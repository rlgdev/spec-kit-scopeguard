# Changelog

All notable changes to scopeGuard are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

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
