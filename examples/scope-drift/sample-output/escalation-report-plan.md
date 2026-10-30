# scopeGuard escalation: plan gate

- **Feature**: `specs/001-team-board`
- **Result**: the scope changed after the stamp of 2026-10-30 08:20:43: 2 stamped item(s) removed from spec.md, 0 item(s) added (2026-10-30 08:20)
- **Still open**: 0 scope item(s), 0 other violation(s)
- **Artifact being resolved**: `plan.md`

The plan gate found that `spec.md` no longer matches the scope stamp (`scopeguard-stamp.json`). This is a scope change, not a gap in `plan.md`: the agent does not resolve it and must not edit `spec.md` or the stamp. Decide below, then run the gate again.

## Iteration history

| Iteration | Violations | Open items |
|---|---|---|
| 0 | 2 | US3, FR-004 |

## Scope changed after the stamp

- **Stamp**: `scopeguard-stamp.json`, taken 2026-10-30 08:20:43 by stamp, spec.md sha256 `fe06b1d0a1a4...`
- **US3 removed from spec.md**: Share a board with teammates (P2)
- **FR-004 removed from spec.md**: System MUST let the board owner invite teammates by e-mail and revoke access.

**Decision needed (a person, not the agent):**

1. The change is intended: approve it with `scopeguard stamp --reason "<why the scope changed>"` (`/speckit.scopeguard.stamp`), then run the gate again; the plan and the tasks are re-checked against the new scope.
2. The change is not intended: restore `spec.md` from git, then run the gate again.
