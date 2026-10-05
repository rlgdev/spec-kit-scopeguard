# Changelog

All notable changes to scopeGuard are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

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
