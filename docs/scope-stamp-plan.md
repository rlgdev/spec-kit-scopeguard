# The scope stamp: implementation plan

> Status: proposal, 2026-10-29. Target: scopeGuard 0.5.0, archiGuard 0.1.2, Guardians 0.1.3.
> This document is the plan; it is not yet implemented. Delete it (or move it to the CHANGELOG) once it is.

## 1. The idea, in one paragraph

The scope of a feature is **stamped** at the moment the specification is handed over to Spec Kit: the IDs
`spec.md` defines (user stories, requirements) and the hash of the file are written down once. The plan gate
and the tasks gate then **review** the plan and the tasks against the stamp, not against whatever `spec.md`
happens to say at that moment. When the tasks gate passes, the tasks that carry every in-scope item are
**sealed** into the stamp. From then on the implement gate is responsible: it checks the sealed carriers, not
the spec. A change of the stamp after planning is a decision of a person, with a reason, never a repair of the
agent.

## 2. What the project does today, and the gap

### 2.1 What exists

| Moment | scopeGuard (standalone, `integration: inline`) | Guardians default (scopeGuard embedded, archiGuard runs the scope gate) |
|--------|-----------------------------------------------|---------------------------------------------------------------------------|
| hand-over of the spec | `inventory` in step A of `/speckit.plan` prints the IDs and the scope contract. Nothing is written. | the same `inventory`, as the `scope` gate in `pipeline.speckit.plan.step_a`. archiGuard additionally needs `handover.yml` (written by the BA tool: `source.sha256` of the spec, the BA `scope` list) and its edit guard makes `spec.md` read-only for the agent once that file exists. |
| after plan | plan gate: every ID of **the current `spec.md`** has a `covered` or `deferred` row. | the same, inside archiGuard's step B budget. |
| after tasks | tasks gate: every in-scope ID of **the current `spec.md`** is carried by a task. | the same. |
| after implement | implement gate (optional `after_implement` hook): every carrying task in **the current `tasks.md`** is checked off, for every ID of **the current `spec.md`**. | the same, in `pipeline.speckit.implement.step_b`; plus archiGuard's A4.1 compares the hash of `spec.md` with `handover.yml` at the start of implement. |

Every gate re-reads `spec.md` as it is now. The only thing that says "never drop an ID from spec.md" is prose in
the command files (`inventory`, the plan and tasks wraps) and the README. Nothing checks it.

### 2.2 The gap, reproduced on the shipped example

`examples/missing-story` has a plan that dropped US3. The plan gate fails, as documented. Now do what the
command text forbids: delete the `### User Story 3` section and the `FR-004` line from `spec.md`.

```text
$ scopeguard plan --feature-dir specs/001-team-board
RESULT: PASS | 0 violation(s), 8 pass, 1 waived, 0 warning(s) | coverage 8/8 in-scope items (100.0%)
$ scopeguard check --feature-dir specs/001-team-board --json   ->  "verdict": "pass"
```

Every gate passes with 100 % coverage. The story is gone from the plan, the tasks, the implementation, and
from the record. In the Guardians setup the same edit is blocked for the **agent** by archiGuard's edit guard,
but only once `handover.yml` exists, and a hash difference is noticed by A4.1 only at the start of
`/speckit.implement`, as a hash, without saying which items changed. Between `/speckit.specify` and
`/speckit.implement` nobody checks.

### 2.3 Can it be configured today?

No. There is no setting, hook or command in scopeGuard that records the scope, and the gates have no input
other than the live `spec.md`. archiGuard's `handover.yml` is the closest thing (it pins the spec hash and the BA
scope list), but scopeGuard does not read it, it exists only in the Guardians setup with a BA hand-over, and it
is checked at implement time only. The idea needs new behaviour in scopeGuard and a small adapter change in
archiGuard.

## 3. Design

Four decisions keep this small. Everything else follows from them.

| # | Decision | Why |
|---|----------|-----|
| D1 | **One file per feature**, `specs/<feature>/scopeguard-stamp.json`, committed. Written only by scopeGuard. | It sits next to `scopeguard-report.md` and `scopeguard-escalation-*.md`. auditGuard's golden check already reports a commit that touches it outside a recorded command (`specs/**` is explained, only `scopeguard-*.md` and `.scopeguard/` are excluded); one entry in its artefact list (WP4) makes a re-stamp a hashed, per-command `artefact.changed` event with its author. |
| D2 | **Stamped at first use.** `inventory` writes the stamp when there is none. Every integration already runs `inventory` as step A of `/speckit.plan` (the inline preset, the `before_plan` hook, archiGuard's pipeline). A `stamp` command exists for people. No new Spec Kit hook. | The hand-over moment in Spec Kit is the first `/speckit.plan`; `/speckit.clarify` before it changes the spec by design and needs no ceremony. An `after_specify` hook would need a re-stamp after every clarify and a second command in every integration; it buys nothing the first inventory does not. |
| D3 | **Drift is not repairable by the agent.** A stamped ID missing from `spec.md`, or an ID that appeared after the stamp, is a violation that escalates at once (exit `3`, problem report) instead of entering the resolve loop. The decision is a person's: re-stamp with a reason, or restore `spec.md`. | The agent must never edit `spec.md`; a loop that asks it to "resolve" a spec change would ask exactly that. archiGuard has the same notion (`repairable: false`). |
| D4 | **The tasks gate seals the carriers on pass.** It writes `tasks.carriers` (ID to task IDs) into the stamp. The implement gate checks the sealed carriers (they must still exist and be done) plus whatever carries the item now. | "When tasks are stamped according to the scope, the implementation scope is responsible for further checks." The implement gate gets a committed contract instead of whatever `tasks.md` says now, and a carrier removed from `tasks.md` is caught (today it is not, as long as one other carrier is done). |

Two config keys, no more:

```yaml
stamp:
  enabled: true            # false = 0.4 behaviour: nothing is stamped, the gates read spec.md as it is now
  added_ids: violation     # an ID spec.md defines that the stamp does not have: violation | warning
```

Not configurable on purpose: the file name, the "missing stamp is a warning" rule (upgrade path for features
planned before 0.5), the "removed ID is a violation" rule.

### 3.1 The stamp file

```json
{
  "tool": "scopeguard", "version": "0.5.0", "format": 1,
  "feature_dir": "specs/001-team-board",
  "stamped_at": "2026-10-29 10:12:03",
  "stamped_by": "inventory",
  "spec": { "sha256": "9f3c…", "story_key": "US", "requirement_prefixes": ["FR", "NFR"] },
  "items": [
    { "id": "US1", "kind": "story", "title": "Create a board and add cards", "priority": "P1" },
    { "id": "FR-001", "kind": "requirement", "title": "System MUST let a user create a board…" }
  ],
  "tasks": null,
  "history": [
    { "at": "2026-10-29 10:12:03", "action": "stamp", "by": "inventory", "spec_sha256": "9f3c…",
      "added": ["US1", "US2", "US3", "US4", "FR-001", "…"], "removed": [], "reason": null }
  ]
}
```

After the tasks gate passes, `tasks` becomes:

```json
  "tasks": {
    "sealed_at": "2026-10-29 11:40:10",
    "carriers": { "US1": ["T003", "T004"], "FR-001": ["T003"], "US3": ["T012", "T013"] },
    "waived": { "FR-007": "deferred in plan: PO decision 2026-10-05: phase 2" }
  }
```

and `history` gets an `{ "action": "seal", … }` entry. A re-stamp gets `{ "action": "restamp", "reason": "…",
"added": [...], "removed": [...] }`. The file is JSON (the engine writes JSON already; YAML is read-only for
the config), LF, UTF-8, sorted keys, so two runs on the same input produce the same bytes.

### 3.2 The `stamp` command

`scopeguard stamp [--feature-dir DIR] [--reason TEXT] [--json]`, and `/speckit.scopeguard.stamp` for the agent.

| State | Result |
|-------|--------|
| no stamp | written; exit `0`; prints the counts and the hash |
| stamp exists, `spec.md` unchanged (same hash) | `scope stamp is current`; exit `0`; nothing written |
| stamp exists, spec changed, **no `plan.md` yet** | updated (action `restamp`, reason `before planning`); exit `0`; prints added / removed / retitled |
| stamp exists, spec changed, `plan.md` exists, `--reason` given | updated with the reason; exit `0`; prints the diff and `re-run the plan and tasks gates` |
| the same without `--reason` | exit `1`; prints the diff and `a scope change after planning needs a reason: stamp --reason "..."` |
| config changed what is traced (story key, prefixes differ from the stamp) | treated as a spec change (the diff shows what the new config adds or drops) |

The agent command file says, in the same tone as the existing ones: run it only when the user asked for the
re-stamp in this conversation, pass the user's reason verbatim, never invent one, show the diff, then re-run
the gates. It is a human decision that an agent executes on request, like `configure`.

### 3.3 What the gates do with the stamp

Common to `plan`, `tasks` and `implement`, when `stamp.enabled` and the file exists (`check_stamp()`):

- **Removed ID** (in the stamp, not in `spec.md`): one `ItemResult` per ID, verdict `violation`, code
  `unstamped-drop`, built from the stamp's record (so the report shows the title):
  `[FAIL] US3  Share a board with teammates (P2) -> dropped from spec.md after the scope stamp of 2026-10-29; not a planning fix`.
  The `unknown_ids` finding is **not** raised for such an ID when the plan or tasks still carry it (it is the
  drop that is reported, once).
- **Added ID** (in `spec.md`, not in the stamp): a finding at the level of `stamp.added_ids`:
  `spec.md defines FR-010, which is not in the scope stamp (scope grew after the hand-over)`.
- **Hash differs, same IDs and titles**: warning `spec.md text changed after the scope stamp (IDs unchanged)`.
- **Retitled ID**: warning naming the old and new title.
- **No stamp**: warning `no scope stamp yet (run inventory or stamp); the gates read spec.md as it is now`.
  CI (`check --all`) never writes a stamp.

Drift violations set `GateResult.unrepairable = True`. In `apply_iteration` (the resolve loop) an unrepairable
result escalates at `iteration` 0, regardless of `max_iterations` and of `autocorrect`. The escalation report
gets a section **Scope changed after the stamp** listing removed and added IDs and the two possible
decisions (approve the change: `stamp --reason`, then re-run the gate; or restore `spec.md` from git and
re-run), with no `TODO(agent)` for these items. In JSON every drift item and finding carries
`"repairable": false` and the gate carries `"unrepairable": true`; archiGuard reads that (§4).

Per gate:

- **plan**: the checks above, then the existing coverage check over the **union** of stamped and live IDs
  (a dropped ID still needs its row, so the plan is not "repaired" by the drop either).
- **tasks**: the same; on `pass` (verdict pass, `mode: enforce`, not `--report-only`) it seals: writes
  `tasks.carriers` (every in-scope ID to its carrier task IDs, from `carriers()` plus the Scope Coverage table
  of tasks.md) and `tasks.waived`. Idempotent: identical content is not rewritten. It seals under archiGuard
  too (archiGuard calls `scopeguard tasks --json` on every iteration; the last, passing one seals).
- **implement**: items = stamped IDs (plus live IDs not in the stamp, reported as above). Carriers = sealed
  carriers ∪ live carriers. A sealed carrier that is not in `tasks.md` any more is a violation
  (`T012 was sealed as carrying US3 and is no longer in tasks.md`, code `carrier-removed`). Open carriers are
  reported as today. Without a seal the gate behaves as in 0.4 and warns once
  `tasks were never sealed (the tasks gate did not pass with a stamp); checking tasks.md as it is now`.
- **inventory**: prints a `SCOPE STAMP` block (`stamped 2026-10-29 10:12 (sha256 9f3c…), 4 user stories,
  7 requirements`, or `scope stamped now`), and one more contract line:
  `spec.md is the stamped scope of this feature: a change needs the user's re-stamp (stamp --reason), never an edit by the agent`.
  When the stamp and the spec already differ, inventory prints the diff and says the gate will escalate.
- **report**: the header names the stamp (date, hash, `sealed` or not) and the drift, if any.

### 3.4 What is deliberately not in the design

- No new Spec Kit hook (`after_specify`, `after_clarify`): see D2.
- No lock on `spec.md` itself: archiGuard's edit guard does that in the Guardians setup; standalone scopeGuard
  stays a checker. The stamp makes an edit visible and blocking; it does not prevent it.
- No stamp of `plan.md` or of the plan's deferrals: a deferral is already visible in the Scope Coverage table and
  recorded by auditGuard as a waiver.
- No reading of archiGuard's `handover.yml` by scopeGuard (coupling in the wrong direction). A cross-check
  "stamp ⊇ handover scope" is a possible archiGuard follow-up, listed in §4.
- No per-ID allow-list, no expiry, no signatures. Git history, CODEOWNERS and auditGuard cover who changed the
  file and when.

## 4. Work packages

### WP1: scopeGuard 0.5.0 (engine, commands, preset, docs, tests)

All in `rlgdev/spec-kit-scopeguard`. Estimated size: ~400 lines engine, ~300 lines tests, docs.

**Engine, `scripts/python/scopeguard.py`**

1. `DEFAULT_CONFIG["stamp"] = {"enabled": True, "added_ids": "violation"}`; `load_config` validates the
   section (unknown key is exit `2`, as elsewhere; `added_ids` must be `violation` or `warning`;
   `enabled` through `_as_bool`). `STAMP_FILENAME = "scopeguard-stamp.json"`.
2. `@dataclass Stamp` (items as `ScopeItem`-like records, spec hash, scheme, tasks seal, history) with
   `load_stamp(feature_dir) -> Optional[Stamp]` (a corrupt or foreign-format file is exit `2` naming the file)
   and `write_stamp(stamp, feature_dir)` (sorted keys, LF, `format: 1`).
3. `spec_fingerprint(spec_path) -> str` (sha256 of the bytes, as archiGuard does, so both tools agree on the
   hash of the same file).
4. `make_stamp(feature_dir, spec, scheme, config, by, reason)` and `diff_stamp(stamp, spec) -> StampDiff`
   (`added`, `removed`, `retitled`, `hash_changed`, `scheme_changed`).
5. `check_stamp(result: GateResult, stamp, config)`: adds the items and findings of §3.3, sets
   `result.unrepairable`, returns the union of IDs the gate must cover.
6. `GateResult`: new fields `unrepairable: bool = False`, `stamp: Optional[Stamp]`; `ItemResult` and
   `Finding` get `repairable: bool = True`; `to_dict` / `gate_to_dict` print them (`"repairable": false`
   only when false, so existing JSON consumers see no change otherwise; `"unrepairable"` always).
7. `gate_plan`, `gate_tasks`, `gate_implement`: call `check_stamp` first; iterate over the union of IDs;
   suppress the `unknown_ids` finding for a stamped-but-dropped ID. `gate_tasks` returns the carrier map; the
   `run()` loop seals after a passing tasks gate (`seal_tasks(stamp, result)`), never in report mode.
   `gate_implement` merges sealed carriers and raises `carrier-removed`.
8. `apply_iteration`: `if result.unrepairable and result.verdict == "fail": escalate now` (before the
   `iteration >= max_iterations` test); `render_escalation`: the new section; history entry notes
   `"unrepairable": true`.
9. `inventory` / `render_inventory_text`: stamp when absent (not with `--json`? no: `--json` stamps too,
   archiGuard calls it in text mode anyway; only `--report-only` and `stamp.enabled: false` never write),
   print the block and the contract line, print the diff when the spec moved.
10. `cmd_stamp` with the state table of §3.2; `--reason` on the `stamp` subparser only. `--json` output:
    `{"command": "stamp", "verdict": "written|current|refused", "diff": {...}, "stamp": {...}}`.
11. `phase_matrix` / `render_report_markdown`: the stamp line in the header.
12. `__version__ = "0.5.0"`.

**Commands and preset**

13. `commands/speckit.scopeguard.stamp.md` (new; `scripts:` block like the siblings; the rules of §3.2).
14. `commands/speckit.scopeguard.inventory.md`: step 4 gets the stamp line of the contract; a sentence on what to
    do when inventory reports a diff (tell the user, do not plan, do not touch spec.md).
15. `commands/speckit.scopeguard.plan.md`, `commands/speckit.scopeguard.tasks.md`,
    `preset/commands/speckit.plan.md`, `preset/commands/speckit.tasks.md`: in the exit-`3` branch, a bullet for
    the stamp case: the output says `SCOPE CHANGED AFTER THE STAMP`; report the removed and added IDs and the two
    decisions; do not edit `spec.md`; do not re-stamp; the command ends.
16. `commands/speckit.scopeguard.implement.md`: name the sealed carriers; a removed carrier is a finding to report,
    not a checkbox to tick.
17. `extension.yml`: the new command (8 commands); description mentions the stamp. `catalog/extensions.json`:
    `provides.commands: 8`, version. `preset/preset.yml`, `workflows/scopeguard-sdd/workflow.yml`: version;
    the workflow gets a `scope-stamp` shell step (`{{ inputs.scopeguard }} stamp`) right after `review-spec`,
    which is the hand-over moment of the workflow.
18. `config-template.yml`: the `stamp:` section with comments (D1 to D4 in two sentences each).

**Docs**

19. README: a row for the stamp in the "How it works" table (`/speckit.plan` step A: *stamps the scope on first
    run*), a section **The scope stamp** after "Resolve, re-check, escalate" (what is stamped, when, the file,
    drift and the escalation, re-stamping, the seal, upgrade note: features planned before 0.5 get a warning
    until their first inventory), the `stamp` row in the command table, the two config keys, the "What
    scopeGuard does and does not prove" list (it now proves that the scope a feature was planned against is
    the scope it was handed over with, or that someone wrote down why not).
20. `CHANGELOG.md` under `[Unreleased]`, then `## [0.5.0]`.
21. `examples/scope-drift/`: the team-board spec with US3 and FR-004 deleted after the stamp, the stamp file,
    and `sample-output/escalation-report-plan.md`; `examples/README.md` entry.

**Tests, `tests/test_scopeguard.py`**

22. `test_inventory_stamps_on_first_run_and_is_idempotent` (same bytes twice).
23. `test_stamp_updates_freely_before_plan`, `test_stamp_refuses_change_after_plan_without_reason` (exit 1, diff
    printed), `test_stamp_with_reason_records_history`.
24. `test_plan_gate_escalates_at_once_when_stamped_id_dropped_from_spec` (the §2.2 reproduction: now exit `3` at
    iteration 0, report lists US3 and FR-004 under "Scope changed after the stamp", no `TODO(agent)`).
25. `test_added_id_after_stamp_is_violation_by_default_and_warning_when_configured`.
26. `test_hash_only_change_is_a_warning`, `test_retitled_id_is_a_warning`.
27. `test_missing_stamp_is_a_warning_and_check_all_never_writes_one`.
28. `test_tasks_gate_seals_carriers_on_pass_and_not_in_report_mode`.
29. `test_implement_gate_flags_removed_sealed_carrier` and `test_implement_without_seal_behaves_as_0_4`.
30. `test_stamp_disabled_restores_0_4_behaviour`, `test_stamp_config_validation` (unknown key, bad `added_ids`).
31. `test_json_marks_drift_unrepairable` (the contract archiGuard's adapter relies on).
32. `test_scheme_change_counts_as_spec_change`.
33. `test_example_scope_drift_reproduces`.
34. `test_preset_wraps_core_commands_with_inline_steps`: the wraps mention `SCOPE CHANGED AFTER THE STAMP`.

**e2e, `tools/e2e-speckit.sh`**: after the inline `inventory`, assert the stamp file exists; drop US3 from the
spec; `plan --via inline --iteration 0` exits `3` and the report names US3.

**Release**: 0.5.0 per CONTRIBUTING (version in five files, CHANGELOG, README URLs, tag).

### WP2: archiGuard 0.1.2 (adapter, manifest, default pipeline, edit guard)

All in `rlgdev/spec-kit-archiguard`. Estimated size: ~80 lines plus docs. Depends on WP1 being released
(CI pins `SCOPEGUARD_TAG`).

1. `gates.scope.version` default `">=0.3.0,<0.6"` in `archiguard_core/config.py`, `config-template.yml`, README,
   `docs/configuration.md`, `docs/plugin-contract.md` (the adapter paragraph: 0.5 adds the stamp).
2. `gates/plugged.py`, `run_scopeguard`: a `stamp` check runs like `inventory` (text into `res.info`; exit `1`
   becomes one **non-repairable blocking** finding with the printed diff; exit `2` an error). For `plan`,
   `tasks`, `implement`: an item or finding with `"repairable": false`, or a gate with `"unrepairable": true`,
   sets `res.repairable = False`, so the runner escalates with "a check no agent may repair is red" instead of
   spending the budget. Findings keep scopeGuard's wording.
3. `manifests/scope.yml`: `stamp: { name: scope stamp, target: spec, repairable: false, checker: false }`.
4. Default pipeline (`config.py` defaults, `config-template.yml`, README table, `examples/orders` config):
   `speckit.plan.step_a` gets `{ gate: scope, run: [stamp, inventory] }` in place of `[inventory]`. `stamp` is
   explicit so that a spec that moved since the stamp stops the command **before** the agent plans against it;
   `inventory` would stamp anyway for a custom pipeline that lists only it.
5. `edit_guard.always_readonly` default gains `"specs/*/scopeguard-stamp.json"` (the agent may not re-stamp or
   delete the stamp; `scopeguard stamp` is for people, like `signoff`). Documented in README and
   `docs/configuration.md`.
6. `scope-config-template.yml`: the two `stamp:` keys, commented, with the default.
7. Tests: `test_plugged_scopeguard_unrepairable` (a fixture JSON with `repairable: false` makes the check
   non-repairable), the SCOPEGUARD_SRC integration test: step A with `stamp` on a moved spec escalates (exit `3`)
   and names the removed ID; step B `plan` on a dropped ID escalates at iteration 0 without consuming the budget.
   `tools/e2e-speckit.sh`: the stamp file appears after step A.
8. CI: `SCOPEGUARD_TAG: v0.5.0`. CHANGELOG, release 0.1.2.

Follow-up (not in 0.1.2): when `handover.yml` lists `scope`, step A could check that every BA scope ID is in the
stamp (the BA hand-over and the Spec Kit stamp agree). One function, one finding; decide after 0.1.2 is in use.

### WP3: Guardians 0.1.3 (pins, constants, verify, docs)

All in `rlgdev/spec-kit-guardians`. Estimated size: ~80 lines plus docs. Depends on WP1 and WP2 releases.

1. Pins: `bundle/bundle.yml`, `catalog/*.json`, `action.yml`, CI refs to scopeGuard 0.5.0 and archiGuard 0.1.2
   (and whatever auditGuard version is current; `tools/check-family.py` fails while they disagree).
2. `guardians_core/siblings.py`: `ARCHIGUARD_SCOPE_RANGE = ">=0.3.0,<0.6"`, `ARCHIGUARD_READONLY` gains
   `specs/*/scopeguard-stamp.json`; `tests/fixtures/*-config.yml` refreshed from the new templates at the tags.
3. `verify`, one new check `scope_stamp: warn` (config-template `checks:`, README table, the twelve becomes
   thirteen): `[OK]` when archiGuard's `scope-config.yml` does not set `stamp.enabled: false` and its plan step A
   lists `stamp` or `inventory`; `[WARN]` otherwise, with the file and key in the `fix:` line; `[--]` when the
   scope gate is not in the pipeline. `configure` writes nothing new: the family default comes from the two
   siblings' own defaults.
4. `docs/getting-started.md`: §4 "Day to day" gets two sentences (the stamp is taken at the first `/speckit.plan`;
   a spec change after that stops the command and a person re-stamps with `scopeguard stamp --reason`); §6
   "What was written where" gets the row `specs/<feature>/scopeguard-stamp.json | scopeGuard, at the first
   inventory; the tasks gate seals it | yes (evidence)`; §7 gets the symptom `SCOPE CHANGED AFTER THE STAMP`
   with the fix; the smoke test in §4 asserts the stamp file. README: the scopeGuard row of the family table
   ("…is dropped, and the scope a feature is planned against is the one it was handed over with").
5. `docs/specification.md`: amendment row A12 (the stamp as part of the family default; `scope_stamp` check).
6. Tests: `test_verify.py` for the new check (three outcomes); `tools/check-family.py` passes against the three
   checkouts at their tags. `tools/e2e-speckit.sh`: after `run plan a`, the stamp exists.
7. CHANGELOG, release 0.1.3.

### WP4: auditGuard 0.2.x (one default, one sentence)

The collector range `scopeguard: ">=0.4,<0.6"` accepts 0.5 as it is. Two small things, in the next auditGuard
release (no new Guardians pin needed for them; the stamp works without them):

1. `collectors.git.artefacts` default (`auditguard_core/config.py`, `config-template.yml`, `docs/configuration.md`)
   gains `scopeguard-stamp.json`, so every command records the stamp's hash and a re-stamp outside a command
   becomes `artefact.changed` with its author. Until then the golden check G3 (`unexplained_commit`) already
   reports a commit that touches the file outside a recorded command, because `explain_paths` covers `specs/**`
   and the exclusions name only `scopeguard-*.md` and `.scopeguard/`. Do **not** add the stamp to
   `exclude_paths`.
2. README, "Changes outside commands" row: name the stamp as an example. One test: the artefact list includes
   it and a changed stamp between two hooks produces `artefact.changed`.

## 5. Order, and how to verify the whole

1. WP1 on a branch of scopeGuard; green CI (tests on three OSes, PyYAML variant, lint, e2e, the action self-test);
   release `v0.5.0`.
2. WP2 on a branch of archiGuard with `SCOPEGUARD_TAG: v0.5.0`; the integration test and the e2e install
   `scopeguard.zip` of that tag; release `v0.1.2`.
3. WP3 on a branch of Guardians; `tools/check-family.py` against the three checkouts at the tags; the e2e
   installs the bundle from the release assets; release `v0.1.3`.
4. The acceptance run, on a fresh Spec Kit project with the bundle (the getting-started smoke test, extended):

```bash
bash .specify/scripts/bash/create-new-feature.sh --json --short-name demo "Demo feature"
#   write specs/001-demo/spec.md with two user stories and two requirements
bash .specify/extensions/archiguard/scripts/bash/archiguard.sh run plan a      # step A: stamps; specs/001-demo/scopeguard-stamp.json exists
#   delete "### User Story 2" from spec.md
bash .specify/extensions/archiguard/scripts/bash/archiguard.sh run plan a      # exit 3: SCOPE CHANGED AFTER THE STAMP, US2 removed; escalation note written
bash .specify/extensions/scopeguard/scripts/bash/scopeguard.sh stamp           # exit 1: needs --reason (plan.md exists)
bash .specify/extensions/scopeguard/scripts/bash/scopeguard.sh stamp --reason "PO dropped US2 on 2026-10-29"   # exit 0, history records it
bash .specify/extensions/auditguard/scripts/bash/auditguard.sh show --all      # the re-stamp is an artefact.changed with the author
bash .specify/extensions/guardians/scripts/bash/guardians.sh verify            # RESULT: OK, [OK] scope_stamp
```

## 6. Risks and open points

- **Agents that "fix" the stamp.** Standalone scopeGuard cannot stop a file edit; the command text forbids it and
  the file is committed, so the diff shows it. In the Guardians setup archiGuard's edit guard blocks the agent
  (WP2 item 5). If that is not enough for a team, CODEOWNERS on `specs/*/scopeguard-stamp.json` is the usual
  answer; the getting-started guide already recommends CODEOWNERS for the other evidence files.
- **Features in flight at upgrade time.** They have no stamp; the next inventory takes one from the spec as it is
  then. The gates warn until that happens. No migration step.
- **`/speckit.clarify` after planning.** Clarify edits the spec; with a plan in place that is drift and the next
  gate escalates. That is the intended behaviour (a clarification that changes scope after planning is a scope
  change); the escalation report says to re-stamp with the clarification as the reason. If this turns out to be
  too strict in practice, the option is `stamp.added_ids: warning` for additions; removals stay violations.
- **Sealing in report mode.** Never; report mode measures and writes nothing but history. Documented.
- **Two stamps in the Guardians setup** (`handover.yml` from the BA tool, `scopeguard-stamp.json` from
  scopeGuard). They answer different questions (the BA released this spec version; Spec Kit planned against
  these IDs) and the follow-up in WP2 ties them together when wanted.
