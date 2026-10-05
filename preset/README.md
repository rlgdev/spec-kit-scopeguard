# scopeGuard Templates (preset)

Appends a `## Scope Coverage` section to Spec Kit's `plan-template` and `tasks-template`
(strategy `append`, so the core templates and other presets keep working).

- **plan.md** gets a table with one row per user story and requirement ID from `spec.md`:
  `covered` with a plan reference, or `deferred` with a reason.
- **tasks.md** gets an optional table that maps requirement IDs to task IDs.

The tables are checked by the [scopeGuard extension](https://github.com/rlgdev/spec-kit-scopeguard)
(`after_plan` / `after_tasks` hooks). Install both:

```bash
specify extension add scopeguard --from https://github.com/rlgdev/spec-kit-scopeguard/releases/download/v0.1.0/scopeguard.zip
specify preset add --from https://github.com/rlgdev/spec-kit-scopeguard/releases/download/v0.1.0/scopeguard-preset.zip
```
