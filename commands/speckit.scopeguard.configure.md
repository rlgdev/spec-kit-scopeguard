---
description: "scopeGuard configure: apply scopeguard-config.yml — run the scope gates inline inside /speckit.plan and /speckit.tasks or as hook commands, autocorrect on/off and its iteration limit"
scripts:
  sh: bash scripts/bash/scopeguard.sh configure
  ps: scripts/powershell/scopeguard.ps1 configure
  py: scripts/python/scopeguard.py configure
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Goal

Show and apply the scopeGuard settings from `.specify/extensions/scopeguard/scopeguard-config.yml`:

- `integration: inline`: the scope gate is a mandatory step inside `/speckit.plan` and `/speckit.tasks`, and the separate scopeGuard hooks are switched off. This needs the scopeguard-templates preset.
- `integration: hooks`: the gate runs as separate scopeGuard commands from Spec Kit's hooks.
- `autocorrect.enabled` and `autocorrect.max_iterations`: whether a failing gate fixes the plan or task list itself, and how many fix-and-recheck iterations it gets before escalating.

## Steps

1. If the user input asks to change a setting (for example "use hooks", "6 iterations", "turn autocorrect off"), edit `.specify/extensions/scopeguard/scopeguard-config.yml` first, changing only those keys. If the file does not exist, copy it from `.specify/extensions/scopeguard/config-template.yml`.
2. Run `{SCRIPT}` from the repository root. Add `--dry-run` if the user only wants to see what would change.
3. Show the printed settings and hook table as is. If it prints a `NOTE` (for example the preset needed for `inline` is missing), repeat the note and the install command it gives.
4. If the script exits with code 2, show the error. A bad config value names the key to fix.
