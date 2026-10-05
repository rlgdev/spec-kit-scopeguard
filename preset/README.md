# scopeGuard Templates (preset)

Pairs with the [scopeGuard extension](https://github.com/rlgdev/spec-kit-scopeguard).

- **Wraps `/speckit.plan` and `/speckit.tasks`** (strategy `wrap`) with two mandatory steps: the
  scope inventory right after Setup, and the scope gate before the post-execution hooks and the
  Completion Report. When the gate finds missing items it resolves them (autocorrect), and if it
  cannot it escalates with a problem report. Used when `integration: inline` (the default) is set
  in `scopeguard-config.yml`. With `integration: hooks` the wrapped steps print `skipped` and the
  scopeGuard hook commands do the work.
- **Appends a `## Scope Coverage` section** (strategy `append`) to `plan-template` and
  `tasks-template`:
  - **plan.md** gets one row per user story and requirement ID: `covered` with a plan reference,
    or `deferred` with a reason.
  - **tasks.md** gets an optional table that maps requirement IDs to task IDs.

Install both, then apply the config:

```bash
specify extension add scopeguard --from https://github.com/rlgdev/spec-kit-scopeguard/releases/download/v0.3.0/scopeguard.zip
specify preset add --from https://github.com/rlgdev/spec-kit-scopeguard/releases/download/v0.3.0/scopeguard-preset.zip
bash .specify/extensions/scopeguard/scripts/bash/scopeguard.sh configure
```
