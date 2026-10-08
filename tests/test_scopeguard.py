"""Tests for the scopeGuard engine (scripts/python/scopeguard.py)."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
ENGINE = REPO / "scripts" / "python" / "scopeguard.py"
EXAMPLE = REPO / "examples" / "missing-story" / "specs" / "001-team-board"

spec_obj = importlib.util.spec_from_file_location("scopeguard", ENGINE)
sg = importlib.util.module_from_spec(spec_obj)
assert spec_obj.loader is not None
sys.modules["scopeguard"] = sg
spec_obj.loader.exec_module(sg)


SPEC = """# Feature Specification: Demo

## User Scenarios & Testing *(mandatory)*

<!-- ### User Story 9 - template example inside a comment must be ignored -->

### User Story 1 - Browse catalog (Priority: P1)

Text.

### User Story 2 - Add to basket (Priority: P2)

Text.

### User Story 3 – Pay with card (Priority: P3)

Text.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST list products.
- **FR-002**: System MUST keep a basket per session.
- **FR-003**: System MUST accept card payments.

### Non-Functional Requirements

- **NFR-001**: Pages MUST render in under 1 s.

## Success Criteria *(mandatory)*

- **SC-001**: 90% of users finish checkout.
"""

PLAN_HEAD = """# Implementation Plan: Demo

## Summary

Stuff.

## Scope Coverage

| ID | Title | Status | Plan reference | Reason (required if deferred) |
|----|-------|--------|----------------|-------------------------------|
"""

FULL_ROWS = [
    "| US1 | Browse | covered | contracts/catalog.yaml | |",
    "| US2 | Basket | covered | data-model.md Basket | |",
    "| US3 | Pay | covered | contracts/payments.yaml | |",
    "| FR-001 | list | covered | contracts/catalog.yaml | |",
    "| FR-002 | basket | covered | data-model.md | |",
    "| FR-003 | pay | covered | contracts/payments.yaml | |",
    "| NFR-001 | perf | covered | research.md caching | |",
]

TASKS = """# Tasks: Demo

## Phase 1: Setup

- [x] T001 Create project structure

## Phase 3: User Story 1 - Browse catalog (Priority: P1)

- [x] T002 [P] [US1] Product list endpoint (FR-001)
- [x] T003 [US1] Catalog page, renders under 1 s (NFR-001)

## Phase 4: User Story 2 - Add to basket (Priority: P2)

- [ ] T004 [US2] Basket service (FR-002)
- [x] T005 Basket widget

## Phase 5: User Story 3 - Pay with card (Priority: P3)

- [ ] T006 [US3] Card payment flow (FR-003)
"""


def make_feature(root: Path, spec: str = SPEC, plan: str | None = None, tasks: str | None = None, name: str = "001-demo") -> Path:
    (root / ".specify").mkdir(parents=True, exist_ok=True)
    fd = root / "specs" / name
    fd.mkdir(parents=True, exist_ok=True)
    (fd / "spec.md").write_text(spec, encoding="utf-8")
    if plan is not None:
        (fd / "plan.md").write_text(plan, encoding="utf-8")
    if tasks is not None:
        (fd / "tasks.md").write_text(tasks, encoding="utf-8")
    return fd


def plan_with(rows) -> str:
    return PLAN_HEAD + "\n".join(rows) + "\n"


def run_cli(root: Path, *args: str, env: dict | None = None):
    full_env = dict(os.environ)
    full_env.pop("SPECIFY_FEATURE_DIRECTORY", None)
    full_env.pop("SPECIFY_FEATURE", None)
    full_env.pop("SCOPEGUARD_MODE", None)
    if env:
        full_env.update(env)
    proc = subprocess.run(
        [sys.executable, str(ENGINE), *args], cwd=str(root), capture_output=True, text=True, env=full_env, encoding="utf-8"
    )
    return proc


def gate(root: Path, name: str, *extra: str):
    proc = run_cli(root, name, "--json", "--feature-dir", "specs/001-demo", *extra)
    assert proc.returncode in (0, 1, 2, 3), proc.stderr
    data = json.loads(proc.stdout)
    return proc.returncode, data


def items(data, gate_index: int = 0):
    return {i["id"]: i for i in data["gates"][gate_index]["items"]}


# --------------------------------------------------------------------------- spec


def test_spec_inventory_parses_stories_requirements_and_ignores_comments(tmp_path):
    fd = make_feature(tmp_path)
    config, _ = sg.load_config(tmp_path, None)
    model = sg.parse_spec(fd / "spec.md", sg.IdScheme(config), config)
    assert [i.display for i in model.stories] == ["US1", "US2", "US3"]
    assert [i.display for i in model.requirements] == ["FR-001", "FR-002", "FR-003", "NFR-001"]
    us3 = model.items["US3"]
    assert us3.title == "Pay with card" and us3.priority == "P3"
    assert "SC-1" not in model.items  # SC is not traced by default


def test_success_criteria_can_be_traced(tmp_path):
    fd = make_feature(tmp_path)
    cfg_path = tmp_path / "cfg.yml"
    cfg_path.write_text("ids:\n  requirement_prefixes: [FR, NFR, SC]\n", encoding="utf-8")
    config, _ = sg.load_config(tmp_path, str(cfg_path))
    model = sg.parse_spec(fd / "spec.md", sg.IdScheme(config), config)
    assert "SC-1" in model.items


def test_duplicate_ids_in_spec_are_violations(tmp_path):
    spec = SPEC + "\n### User Story 2 - Duplicate\n\n- **FR-001**: again\n"
    make_feature(tmp_path, spec=spec, plan=plan_with(FULL_ROWS))
    code, data = gate(tmp_path, "plan")
    assert code == 1
    messages = " ".join(f["message"] for f in data["gates"][0]["findings"])
    assert "US2 is defined twice" in messages and "FR-001 is defined twice" in messages


def test_spec_without_stories_fails(tmp_path):
    make_feature(tmp_path, spec="# Spec\n\n- **FR-001**: x\n", plan=plan_with(["| FR-001 | x | covered | a | |"]))
    code, data = gate(tmp_path, "plan")
    assert code == 1
    assert any("no user stories" in f["message"] for f in data["gates"][0]["findings"])


def test_plain_and_table_requirement_definitions(tmp_path):
    spec = (
        "### User Story 1 - A\n\n- FR-010: plain form\n"
        "| ID | Requirement |\n|---|---|\n| FR-011 | table form |\n"
        "- FR-010 and FR-011 together are not a definition\n"
    )
    fd = make_feature(tmp_path, spec=spec)
    config, _ = sg.load_config(tmp_path, None)
    model = sg.parse_spec(fd / "spec.md", sg.IdScheme(config), config)
    assert set(model.items) == {"US1", "FR-10", "FR-11"}
    assert not [f for f in model.findings if f.level == "violation"]


# --------------------------------------------------------------------------- plan gate


def test_plan_gate_catches_missing_user_story(tmp_path):
    rows = [r for r in FULL_ROWS if not r.startswith("| US3")]
    make_feature(tmp_path, plan=plan_with(rows))
    code, data = gate(tmp_path, "plan")
    assert code == 1
    result = items(data)
    assert result["US3"]["verdict"] == "violation"
    assert result["US3"]["code"] == "missing"
    assert data["gates"][0]["fix_skeleton"][0].startswith("| US3 |")


def test_plan_gate_passes_when_complete(tmp_path):
    make_feature(tmp_path, plan=plan_with(FULL_ROWS))
    code, data = gate(tmp_path, "plan")
    assert code == 0, data
    assert data["verdict"] == "pass"
    assert data["gates"][0]["summary"]["coverage_pct"] == 100.0


def test_deferred_needs_reason_and_is_waived_with_one(tmp_path):
    rows = FULL_ROWS[:-1] + ["| NFR-001 | perf | deferred | | |"]
    make_feature(tmp_path, plan=plan_with(rows))
    code, data = gate(tmp_path, "plan")
    assert code == 1 and items(data)["NFR-001"]["code"] == "no-reason"

    rows = FULL_ROWS[:-1] + ["| NFR-001 | perf | Deferred | | PO: after launch |"]
    make_feature(tmp_path, plan=plan_with(rows))
    code, data = gate(tmp_path, "plan")
    assert code == 0
    assert items(data)["NFR-001"]["verdict"] == "waived"
    assert "PO: after launch" in items(data)["NFR-001"]["detail"]


def test_reason_inside_status_cell_is_accepted(tmp_path):
    rows = FULL_ROWS[:-1] + ["| NFR-001 | perf | deferred - phase 2 |  | |"]
    make_feature(tmp_path, plan=plan_with(rows))
    code, data = gate(tmp_path, "plan")
    assert code == 0
    assert items(data)["NFR-001"]["detail"] == "deferred: phase 2"


def test_status_variants(tmp_path):
    assert sg.normalize_status("✅") == "covered"
    assert sg.normalize_status("**Covered**") == "covered"
    assert sg.normalize_status("In scope") == "covered"
    assert sg.normalize_status("Out of scope (v2)") == "deferred"
    assert sg.normalize_status("partial") == "partial"
    assert sg.normalize_status("") == "empty"
    assert sg.normalize_status("N/A") == "invalid"
    assert sg.normalize_status("maybe") == "invalid"


def test_invalid_status_and_placeholder_reference(tmp_path):
    rows = FULL_ROWS[:5] + ["| FR-003 | pay | maybe | x | |", "| NFR-001 | perf | covered | <where the plan handles it> | |"]
    make_feature(tmp_path, plan=plan_with(rows))
    code, data = gate(tmp_path, "plan")
    assert code == 1
    result = items(data)
    assert result["FR-003"]["code"] == "bad-status"
    assert result["NFR-001"]["code"] == "placeholder"


def test_conflicting_rows(tmp_path):
    rows = FULL_ROWS + ["| US2 | Basket | deferred | | later |"]
    make_feature(tmp_path, plan=plan_with(rows))
    code, data = gate(tmp_path, "plan")
    assert code == 1 and items(data)["US2"]["code"] == "conflict"


def test_unknown_id_in_plan_is_violation_or_warning(tmp_path):
    rows = FULL_ROWS + ["| US7 | Invented | covered | x | |"]
    make_feature(tmp_path, plan=plan_with(rows))
    code, data = gate(tmp_path, "plan")
    assert code == 1
    assert any("US7" in f["message"] for f in data["gates"][0]["findings"])
    cfg = tmp_path / "cfg.yml"
    cfg.write_text("unknown_ids: warning\n", encoding="utf-8")
    code, data = gate(tmp_path, "plan", "--config", str(cfg))
    assert code == 0


def test_multiple_ids_in_one_row(tmp_path):
    rows = FULL_ROWS[:3] + ["| FR-001, FR-002, FR-003 | all | covered | contracts/ | |", "| NFR-001 | p | covered | r | |"]
    make_feature(tmp_path, plan=plan_with(rows))
    code, _ = gate(tmp_path, "plan")
    assert code == 0


def test_missing_section(tmp_path):
    plan = "# Plan\n\nUS1, US2 and US3 are handled; FR-001 FR-002 FR-003 NFR-001 too.\n"
    make_feature(tmp_path, plan=plan)
    code, data = gate(tmp_path, "plan")
    assert code == 1
    assert any("no '## Scope Coverage' section" in f["message"] for f in data["gates"][0]["findings"])
    assert data["gates"][0]["fix_skeleton"][0] == "## Scope Coverage"
    cfg = tmp_path / "cfg.yml"
    cfg.write_text("plan:\n  require_section: false\n", encoding="utf-8")
    code, data = gate(tmp_path, "plan", "--config", str(cfg))
    assert code == 0, data


def test_stories_only_mode(tmp_path):
    rows = FULL_ROWS[:3]
    make_feature(tmp_path, plan=plan_with(rows))
    cfg = tmp_path / "cfg.yml"
    cfg.write_text("plan:\n  check_requirements: false\n", encoding="utf-8")
    code, _ = gate(tmp_path, "plan", "--config", str(cfg))
    assert code == 0


def test_html_comment_rows_are_ignored(tmp_path):
    plan = PLAN_HEAD.replace("| ID |", "<!-- | US3 | x | covered | y | | -->\n| ID |", 1)
    plan = plan_with([r for r in FULL_ROWS if not r.startswith("| US3")]).replace(
        "## Scope Coverage", "## Scope Coverage\n\n<!--\n| US3 | x | covered | y | |\n-->"
    )
    make_feature(tmp_path, plan=plan)
    code, data = gate(tmp_path, "plan")
    assert code == 1 and items(data)["US3"]["verdict"] == "violation"


# --------------------------------------------------------------------------- tasks gate


def test_tasks_gate_passes_and_uses_phase_inheritance(tmp_path):
    make_feature(tmp_path, plan=plan_with(FULL_ROWS), tasks=TASKS)
    code, data = gate(tmp_path, "tasks")
    assert code == 0, data
    assert items(data)["US2"]["evidence"] == ["T004", "T005"]  # T005 inherits US2 from its phase


def test_tasks_gate_catches_story_without_tasks(tmp_path):
    tasks = TASKS.split("## Phase 5")[0]
    make_feature(tmp_path, plan=plan_with(FULL_ROWS), tasks=tasks)
    code, data = gate(tmp_path, "tasks")
    assert code == 1
    result = items(data)
    assert result["US3"]["verdict"] == "violation"
    assert result["FR-003"]["verdict"] == "violation"


def test_plan_deferral_waives_tasks(tmp_path):
    rows = [r for r in FULL_ROWS if not r.startswith(("| US3", "| FR-003"))]
    rows += ["| US3 | Pay | deferred | | needs PSP contract |", "| FR-003 | pay | deferred | | with US3 |"]
    tasks = TASKS.split("## Phase 5")[0]
    make_feature(tmp_path, plan=plan_with(rows), tasks=tasks)
    code, data = gate(tmp_path, "tasks")
    assert code == 0
    assert items(data)["US3"]["verdict"] == "waived"


def test_tasks_coverage_table_maps_requirements(tmp_path):
    tasks = TASKS.replace(" (FR-002)", "") + (
        "\n## Scope Coverage\n\n| ID | Title | Status | Tasks | Reason |\n|----|----|----|----|----|\n"
        "| FR-002 | basket | covered | T004, T005 | |\n"
    )
    make_feature(tmp_path, plan=plan_with(FULL_ROWS), tasks=tasks)
    code, data = gate(tmp_path, "tasks")
    assert code == 0, data
    assert items(data)["FR-002"]["evidence"] == ["T004", "T005"]


def test_tasks_table_with_unknown_task_and_unknown_label(tmp_path):
    tasks = TASKS + "\n- [ ] T099 [US8] Ghost story task\n\n## Scope Coverage\n\n| ID | Status | Tasks |\n|---|---|---|\n| FR-001 | covered | T777 |\n"
    make_feature(tmp_path, plan=plan_with(FULL_ROWS), tasks=tasks)
    code, data = gate(tmp_path, "tasks")
    assert code == 1
    msgs = " ".join(f["message"] for f in data["gates"][0]["findings"])
    assert "T777" in msgs and "US8" in msgs


def test_duplicate_task_ids(tmp_path):
    tasks = TASKS + "\n- [ ] T002 [US1] Duplicate id\n"
    make_feature(tmp_path, plan=plan_with(FULL_ROWS), tasks=tasks)
    code, data = gate(tmp_path, "tasks")
    assert code == 1
    assert any("T002 is used twice" in f["message"] for f in data["gates"][0]["findings"])


# --------------------------------------------------------------------------- implement gate


def test_implement_gate_reports_open_tasks(tmp_path):
    make_feature(tmp_path, plan=plan_with(FULL_ROWS), tasks=TASKS)
    code, data = gate(tmp_path, "implement")
    assert code == 1
    result = items(data)
    assert result["US1"]["verdict"] == "pass"
    assert result["US2"]["code"] == "open"
    assert "T004" in result["US2"]["detail"]
    done = TASKS.replace("- [ ]", "- [x]")
    make_feature(tmp_path, plan=plan_with(FULL_ROWS), tasks=done)
    code, _ = gate(tmp_path, "implement")
    assert code == 0


# --------------------------------------------------------------------------- CLI behaviour


def test_check_runs_available_gates_and_report_mode(tmp_path):
    rows = [r for r in FULL_ROWS if not r.startswith("| US3")]
    make_feature(tmp_path, plan=plan_with(rows), tasks=TASKS)
    proc = run_cli(tmp_path, "check", "--json", "--feature-dir", "specs/001-demo")
    data = json.loads(proc.stdout)
    assert proc.returncode == 1
    assert [g["gate"] for g in data["gates"]] == ["plan", "tasks"]
    proc = run_cli(tmp_path, "check", "--feature-dir", "specs/001-demo", "--report-only")
    assert proc.returncode == 0 and "report mode" in proc.stdout
    proc = run_cli(tmp_path, "check", "--feature-dir", "specs/001-demo", env={"SCOPEGUARD_MODE": "report"})
    assert proc.returncode == 0


def test_feature_resolution(tmp_path):
    make_feature(tmp_path, plan=plan_with(FULL_ROWS), name="001-demo")
    make_feature(tmp_path, plan=plan_with(FULL_ROWS), name="002-other")
    proc = run_cli(tmp_path, "plan")
    assert proc.returncode == 2 and "cannot tell which feature" in proc.stderr
    (tmp_path / ".specify" / "feature.json").write_text('{"feature_directory": "specs/002-other"}', encoding="utf-8")
    proc = run_cli(tmp_path, "plan", "--json")
    assert json.loads(proc.stdout)["gates"][0]["feature_dir"] == "specs/002-other"
    proc = run_cli(tmp_path, "plan", "--json", env={"SPECIFY_FEATURE_DIRECTORY": "specs/001-demo"})
    assert json.loads(proc.stdout)["gates"][0]["feature_dir"] == "specs/001-demo"
    proc = run_cli(tmp_path, "check", "--all", "--json")
    assert [g["feature_dir"] for g in json.loads(proc.stdout)["gates"]] == ["specs/001-demo", "specs/002-other"]
    cfg = tmp_path / ".specify" / "extensions" / "scopeguard"
    cfg.mkdir(parents=True)
    (cfg / "scopeguard-config.yml").write_text("features:\n  exclude:\n    - '001-*'\n", encoding="utf-8")
    proc = run_cli(tmp_path, "check", "--all", "--json")
    assert [g["feature_dir"] for g in json.loads(proc.stdout)["gates"]] == ["specs/002-other"]


def test_missing_artifacts_exit_2(tmp_path):
    make_feature(tmp_path)
    proc = run_cli(tmp_path, "plan", "--feature-dir", "specs/001-demo")
    assert proc.returncode == 2 and "plan.md not found" in proc.stderr
    proc = run_cli(tmp_path, "tasks", "--feature-dir", "specs/001-demo", "--json")
    assert proc.returncode == 2 and json.loads(proc.stdout)["verdict"] == "error"


def test_inventory_prints_contract_and_skeleton(tmp_path):
    make_feature(tmp_path)
    proc = run_cli(tmp_path, "inventory", "--feature-dir", "specs/001-demo")
    assert proc.returncode == 0
    assert "SCOPE CONTRACT" in proc.stdout
    assert "| US3 | Pay with card (P3) | covered | <where the plan handles it> | |" in proc.stdout


def test_report_and_save(tmp_path):
    fd = make_feature(tmp_path, plan=plan_with(FULL_ROWS), tasks=TASKS)
    proc = run_cli(tmp_path, "report", "--feature-dir", "specs/001-demo", "--save")
    assert proc.returncode == 0
    report = (fd / "scopeguard-report.md").read_text(encoding="utf-8")
    assert "| US2 | Add to basket (P2) | ok | ok T004,T005 | OPEN |" in report


def test_compare_two_runs(tmp_path):
    make_feature(tmp_path, plan=plan_with(FULL_ROWS), tasks=TASKS, name="001-run-a")
    rows = [r for r in FULL_ROWS if not r.startswith("| US3")]
    make_feature(tmp_path, plan=plan_with(rows), tasks=TASKS, name="001-run-b")
    proc = run_cli(tmp_path, "compare", "specs/001-run-a", "specs/001-run-b", "--labels", "a,b")
    assert proc.returncode == 0
    assert "| US3 |" in proc.stdout and "**yes**" in proc.stdout
    proc = run_cli(tmp_path, "compare", "specs/001-run-a", "specs/001-run-b", "--fail-on-diff")
    assert proc.returncode == 1


def test_out_markdown_and_append(tmp_path):
    make_feature(tmp_path, plan=plan_with(FULL_ROWS))
    out = tmp_path / "summary.md"
    run_cli(tmp_path, "plan", "--feature-dir", "specs/001-demo", "--out", str(out))
    run_cli(tmp_path, "plan", "--feature-dir", "specs/001-demo", "--out", str(out), "--append")
    assert out.read_text(encoding="utf-8").count("scopeGuard - plan gate") == 2


@pytest.mark.parametrize("eol", ["\r\n", "\r\r\n"])
def test_crlf_bom_and_unicode(tmp_path, eol):
    fd = make_feature(tmp_path)
    spec = "\ufeff" + SPEC.replace("Browse catalog", "Przeglądaj katalog – żółć")
    (fd / "spec.md").write_bytes(spec.replace("\n", eol).encode("utf-8"))
    (fd / "plan.md").write_bytes(plan_with(FULL_ROWS).replace("\n", eol).encode("utf-8"))
    proc = run_cli(tmp_path, "plan", "--feature-dir", "specs/001-demo", "--verbose")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "Przeglądaj katalog" in proc.stdout


def test_example_reproduces_lab_issue(tmp_path):
    root = tmp_path / "lab"
    (root / ".specify").mkdir(parents=True)
    shutil.copytree(EXAMPLE, root / "specs" / "001-team-board")
    proc = run_cli(root, "plan", "--json")
    data = json.loads(proc.stdout)
    assert proc.returncode == 1
    failing = {i["id"] for i in data["gates"][0]["items"] if i["verdict"] == "violation"}
    assert failing == {"US3", "FR-004", "FR-007"}


# --------------------------------------------------------------------------- config


def test_mini_yaml_parser_reads_the_shipped_config_template():
    text = (REPO / "config-template.yml").read_text(encoding="utf-8")
    data = sg.parse_simple_yaml(text)
    assert data["mode"] == "enforce"
    assert data["ids"]["requirement_prefixes"] == ["FR", "NFR"]
    assert data["ids"]["story_key"] == "US" and data["ids"]["story_pattern"] is None
    assert data["plan"]["require_section"] is True
    assert data["features"]["exclude"] == []
    merged = sg._deep_merge(sg.DEFAULT_CONFIG, data)
    assert merged == sg._deep_merge(sg.DEFAULT_CONFIG, {})


def test_mini_yaml_block_lists_and_quotes():
    data = sg.parse_simple_yaml("a:\n  b:\n    - 'x # not a comment'\n    - y\n  c: \"q\" # comment\nd: [1, two]\n")
    assert data == {"a": {"b": ["x # not a comment", "y"], "c": "q"}, "d": [1, "two"]}


def test_bad_config_is_exit_2(tmp_path):
    make_feature(tmp_path, plan=plan_with(FULL_ROWS))
    cfg = tmp_path / "cfg.yml"
    cfg.write_text("mode: strict\n", encoding="utf-8")
    code, data = gate(tmp_path, "plan", "--config", str(cfg))
    assert code == 2 and data["verdict"] == "error"


@pytest.mark.parametrize("text", ["bogus_key: 1\n", "autocorrect:\n  max_iteration: 1\n", "plan:\n  check_requirments: false\n", "plan: false\n"])
def test_unknown_config_key_is_exit_2(tmp_path, text):
    make_feature(tmp_path, plan=plan_with(FULL_ROWS))
    cfg = tmp_path / "cfg.yml"
    cfg.write_text(text, encoding="utf-8")
    code, data = gate(tmp_path, "plan", "--config", str(cfg))
    assert code == 2 and data["verdict"] == "error" and "config:" in data["error"]


def test_python_engine_refuses_old_python():
    text = ENGINE.read_text(encoding="utf-8")
    assert "sys.version_info < (3, 9)" in text


# --------------------------------------------------------------------------- resolution loop


def test_spec_excerpt_is_attached_to_items(tmp_path):
    fd = make_feature(tmp_path, spec=SPEC.replace("### User Story 3 – Pay with card (Priority: P3)\n\nText.",
                                                   "### User Story 3 – Pay with card (Priority: P3)\n\nPay by card.\n\n1. **Given** a basket, **When** paying, **Then** it works."))
    config, _ = sg.load_config(tmp_path, None)
    model = sg.parse_spec(fd / "spec.md", sg.IdScheme(config), config)
    assert model.items["US3"].excerpt.startswith("### User Story 3")
    assert "**When** paying" in model.items["US3"].excerpt
    assert "Requirements" not in model.items["US3"].excerpt
    assert model.items["FR-3"].excerpt == "- **FR-003**: System MUST accept card payments."


def test_iteration_loop_escalates_after_max_iterations(tmp_path):
    rows = [r for r in FULL_ROWS if not r.startswith("| US3")]
    fd = make_feature(tmp_path, plan=plan_with(rows))
    proc = run_cli(tmp_path, "plan", "--feature-dir", "specs/001-demo", "--iteration", "0")
    assert proc.returncode == 1
    assert "RESOLVE" in proc.stdout and "> ### User Story 3" in proc.stdout
    assert "re-run this gate with --iteration 1" in proc.stdout
    for i in (1, 2, 3):
        code, data = gate(tmp_path, "plan", "--iteration", str(i))
        assert code == 1 and data["gates"][0]["next_iteration"] == i + 1 and not data["gates"][0]["escalated"]
    code, data = gate(tmp_path, "plan", "--iteration", "4")
    assert code == 3
    assert data["verdict"] == "escalate"
    g = data["gates"][0]
    assert g["escalated"] and g["escalation_report"] == "specs/001-demo/scopeguard-escalation-plan.md"
    assert items(data)["US3"]["spec_excerpt"].startswith("### User Story 3")
    report = (fd / "scopeguard-escalation-plan.md").read_text(encoding="utf-8")
    assert "### US3 - Pay with card (P3)" in report
    assert "TODO(agent)" in report and "| 4 | 1 | US3 |" in report
    history = json.loads((fd / ".scopeguard" / "history-plan.json").read_text(encoding="utf-8"))
    assert [e["iteration"] for e in history["iterations"]] == [0, 1, 2, 3, 4]


def test_resolving_clears_stale_escalation_and_resets_history(tmp_path):
    rows = [r for r in FULL_ROWS if not r.startswith("| US3")]
    fd = make_feature(tmp_path, plan=plan_with(rows))
    code, _ = gate(tmp_path, "plan", "--iteration", "4")
    assert code == 3 and (fd / "scopeguard-escalation-plan.md").is_file()
    (fd / "plan.md").write_text(plan_with(FULL_ROWS), encoding="utf-8")
    code, data = gate(tmp_path, "plan", "--iteration", "0")
    assert code == 0 and data["gates"][0]["next_iteration"] is None
    assert not (fd / "scopeguard-escalation-plan.md").exists()
    history = json.loads((fd / ".scopeguard" / "history-plan.json").read_text(encoding="utf-8"))
    assert [e["iteration"] for e in history["iterations"]] == [0]


def test_max_iterations_config_and_no_escalation_without_iteration(tmp_path):
    rows = [r for r in FULL_ROWS if not r.startswith("| US3")]
    make_feature(tmp_path, plan=plan_with(rows))
    code, _ = gate(tmp_path, "plan")  # CI / manual: plain violation
    assert code == 1
    cfg = tmp_path / "cfg.yml"
    cfg.write_text("remediation:\n  max_iterations: 2\n", encoding="utf-8")
    code, _ = gate(tmp_path, "plan", "--config", str(cfg), "--iteration", "1")
    assert code == 1
    code, _ = gate(tmp_path, "plan", "--config", str(cfg), "--iteration", "2")
    assert code == 3
    code, _ = gate(tmp_path, "plan", "--config", str(cfg), "--iteration", "2", "--report-only")
    assert code == 0


def test_tasks_gate_escalation_report(tmp_path):
    tasks = TASKS.split("## Phase 5")[0]
    fd = make_feature(tmp_path, plan=plan_with(FULL_ROWS), tasks=tasks)
    code, data = gate(tmp_path, "tasks", "--iteration", "4")
    assert code == 3
    report = (fd / "scopeguard-escalation-tasks.md").read_text(encoding="utf-8")
    assert "### US3 - Pay with card (P3)" in report and "`tasks.md`" in report


# --------------------------------------------------------------------------- integration / autocorrect / configure

EXTENSIONS_YML = """installed:
- git
- scopeguard
settings:
  auto_execute_hooks: true
hooks:
  before_plan:
  - extension: git
    command: speckit.git.commit
    enabled: true
    optional: true
    priority: 10
    prompt: Commit outstanding changes before planning?
    description: Auto-commit before implementation planning
    condition: null
  - extension: scopeguard
    command: speckit.scopeguard.inventory
    enabled: true
    optional: false
    priority: 10
    prompt: Execute speckit.scopeguard.inventory?
    description: Put the full scope contract (every story and requirement ID) in front
      of the planner
    condition: null
  after_plan:
  - extension: scopeguard
    command: speckit.scopeguard.plan
    optional: false
    priority: 10
    condition: null
  before_tasks:
  - extension: scopeguard
    command: speckit.scopeguard.inventory
    enabled: true
    optional: false
  after_tasks:
  - extension: scopeguard
    command: speckit.scopeguard.tasks
    enabled: true
    optional: false
  after_implement:
  - extension: scopeguard
    command: speckit.scopeguard.implement
    enabled: true
    optional: true
    prompt: Run the scopeGuard implement gate?
"""


def install_inline_preset(root: Path, enabled: bool = True) -> None:
    commands = root / ".specify" / "presets" / "scopeguard-templates" / "commands"
    commands.mkdir(parents=True, exist_ok=True)
    for name in ("speckit.plan.md", "speckit.tasks.md"):
        (commands / name).write_text("{CORE_TEMPLATE}\n", encoding="utf-8")
    registry = {"schema_version": "1.0", "presets": {"scopeguard-templates": {"version": "0.3.0", "enabled": enabled}}}
    (root / ".specify" / "presets" / ".registry").write_text(json.dumps(registry), encoding="utf-8")


def write_config(root: Path, text: str) -> None:
    cfg = root / ".specify" / "extensions" / "scopeguard"
    cfg.mkdir(parents=True, exist_ok=True)
    (cfg / "scopeguard-config.yml").write_text(text, encoding="utf-8")


def test_inline_integration_falls_back_to_hooks_without_preset(tmp_path):
    rows = [r for r in FULL_ROWS if not r.startswith("| US3")]
    make_feature(tmp_path, plan=plan_with(rows))
    # default integration is inline, but the preset is missing -> hooks do the work
    proc = run_cli(tmp_path, "plan", "--feature-dir", "specs/001-demo", "--via", "hook")
    assert proc.returncode == 1 and "falls back" not in proc.stdout
    assert "preset" in proc.stdout and "run through the hooks instead" in proc.stdout
    proc = run_cli(tmp_path, "plan", "--feature-dir", "specs/001-demo", "--via", "inline")
    assert proc.returncode == 0 and "skipped" in proc.stdout


def test_inline_integration_with_preset_skips_hooks(tmp_path):
    rows = [r for r in FULL_ROWS if not r.startswith("| US3")]
    make_feature(tmp_path, plan=plan_with(rows))
    install_inline_preset(tmp_path)
    proc = run_cli(tmp_path, "plan", "--feature-dir", "specs/001-demo", "--via", "hook", "--json")
    assert proc.returncode == 0 and json.loads(proc.stdout)["verdict"] == "skipped"
    proc = run_cli(tmp_path, "inventory", "--feature-dir", "specs/001-demo", "--via", "hook")
    assert proc.returncode == 0 and "skipped" in proc.stdout and "SCOPE CONTRACT" not in proc.stdout
    proc = run_cli(tmp_path, "plan", "--feature-dir", "specs/001-demo", "--via", "inline", "--iteration", "0")
    assert proc.returncode == 1 and "RESOLVE" in proc.stdout
    # a disabled preset counts as missing
    install_inline_preset(tmp_path, enabled=False)
    proc = run_cli(tmp_path, "plan", "--feature-dir", "specs/001-demo", "--via", "inline")
    assert proc.returncode == 0 and "skipped" in proc.stdout


def test_hooks_integration_skips_inline_step(tmp_path):
    rows = [r for r in FULL_ROWS if not r.startswith("| US3")]
    make_feature(tmp_path, plan=plan_with(rows))
    install_inline_preset(tmp_path)
    write_config(tmp_path, "integration: hooks\n")
    proc = run_cli(tmp_path, "plan", "--feature-dir", "specs/001-demo", "--via", "inline")
    assert proc.returncode == 0 and "integration is 'hooks'" in proc.stdout
    proc = run_cli(tmp_path, "plan", "--feature-dir", "specs/001-demo", "--via", "hook")
    assert proc.returncode == 1
    proc = run_cli(tmp_path, "plan", "--feature-dir", "specs/001-demo", "--via", "hook", env={"SCOPEGUARD_INTEGRATION": "inline"})
    assert proc.returncode == 0 and "skipped" in proc.stdout


def test_autocorrect_off_reports_and_stops_at_first_check(tmp_path):
    rows = [r for r in FULL_ROWS if not r.startswith("| US3")]
    fd = make_feature(tmp_path, plan=plan_with(rows))
    write_config(tmp_path, "autocorrect:\n  enabled: false\n")
    proc = run_cli(tmp_path, "plan", "--feature-dir", "specs/001-demo", "--iteration", "0")
    assert proc.returncode == 3
    assert "AUTOCORRECT OFF" in proc.stdout
    report = (fd / "scopeguard-escalation-plan.md").read_text(encoding="utf-8")
    assert "autocorrect is off" in report and "TODO(agent)" not in report and "### US3" in report
    # without --iteration (CI / manual) it is a plain violation
    proc = run_cli(tmp_path, "plan", "--feature-dir", "specs/001-demo")
    assert proc.returncode == 1


def test_autocorrect_max_iterations_from_config(tmp_path):
    rows = [r for r in FULL_ROWS if not r.startswith("| US3")]
    make_feature(tmp_path, plan=plan_with(rows))
    write_config(tmp_path, "autocorrect:\n  enabled: true\n  max_iterations: 6\n")
    code, data = gate(tmp_path, "plan", "--iteration", "4")
    assert code == 1 and data["gates"][0]["max_iterations"] == 6
    code, data = gate(tmp_path, "plan", "--iteration", "6")
    assert code == 3
    proc = run_cli(tmp_path, "plan", "--feature-dir", "specs/001-demo", "--iteration", "1", env={"SCOPEGUARD_MAX_ITERATIONS": "1"})
    assert proc.returncode == 3


@pytest.mark.parametrize("text", [
    "integration: sidecar\n",
    "autocorrect:\n  max_iterations: 0\n",
    "autocorrect:\n  enabled: maybe\n",
    "autocorrect:\n  max_iterations: lots\n",
])
def test_invalid_integration_and_autocorrect_config(tmp_path, text):
    make_feature(tmp_path, plan=plan_with(FULL_ROWS))
    write_config(tmp_path, text)
    proc = run_cli(tmp_path, "plan", "--feature-dir", "specs/001-demo")
    assert proc.returncode == 2 and "config:" in proc.stderr


def _hook_states(text: str):
    states, event, current = {}, None, {}
    for line in text.splitlines():
        if line.startswith("  ") and not line.startswith("  -") and line.strip().endswith(":") and not line.startswith("    "):
            event = line.strip()[:-1]
        stripped = line.strip()
        if stripped.startswith("- "):
            current = {}
            stripped = stripped[2:]
        if ":" in stripped:
            k, _, v = stripped.partition(":")
            current[k.strip()] = v.strip()
            if "extension" in current and "command" in current and event:
                states[(event, current["extension"], current["command"])] = current.get("enabled", "true")
    return states


def test_configure_switches_hooks_for_integration(tmp_path):
    make_feature(tmp_path)
    yml = tmp_path / ".specify" / "extensions.yml"
    yml.write_text(EXTENSIONS_YML, encoding="utf-8")
    install_inline_preset(tmp_path)
    write_config(tmp_path, "integration: inline\n")

    proc = run_cli(tmp_path, "configure", "--dry-run")
    assert proc.returncode == 0 and "would change" in proc.stdout
    assert yml.read_text(encoding="utf-8") == EXTENSIONS_YML

    proc = run_cli(tmp_path, "configure")
    assert proc.returncode == 0, proc.stderr
    text = yml.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(text)
        hooks = {(e, h["command"]): h.get("enabled", True) for e, hs in data["hooks"].items() for h in hs}
        assert hooks[("before_plan", "speckit.git.commit")] is True
        assert hooks[("before_plan", "speckit.scopeguard.inventory")] is False
        assert hooks[("after_plan", "speckit.scopeguard.plan")] is False
        assert hooks[("after_tasks", "speckit.scopeguard.tasks")] is False
        assert hooks[("after_implement", "speckit.scopeguard.implement")] is True
    except ImportError:
        pass
    states = _hook_states(text)
    assert states[("after_plan", "scopeguard", "speckit.scopeguard.plan")] == "false"
    assert states[("before_plan", "git", "speckit.git.commit")] == "true"
    assert "of the planner" in text  # multi-line values untouched

    proc = run_cli(tmp_path, "configure", "--json")
    assert json.loads(proc.stdout)["changed"] == 0  # idempotent

    write_config(tmp_path, "integration: hooks\nimplement:\n  enabled: false\n")
    proc = run_cli(tmp_path, "configure", "--json")
    data = json.loads(proc.stdout)
    assert data["effective_integration"] == "hooks"
    states = _hook_states(yml.read_text(encoding="utf-8"))
    assert states[("after_plan", "scopeguard", "speckit.scopeguard.plan")] == "true"
    assert states[("after_implement", "scopeguard", "speckit.scopeguard.implement")] == "false"


def test_configure_keeps_hooks_on_when_inline_preset_missing(tmp_path):
    make_feature(tmp_path)
    yml = tmp_path / ".specify" / "extensions.yml"
    yml.write_text(EXTENSIONS_YML, encoding="utf-8")
    proc = run_cli(tmp_path, "configure")
    assert proc.returncode == 0
    assert "NOTE" in proc.stdout and "specify preset add" in proc.stdout
    states = _hook_states(yml.read_text(encoding="utf-8"))
    assert states[("after_plan", "scopeguard", "speckit.scopeguard.plan")] == "true"


def test_configure_keeps_crlf_line_endings(tmp_path):
    """Spec Kit writes .specify/extensions.yml with CRLF on Windows: configure keeps them, so git shows only its edits."""
    results = {}
    for eol in ("\n", "\r\n"):
        root = tmp_path / ("crlf" if eol == "\r\n" else "lf")
        make_feature(root)
        yml = root / ".specify" / "extensions.yml"
        yml.write_bytes(EXTENSIONS_YML.replace("\n", eol).encode("utf-8"))
        write_config(root, "integration: embedded\n")
        proc = run_cli(root, "configure")
        assert proc.returncode == 0, proc.stderr
        results[eol] = yml.read_bytes()
    assert results["\n"] != EXTENSIONS_YML.encode("utf-8")                     # configure edited the file
    assert results["\r\n"] == results["\n"].replace(b"\n", b"\r\n")             # the same edit, line endings kept


def test_configure_without_extension_registry_is_error(tmp_path):
    make_feature(tmp_path)
    proc = run_cli(tmp_path, "configure")
    assert proc.returncode == 2 and "extensions.yml" in proc.stderr


def test_preset_wraps_core_commands_with_inline_steps():
    manifest = (REPO / "preset" / "preset.yml").read_text(encoding="utf-8")
    for name in ("speckit.plan", "speckit.tasks"):
        assert f'name: "{name}"' in manifest
        body = (REPO / "preset" / "commands" / f"{name}.md").read_text(encoding="utf-8")
        gate = name.split(".")[1]
        assert "strategy: wrap" in body and body.count("{CORE_TEMPLATE}") == 1
        assert f"{gate} --via inline --iteration N --feature-dir <FEATURE_DIR>" in body
        assert "inventory --via inline" in body and "AUTOCORRECT OFF" in body and "TODO(agent)" in body
        assert "scripts/" not in body.replace(".specify/extensions/scopeguard/scripts/", "")


# --------------------------------------------------------------------------- story key (v0.4)

UC_SPEC = """# Feature Specification: Orders

### UC-001 - Place an order (Priority: P1)

Text.

### Use Case 2 - Cancel an order (Priority: P2)

Text.

## Requirements

- **BR-001**: One order line per basket item.
- **BR-002**: An order can be cancelled until it ships.
"""

UC_PLAN = PLAN_HEAD + """| UC-001 | Place | covered | contracts/orders.yaml | |
| BR-001 | lines | covered | data-model.md | |
| BR-002 | cancel | covered | contracts/orders.yaml | |
"""

UC_TASKS = """# Tasks: Orders

## Phase 3: UC-001 - Place an order

- [x] T001 Order endpoint (BR-001)

## Phase 4: Use Case 2 - Cancel an order

- [ ] T002 Cancel endpoint (BR-002)
- [ ] T003 [UC-002] Cancel screen
"""

UC_CONFIG = "ids:\n  story_key: UC\n  story_name: Use Case\n  requirement_prefixes: [BR]\n"


def test_story_key_uc_traces_use_cases(tmp_path):
    make_feature(tmp_path, spec=UC_SPEC, plan=UC_PLAN, tasks=UC_TASKS)
    write_config(tmp_path, UC_CONFIG)
    proc = run_cli(tmp_path, "inventory", "--feature-dir", "specs/001-demo")
    assert proc.returncode == 0, proc.stderr
    assert "2 use cases, 2 requirements (traced prefixes: UC, BR)" in proc.stdout
    assert "UC-001" in proc.stdout and "UC-2" in proc.stdout
    assert "[UC-nnn]" in proc.stdout
    code, data = gate(tmp_path, "plan")
    assert code == 1
    bad = {i["id"] for i in data["gates"][0]["items"] if i["verdict"] == "violation"}
    assert bad == {"UC-2"}                       # Use Case 2 is missing from the plan
    (tmp_path / "specs" / "001-demo" / "plan.md").write_text(
        UC_PLAN + "| UC-002 | Cancel | covered | contracts/orders.yaml | |\n", encoding="utf-8")
    assert gate(tmp_path, "plan")[0] == 0        # UC-002 and Use Case 2 are the same story
    code, data = gate(tmp_path, "tasks")
    assert code == 0, data                       # phase inheritance and [UC-002] labels both carry
    code, data = gate(tmp_path, "implement")
    assert code == 1 and {i["id"] for i in items(data).values() if i["verdict"] == "violation"} >= {"UC-2"}


def test_story_key_defaults_keep_user_stories(tmp_path):
    make_feature(tmp_path, plan=plan_with(FULL_ROWS))
    proc = run_cli(tmp_path, "inventory", "--feature-dir", "specs/001-demo")
    assert "3 user stories" in proc.stdout and "traced prefixes: US, FR, NFR" in proc.stdout and "[USn]" in proc.stdout


@pytest.mark.parametrize("text, message", [
    ("ids:\n  story_key: U-C\n", "letters only"),
    ("ids:\n  story_key: FR\n", "both ids.story_key and a requirement prefix"),
])
def test_story_key_validation(tmp_path, text, message):
    make_feature(tmp_path, plan=plan_with(FULL_ROWS))
    write_config(tmp_path, text)
    proc = run_cli(tmp_path, "plan", "--feature-dir", "specs/001-demo")
    assert proc.returncode == 2 and message in proc.stderr


def test_spec_without_stories_names_the_story_key(tmp_path):
    make_feature(tmp_path, spec="# Spec\n\n- **BR-001**: x\n", plan=PLAN_HEAD)
    write_config(tmp_path, UC_CONFIG)
    proc = run_cli(tmp_path, "plan", "--feature-dir", "specs/001-demo")
    assert proc.returncode == 1 and "defines no use cases" in proc.stdout and "'### Use Case 1" in proc.stdout


# --------------------------------------------------------------------------- embedded integration (v0.4)


def test_embedded_integration_skips_hooks_and_inline_steps_but_runs_direct_calls(tmp_path):
    rows = [r for r in FULL_ROWS if not r.startswith("| US3")]
    make_feature(tmp_path, plan=plan_with(rows))
    write_config(tmp_path, "integration: embedded\n")
    for via in ("hook", "inline"):
        proc = run_cli(tmp_path, "plan", "--feature-dir", "specs/001-demo", "--via", via)
        assert proc.returncode == 0 and "integration is 'embedded'" in proc.stdout, via
    code, data = gate(tmp_path, "plan")              # the embedding tool calls the command line directly
    assert code == 1 and "US3" in items(data)


def test_embedded_without_archiguard_says_no_scope_gate_runs(tmp_path):
    make_feature(tmp_path)
    (tmp_path / ".specify" / "extensions.yml").write_text(EXTENSIONS_YML, encoding="utf-8")
    write_config(tmp_path, "integration: embedded\n")
    warning = "archiGuard, the tool that runs the scope gate, is not installed, so no scope gate runs"
    proc = run_cli(tmp_path, "configure")
    assert proc.returncode == 0 and f"NOTE: integration is 'embedded' but {warning}" in proc.stdout
    proc = run_cli(tmp_path, "plan", "--feature-dir", "specs/001-demo", "--via", "inline")
    assert proc.returncode == 0 and "skipped here" in proc.stdout and warning in proc.stdout
    manifest = tmp_path / ".specify" / "extensions" / "archiguard" / "extension.yml"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("extension:\n  id: archiguard\n", encoding="utf-8")
    assert warning not in run_cli(tmp_path, "configure").stdout


def test_escalation_names_the_other_extensions_hooks_it_skips(tmp_path):
    rows = [r for r in FULL_ROWS if not r.startswith("| US3")]
    make_feature(tmp_path, plan=plan_with(rows))
    install_inline_preset(tmp_path)
    assert EXTENSIONS_YML.count("\n  before_tasks:\n") == 1
    (tmp_path / ".specify" / "extensions.yml").write_text(EXTENSIONS_YML.replace("\n  before_tasks:\n", (
        "\n  - extension: git\n    command: speckit.git.commit\n    enabled: true   # on\n    optional: true\n"
        "  - extension: agent-context\n    command: speckit.agent-context.update\n    optional: false\n"
        "  - extension: other\n    command: speckit.other.thing\n    enabled: false\n"
        "  before_tasks:\n")), encoding="utf-8")
    names = ("NOT RUN: /speckit.plan ends here, so these after_plan hooks of other extensions do not run: "
             "git: speckit.git.commit (optional); agent-context: speckit.agent-context.update. Tell the user; they run "
             "when the command is run again and passes.")
    proc = run_cli(tmp_path, "plan", "--feature-dir", "specs/001-demo", "--via", "inline", "--iteration", "0")
    assert proc.returncode == 1 and "NOT RUN" not in proc.stdout          # resolving: the command goes on
    proc = run_cli(tmp_path, "plan", "--feature-dir", "specs/001-demo", "--via", "inline", "--iteration", "4")
    assert proc.returncode == 3 and names in proc.stdout, proc.stdout
    proc = run_cli(tmp_path, "plan", "--feature-dir", "specs/001-demo", "--iteration", "4")
    assert proc.returncode == 3 and "NOT RUN" not in proc.stdout          # by hand: no command is stopped


def test_configure_embedded_switches_every_hook_off(tmp_path):
    make_feature(tmp_path)
    yml = tmp_path / ".specify" / "extensions.yml"
    yml.write_text(EXTENSIONS_YML, encoding="utf-8")
    write_config(tmp_path, "integration: embedded\n")
    proc = run_cli(tmp_path, "configure", "--json")
    data = json.loads(proc.stdout)
    assert data["effective_integration"] == "embedded"
    states = _hook_states(yml.read_text(encoding="utf-8"))
    for (event, ext, cmd), enabled in states.items():
        if ext == "scopeguard":
            assert enabled == "false", (event, cmd)
    assert states[("before_plan", "git", "speckit.git.commit")] == "true"
    install_inline_preset(tmp_path)
    proc = run_cli(tmp_path, "configure")
    assert "specify preset remove scopeguard-templates" in proc.stdout
