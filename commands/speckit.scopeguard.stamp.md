---
description: "scopeGuard stamp: record the scope of spec.md (its user story and requirement IDs and the file's hash) as the scope this feature is planned against; re-stamp a changed spec only with the user's reason"
scripts:
  sh: bash scripts/bash/scopeguard.sh stamp
  ps: scripts/powershell/scopeguard.ps1 stamp
  py: scripts/python/scopeguard.py stamp
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Goal

The scope stamp (`scopeguard-stamp.json` in the feature directory) is the scope the feature was handed over with: every ID `spec.md` defines and the hash of the file. It is normally taken by the scope inventory at the start of `/speckit.plan`; this command takes it earlier, by hand, or **re-stamps after a scope change that the user approved**. The plan, tasks and implement gates compare `spec.md` with the stamp and escalate when an ID was removed or added after it.

**A re-stamp after planning is a decision of the user, not of the agent.** Run this command with `--reason` only when the user asked for the re-stamp in this conversation; pass their reason in their words. Never invent a reason, never re-stamp to make a gate pass, and never edit `spec.md` or the stamp file yourself.

## Steps

1. Run `{SCRIPT}` from the repository root. If the user input names a feature directory, append `--feature-dir <dir>`. If the user approved a scope change and gave a reason, append `--reason "<their reason>"`.
2. **Exit 0.** Show the printed result: `stamped now` (first stamp), `scope stamp is current` (nothing changed), or `re-stamped` with the list of removed, added and retitled IDs. After a re-stamp, tell the user the plan and tasks gates must run again (`/speckit.scopeguard.plan`, `/speckit.scopeguard.tasks`, or the gates inside `/speckit.plan` and `/speckit.tasks`), because the plan and the tasks are now checked against the new scope.
3. **Exit 1 — refused.** `spec.md` changed after planning and no reason was given. Show the printed diff (`- ID` removed, `+ ID` added, `~ ID` retitled) and ask the user to decide: approve the change with a reason (then run this command again with `--reason`), or restore `spec.md` from git. Do not choose for them.
4. **Exit 2.** Show the error and the fix (for example `--feature-dir specs/<feature>`, or `stamp.enabled: false` in the config).
