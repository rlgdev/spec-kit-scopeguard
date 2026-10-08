#!/usr/bin/env python3
"""scopeGuard - deterministic scope-coverage gates for GitHub Spec Kit.

scopeGuard reads the user stories (US1, US2, ... or another story key such as
UC-001) and requirement IDs (FR-001, NFR-001, ...) defined in a feature's
``spec.md`` and verifies, with
plain parsing and set arithmetic (no LLM involved), that every one of them is
still accounted for after each Spec Kit phase:

* ``plan``      - every scope item has a row in plan.md's "Scope Coverage" table
                  (covered, or deferred with a reason)
* ``tasks``     - every in-scope item is carried by at least one task in tasks.md
* ``implement`` - every task carrying an in-scope item is checked off

Anything missing is a *violation* and the gate exits 1. Deferred items are
*waived* (visible, never silent). The verdict vocabulary is pass / violation /
waived.

Standard library only; Python 3.9+. PyYAML is used for the config file when
available, otherwise a small built-in YAML-subset reader is used.

Exit codes: 0 = pass, 1 = violations found (resolve them), 2 = usage or setup error,
3 = still failing after the last allowed resolution iteration (escalate to the user).
"""

from __future__ import annotations

import argparse
import copy
import fnmatch
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

if sys.version_info < (3, 9):
    sys.stderr.write("scopeGuard: ERROR: Python 3.9 or newer is required\n")
    sys.exit(2)

__version__ = "0.4.1"

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_ERROR = 2
EXIT_ESCALATE = 3  # still failing after the last allowed resolution iteration

TOOL = "scopeguard"
CONFIG_RELATIVE = Path(".specify") / "extensions" / "scopeguard" / "scopeguard-config.yml"
INTEGRATIONS = ("inline", "hooks", "embedded")
CONFIG_LOCAL_RELATIVES = (
    Path(".specify") / "extensions" / "scopeguard" / "local-config.yml",  # Spec Kit convention
    Path(".specify") / "extensions" / "scopeguard" / "scopeguard-config.local.yml",
)
EXTENSIONS_YML = Path(".specify") / "extensions.yml"
INLINE_PRESET_DIR = Path(".specify") / "presets" / "scopeguard-templates"
INLINE_COMMANDS = ("speckit.plan", "speckit.tasks")

DEFAULT_CONFIG: Dict[str, Any] = {
    # inline:   the gates are mandatory steps inside /speckit.plan and /speckit.tasks
    #           (needs the scopeguard-templates preset; falls back to hooks without it).
    # hooks:    the gates run as separate scopeGuard commands triggered by Spec Kit hooks.
    # embedded: no hooks and no inline steps; the gates run only when another tool calls
    #           scopeGuard's command line (for example archiGuard's gate runner).
    "integration": "inline",
    "autocorrect": {
        # true:  a failing plan/tasks gate makes the agent fix the artifact and re-check.
        # false: a failing gate only reports the violations and stops the command.
        "enabled": True,
        # resolve-and-recheck iterations before the gate escalates with a problem report.
        "max_iterations": 4,
    },
    # enforce: violations make the gate exit 1.  report: always exit 0 (measure only).
    "mode": "enforce",
    "ids": {
        # The key of story IDs: US (Spec Kit user stories: US1, task labels [US1]) or another key,
        # e.g. UC for use cases (UC-001, task labels [UC-001]).
        "story_key": "US",
        # Long name of a story in headings and phase titles ("User Story 1"); "" = only the key.
        # Default: "User Story" for the key US, none for other keys (set e.g. "Use Case").
        "story_name": None,
        # Matched (case-insensitive) at the start of a spec.md heading's text.
        # Group 1 must capture the story number. Default: derived from story_key and story_name.
        "story_pattern": None,
        # Requirement ID prefixes that are part of the traced scope.
        # Add "SC" to also trace Success Criteria.
        "requirement_prefixes": ["FR", "NFR"],
    },
    "spec": {
        "require_stories": True,
    },
    "plan": {
        "enabled": True,
        "section": "Scope Coverage",
        "require_section": True,
        "check_requirements": True,
        "require_reason_for_waiver": True,
        "require_reference_for_covered": False,
    },
    "tasks": {
        "enabled": True,
        "section": "Scope Coverage",
        "check_requirements": True,
        "inherit_story_from_phase": True,
        "require_reason_for_waiver": True,
    },
    "implement": {
        "enabled": True,
        "check_requirements": True,
    },
    # How to treat IDs referenced in plan/tasks that spec.md does not define.
    "unknown_ids": "violation",  # violation | warning | ignore
    "features": {
        "exclude": [],  # glob patterns of feature directory names skipped by --all
    },
}

PASS = "pass"
VIOLATION = "violation"
WAIVED = "waived"
WARNING = "warning"

COVERED_WORDS = (
    "covered", "planned", "in scope", "in-scope", "inscope", "included", "addressed",
    "yes", "done", "implemented", "mapped", "ok",
)
PARTIAL_WORDS = ("partial", "partially")
DEFERRED_WORDS = (
    "deferred", "defer", "out of scope", "out-of-scope", "outofscope", "excluded",
    "descoped", "de-scoped", "postponed", "waived", "later", "not in scope", "won't do",
    "wont do", "dropped",
)
COVERED_GLYPHS = ("✅", "✔", "✓")  # check marks
DEFERRED_GLYPHS = ("⏸", "❌", "✖", "✗")


class ScopeGuardError(Exception):
    """Setup or usage problem (exit code 2)."""


# --------------------------------------------------------------------------- #
# Config                                                                        #
# --------------------------------------------------------------------------- #


def _strip_yaml_comment(line: str) -> str:
    out = []
    quote: Optional[str] = None
    prev = " "
    for ch in line:
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
            out.append(ch)
        elif ch == "#" and prev in (" ", "\t"):
            break
        else:
            out.append(ch)
        prev = ch
    return "".join(out).rstrip()


def _parse_yaml_scalar(raw: str) -> Any:
    value = raw.strip()
    if value == "":
        return None
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        items, buf, quote = [], [], None
        for ch in inner:
            if quote:
                buf.append(ch)
                if ch == quote:
                    quote = None
            elif ch in ("'", '"'):
                quote = ch
                buf.append(ch)
            elif ch == ",":
                items.append(_parse_yaml_scalar("".join(buf)))
                buf = []
            else:
                buf.append(ch)
        items.append(_parse_yaml_scalar("".join(buf)))
        return items
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    if len(value) >= 2 and value[0] == value[-1] == '"':
        inner = value[1:-1]
        return (
            inner.replace("\\\\", "\x00").replace('\\"', '"').replace("\\n", "\n")
            .replace("\\t", "\t").replace("\x00", "\\")
        )
    lowered = value.lower()
    if lowered in ("true", "yes", "on"):
        return True
    if lowered in ("false", "no", "off"):
        return False
    if lowered in ("null", "~"):
        return None
    if re.fullmatch(r"[-+]?\d+", value):
        return int(value)
    if re.fullmatch(r"[-+]?\d+\.\d*", value):
        return float(value)
    return value


def parse_simple_yaml(text: str) -> Dict[str, Any]:
    """Parse the YAML subset used by scopeGuard config files.

    Supports nested mappings (space indentation), block lists of scalars,
    inline lists, quoted/unquoted scalars and comments. Used only when PyYAML
    is not importable.
    """
    lines: List[Tuple[int, str]] = []
    for raw in text.replace("\t", "    ").splitlines():
        stripped = _strip_yaml_comment(raw)
        if not stripped.strip() or stripped.strip() in ("---", "..."):
            continue
        lines.append((len(stripped) - len(stripped.lstrip(" ")), stripped.strip()))

    root: Dict[str, Any] = {}
    stack: List[Tuple[int, Any]] = [(-1, root)]
    for index, (indent, content) in enumerate(lines):
        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if content.startswith("- ") or content == "-":
            if not isinstance(parent, list):
                raise ScopeGuardError(f"config: unexpected list item: {content!r}")
            parent.append(_parse_yaml_scalar(content[1:]))
            continue
        if ":" not in content:
            raise ScopeGuardError(f"config: cannot parse line: {content!r}")
        key, _, rest = content.partition(":")
        key = str(_parse_yaml_scalar(key))
        if not isinstance(parent, dict):
            raise ScopeGuardError(f"config: unexpected mapping key: {key!r}")
        if rest.strip():
            parent[key] = _parse_yaml_scalar(rest)
            continue
        nxt = lines[index + 1] if index + 1 < len(lines) else None
        if nxt is not None and nxt[0] > indent:
            child: Any = [] if (nxt[1].startswith("- ") or nxt[1] == "-") else {}
        elif nxt is not None and nxt[0] == indent and nxt[1].startswith("- "):
            child = []  # list items at the same indent as the key (valid YAML)
            parent[key] = child
            stack.append((indent - 1, child))
            continue
        else:
            parent[key] = None
            continue
        parent[key] = child
        stack.append((indent, child))
    return root


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_yaml_file(path: Path) -> Dict[str, Any]:
    text = read_text(path)
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text)
    except ImportError:
        data = parse_simple_yaml(text)
    except Exception as exc:  # yaml.YAMLError and friends
        raise ScopeGuardError(f"invalid YAML in {path}: {exc}")
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ScopeGuardError(f"config {path} must be a mapping")
    return data


def _as_bool(value: Any, name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in ("true", "yes", "on", "1", "false", "no", "off", "0"):
        return value.strip().lower() in ("true", "yes", "on", "1")
    raise ScopeGuardError(f"config: {name} must be true or false, got {value!r}")


def load_config(root: Path, explicit: Optional[str]) -> Tuple[Dict[str, Any], List[str]]:
    sources: List[str] = []
    config = copy.deepcopy(DEFAULT_CONFIG)
    user: Dict[str, Any] = {}
    paths: List[Path] = []
    if explicit:
        p = Path(explicit)
        if not p.is_absolute():
            p = Path.cwd() / p
        if not p.is_file():
            raise ScopeGuardError(f"config file not found: {explicit}")
        paths.append(p)
    else:
        for rel in (CONFIG_RELATIVE,) + CONFIG_LOCAL_RELATIVES:
            if (root / rel).is_file():
                paths.append(root / rel)
    for p in paths:
        user = _deep_merge(user, _load_yaml_file(p))
        sources.append(str(p))
    config = _deep_merge(config, user)

    # Unknown keys are errors (a misspelt key must not silently fall back to the default).
    allowed_top = set(DEFAULT_CONFIG) | {"remediation"}  # remediation: the v0.2 name, read below
    unknown = sorted(str(k) for k in set(user) - allowed_top)
    if unknown:
        raise ScopeGuardError(
            f"config: unknown setting(s) {', '.join(unknown)} - see config-template.yml for the settings scopeGuard reads"
        )
    for section in ("autocorrect", "ids", "spec", "plan", "tasks", "implement", "features"):
        value = user.get(section)
        if value is None:
            continue
        if not isinstance(value, dict):
            raise ScopeGuardError(f"config: {section} must be a mapping")
        bad = sorted(str(k) for k in set(value) - set(DEFAULT_CONFIG[section]))
        if bad:
            raise ScopeGuardError(f"config: {section}: unknown setting(s) {', '.join(bad)}")

    # v0.2 name for the iteration limit
    legacy = (user.get("remediation") or {}) if isinstance(user.get("remediation"), dict) else {}
    if "max_iterations" in legacy and "max_iterations" not in (user.get("autocorrect") or {}):
        config["autocorrect"]["max_iterations"] = legacy["max_iterations"]

    for env, key in (("SCOPEGUARD_MODE", "mode"), ("SCOPEGUARD_INTEGRATION", "integration")):
        if os.environ.get(env):
            config[key] = os.environ[env].strip()
    if os.environ.get("SCOPEGUARD_MAX_ITERATIONS"):
        config["autocorrect"]["max_iterations"] = os.environ["SCOPEGUARD_MAX_ITERATIONS"].strip()
    if os.environ.get("SCOPEGUARD_AUTOCORRECT"):
        config["autocorrect"]["enabled"] = os.environ["SCOPEGUARD_AUTOCORRECT"].strip()

    if config.get("mode") not in ("enforce", "report"):
        raise ScopeGuardError(f"config: mode must be 'enforce' or 'report', got {config.get('mode')!r}")
    if config.get("integration") not in INTEGRATIONS:
        raise ScopeGuardError(
            f"config: integration must be 'inline', 'hooks' or 'embedded', got {config.get('integration')!r}"
        )
    if not isinstance(config.get("autocorrect"), dict):
        raise ScopeGuardError("config: autocorrect must be a mapping with enabled and max_iterations")
    config["autocorrect"]["enabled"] = _as_bool(config["autocorrect"].get("enabled", True), "autocorrect.enabled")
    try:
        max_iterations = int(config["autocorrect"].get("max_iterations", 4))
    except (TypeError, ValueError):
        raise ScopeGuardError("config: autocorrect.max_iterations must be a whole number")
    if max_iterations < 1:
        raise ScopeGuardError("config: autocorrect.max_iterations must be at least 1 (use autocorrect.enabled: false to switch autocorrect off)")
    config["autocorrect"]["max_iterations"] = max_iterations
    for gate in ("plan", "tasks", "implement"):
        config[gate]["enabled"] = _as_bool(config[gate].get("enabled", True), f"{gate}.enabled")
    if config.get("unknown_ids") not in (VIOLATION, WARNING, "ignore"):
        raise ScopeGuardError("config: unknown_ids must be violation, warning or ignore")
    prefixes = config["ids"].get("requirement_prefixes") or []
    if isinstance(prefixes, str):
        prefixes = [prefixes]
    config["ids"]["requirement_prefixes"] = [str(p).strip().upper() for p in prefixes if str(p).strip()]
    story_key = str(config["ids"].get("story_key") or "US").strip().upper()
    if not re.fullmatch(r"[A-Z]{1,8}", story_key):
        raise ScopeGuardError(f"config: ids.story_key must be letters only, e.g. US or UC, got {story_key!r}")
    if story_key in config["ids"]["requirement_prefixes"]:
        raise ScopeGuardError(f"config: {story_key} is both ids.story_key and a requirement prefix")
    config["ids"]["story_key"] = story_key
    name = config["ids"].get("story_name")
    if name is None:
        name = "User Story" if story_key == "US" else ""
    config["ids"]["story_name"] = str(name).strip()
    if not config["ids"].get("story_pattern"):
        config["ids"]["story_pattern"] = default_story_pattern(story_key, config["ids"]["story_name"])
    try:
        re.compile(config["ids"]["story_pattern"])
    except re.error as exc:
        raise ScopeGuardError(f"config: invalid ids.story_pattern: {exc}")
    return config, sources


def _name_regex(name: str) -> str:
    return r"\s+".join(re.escape(w) for w in name.split())


def default_story_pattern(key: str, name: str) -> str:
    """Heading pattern for stories: 'User Story 1' / 'US1' (key US), or e.g. 'UC-001' / 'Use Case 1'."""
    alts = ([_name_regex(name)] if name else []) + [re.escape(key)]
    return r"(?:" + "|".join(alts) + r")\s*[-#:]?\s*(\d+)\b"


def inline_preset_installed(root: Path) -> bool:
    """True when the scopeguard-templates preset with the inline command wraps is installed and enabled."""
    preset = root / INLINE_PRESET_DIR
    if not all((preset / "commands" / f"{name}.md").is_file() for name in INLINE_COMMANDS):
        return False
    registry = root / ".specify" / "presets" / ".registry"
    if registry.is_file():
        try:
            entry = json.loads(read_text(registry)).get("presets", {}).get("scopeguard-templates")
            if isinstance(entry, dict) and entry.get("enabled") is False:
                return False
        except (ValueError, AttributeError):
            pass
    return True


def effective_integration(root: Path, config: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    """Return (integration actually in force, note). inline falls back to hooks without the preset."""
    wanted = config["integration"]
    if wanted == "embedded":
        notes = []
        if not (root / ".specify" / "extensions" / "archiguard" / "extension.yml").is_file():
            notes.append("integration is 'embedded' but archiGuard, the tool that runs the scope gate, is not installed, "
                         "so no scope gate runs - set integration: inline (with the scopeguard-templates preset) or hooks "
                         "in scopeguard-config.yml, then run configure")
        if inline_preset_installed(root):
            notes.append("integration is 'embedded' but the scopeguard-templates preset is installed; its steps are "
                         "skipped - remove it: specify preset remove scopeguard-templates")
        return wanted, ("; ".join(notes) or None)
    if wanted == "inline" and not inline_preset_installed(root):
        return "hooks", (
            "integration is 'inline' but the scopeguard-templates preset (v0.3.0+) is not installed, "
            "so the gates run through the hooks instead"
        )
    return wanted, None


# --------------------------------------------------------------------------- #
# Text helpers                                                                  #
# --------------------------------------------------------------------------- #


def read_text(path: Path) -> str:
    data = path.read_bytes()
    text = data.decode("utf-8-sig", errors="replace")
    # CRLF, doubled CR (CRLF re-converted by a tool) and lone CR all become LF.
    return re.sub(r"\r+\n", "\n", text).replace("\r", "\n")


_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)


def strip_html_comments(text: str) -> str:
    """Blank out HTML comments while keeping line numbers stable."""
    return _COMMENT_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text)


_HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)(?:\s+#+)?\s*$")


def heading(line: str) -> Optional[Tuple[int, str]]:
    m = _HEADING_RE.match(line)
    if not m:
        return None
    text = re.sub(r"(\*\*|__|`)", "", m.group(2)).strip()
    return len(m.group(1)), text


def clean_cell(cell: str) -> str:
    value = cell.strip()
    value = re.sub(r"(\*\*|__|`)", "", value)
    return value.strip()


def split_row(line: str) -> List[str]:
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|") and not body.endswith("\\|"):
        body = body[:-1]
    cells, buf = [], []
    i = 0
    while i < len(body):
        ch = body[i]
        if ch == "\\" and i + 1 < len(body) and body[i + 1] == "|":
            buf.append("|")
            i += 2
            continue
        if ch == "|":
            cells.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
        i += 1
    cells.append("".join(buf))
    return [c.strip() for c in cells]


_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")


# --------------------------------------------------------------------------- #
# IDs                                                                           #
# --------------------------------------------------------------------------- #


class IdScheme:
    """Knows how scope IDs look and how to normalize them."""

    def __init__(self, config: Dict[str, Any]):
        ids = config["ids"]
        self.key = str(ids.get("story_key") or "US").upper()
        name = ids.get("story_name")
        if name is None:
            name = "User Story" if self.key == "US" else ""
        self.name = str(name).strip()
        self.story_heading_re = re.compile(ids.get("story_pattern") or default_story_pattern(self.key, self.name), re.I)
        self.prefixes: List[str] = list(config["ids"]["requirement_prefixes"])
        prefix_alt = "|".join(re.escape(p) for p in sorted(self.prefixes, key=len, reverse=True))
        self.req_token_re = (
            re.compile(r"(?<![A-Za-z0-9_-])(" + prefix_alt + r")-(\d+)(?![A-Za-z0-9_])") if self.prefixes else None
        )
        key_re = re.escape(self.key)
        long_re = _name_regex(self.name) if self.name else None
        alts = ([long_re] if long_re else []) + [key_re]
        # Story tokens inside table cells: US1, US-1, US 1, User Story 1 (or UC-001, Use Case 1, ...)
        self.story_token_re = re.compile(r"(?<![A-Za-z0-9])(?:" + "|".join(alts) + r")\s*[-#]?\s*(\d+)(?![0-9])", re.I)
        # Story labels on task lines: [US1] / [US-1] / [US 1] (or [UC-001])
        self.story_label_re = re.compile(r"\[\s*" + key_re + r"\s*-?\s*(\d+)\s*\]", re.I)
        # Story in a tasks.md phase title: "Phase 3: User Story 1 - ..." / "US1" (or "UC-001")
        self.story_phase_re = re.compile(
            r"(?:" + ((long_re + "|") if long_re else "") + r"\b" + key_re + r")\s*-?\s*(\d+)\b", re.I)

    def story_key(self, number: str) -> str:
        return f"US{int(number)}" if self.key == "US" else f"{self.key}-{int(number)}"

    def story_display(self, number: str) -> str:
        """The ID as people write it: US1, or the key with the number as written (UC-001)."""
        return f"US{int(number)}" if self.key == "US" else f"{self.key}-{number}"

    @property
    def stories_label(self) -> str:
        if self.key == "US":
            return "user stories"
        return (self.name.lower() + "s") if self.name else f"stories ({self.key})"

    @property
    def label_example(self) -> str:
        return "[USn]" if self.key == "US" else f"[{self.key}-nnn]"

    @staticmethod
    def req_key(prefix: str, number: str) -> str:
        return f"{prefix.upper()}-{int(number)}"

    def reqs_in(self, text: str) -> List[Tuple[str, str]]:
        """Return (key, display) requirement IDs mentioned in text."""
        if not self.req_token_re:
            return []
        return [(self.req_key(m.group(1), m.group(2)), f"{m.group(1)}-{m.group(2)}") for m in self.req_token_re.finditer(text)]

    def stories_in_cell(self, text: str) -> List[Tuple[str, str]]:
        return [(self.story_key(m.group(1)), self.story_display(m.group(1))) for m in self.story_token_re.finditer(text)]

    def story_labels(self, text: str) -> List[Tuple[str, str]]:
        return [(self.story_key(m.group(1)), self.story_display(m.group(1))) for m in self.story_label_re.finditer(text)]

    def ids_in_cell(self, text: str) -> List[Tuple[str, str]]:
        found = self.stories_in_cell(text) + self.reqs_in(text)
        seen: Set[str] = set()
        out = []
        for key, display in found:
            if key not in seen:
                seen.add(key)
                out.append((key, display))
        return out


# --------------------------------------------------------------------------- #
# Model                                                                         #
# --------------------------------------------------------------------------- #


@dataclass
class ScopeItem:
    key: str
    display: str
    kind: str  # story | requirement
    title: str
    priority: Optional[str]
    line: int
    excerpt: str = ""  # the item's text in spec.md, for resolving it


@dataclass
class Finding:
    level: str  # violation | warning
    message: str
    location: Optional[str] = None
    item: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {"level": self.level, "message": self.message, "location": self.location, "item": self.item}


@dataclass
class SpecModel:
    path: Path
    items: Dict[str, ScopeItem]
    findings: List[Finding]
    stories_label: str = "user stories"
    story_key: str = "US"

    @property
    def stories(self) -> List[ScopeItem]:
        return [i for i in self.items.values() if i.kind == "story"]

    @property
    def requirements(self) -> List[ScopeItem]:
        return [i for i in self.items.values() if i.kind == "requirement"]


@dataclass
class CoverageRow:
    keys: List[Tuple[str, str]]
    state: str  # covered | partial | deferred | invalid | empty
    status_raw: str
    reference: str
    reason: str
    task_ids: List[str]
    line: int


@dataclass
class CoverageTable:
    found_section: bool
    section_title: Optional[str]
    rows: List[CoverageRow]
    findings: List[Finding]

    def index(self) -> Dict[str, List[CoverageRow]]:
        idx: Dict[str, List[CoverageRow]] = {}
        for row in self.rows:
            for key, _ in row.keys:
                idx.setdefault(key, []).append(row)
        return idx


@dataclass
class Task:
    task_id: str
    done: bool
    text: str
    line: int
    stories: Set[str] = field(default_factory=set)
    inherited_story: Optional[str] = None
    requirements: Set[str] = field(default_factory=set)
    displays: Dict[str, str] = field(default_factory=dict)


@dataclass
class TasksModel:
    path: Path
    tasks: Dict[str, Task]
    table: CoverageTable
    findings: List[Finding]


@dataclass
class ItemResult:
    item: ScopeItem
    verdict: str  # pass | violation | waived
    detail: str
    evidence: List[str] = field(default_factory=list)
    location: Optional[str] = None
    code: str = ""  # machine-readable reason: missing, open, no-reason, conflict, bad-status, ...

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.item.display,
            "code": self.code or self.verdict,
            "kind": self.item.kind,
            "title": self.item.title,
            "priority": self.item.priority,
            "verdict": self.verdict,
            "detail": self.detail,
            "evidence": self.evidence,
            "location": self.location,
            "spec_excerpt": self.item.excerpt if self.verdict == VIOLATION else None,
        }


@dataclass
class GateResult:
    gate: str
    feature_dir: Path
    spec: SpecModel
    items: List[ItemResult]
    findings: List[Finding]
    skeleton: List[str] = field(default_factory=list)
    skeleton_target: Optional[str] = None
    iteration: Optional[int] = None
    max_iterations: Optional[int] = None
    escalated: bool = False
    autocorrect: bool = True
    escalation_report: Optional[Path] = None
    history: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def violations(self) -> List[Any]:
        return [r for r in self.items if r.verdict == VIOLATION] + [f for f in self.findings if f.level == VIOLATION]

    @property
    def warnings(self) -> List[Finding]:
        return [f for f in self.findings if f.level == WARNING]

    @property
    def verdict(self) -> str:
        return "fail" if self.violations else "pass"

    def counts(self) -> Dict[str, Any]:
        passed = sum(1 for r in self.items if r.verdict == PASS)
        waived = sum(1 for r in self.items if r.verdict == WAIVED)
        violated = sum(1 for r in self.items if r.verdict == VIOLATION)
        in_scope = passed + violated
        return {
            "items": len(self.items),
            "pass": passed,
            "waived": waived,
            "violation_items": violated,
            "violations": len(self.violations),
            "warnings": len(self.warnings),
            "in_scope": in_scope,
            "coverage_pct": round(100.0 * passed / in_scope, 1) if in_scope else 100.0,
        }


# --------------------------------------------------------------------------- #
# Parsing                                                                       #
# --------------------------------------------------------------------------- #

_PRIORITY_RE = re.compile(r"\(\s*Priority\s*:\s*([A-Za-z0-9]+)\s*\)", re.I)


def parse_spec(path: Path, scheme: IdScheme, config: Dict[str, Any]) -> SpecModel:
    if not path.is_file():
        raise ScopeGuardError(f"spec.md not found: {path}")
    text = strip_html_comments(read_text(path))
    lines = text.split("\n")
    items: Dict[str, ScopeItem] = {}
    findings: List[Finding] = []
    rel = path.name

    def add(item: ScopeItem) -> None:
        if item.key in items:
            first = items[item.key]
            findings.append(Finding(
                VIOLATION,
                f"{item.display} is defined twice in spec.md (lines {first.line} and {item.line}); IDs must be unique",
                f"{rel}:{item.line}", item.display,
            ))
            return
        items[item.key] = item

    prefixes = scheme.prefixes
    req_bold_re = None
    req_plain_re = None
    req_table_re = None
    if prefixes:
        alt = "|".join(re.escape(p) for p in sorted(prefixes, key=len, reverse=True))
        lead = r"^\s*(?:[-*+]\s+|\d+[.)]\s+)?"
        # - **FR-001**: text   /   - **FR-001:** text   /   **FR-001** - text
        req_bold_re = re.compile(
            lead + r"(?:\*\*|__)\s*(" + alt + r")-(\d+)\s*[:.]?\s*(?:\*\*|__)\s*[:.\-\u2013\u2014]?\s*(.*)$"
        )
        # - FR-001: text   /   FR-001 - text
        req_plain_re = re.compile(lead + r"(" + alt + r")-(\d+)\s*[:\-\u2013\u2014]\s*(.*)$")
        # | FR-001 | text |
        req_table_re = re.compile(r"^\s*\|\s*(?:\*\*|__)?\s*(" + alt + r")-(\d+)\s*(?:\*\*|__)?\s*\|(.*)$")

    clarifications = 0
    for number, line in enumerate(lines, start=1):
        if "NEEDS CLARIFICATION" in line.upper():
            clarifications += 1
        h = heading(line)
        if h:
            level, title_text = h
            if level >= 2:
                m = scheme.story_heading_re.match(title_text)
                if m:
                    rest = title_text[m.end():]
                    priority_match = _PRIORITY_RE.search(rest)
                    priority = priority_match.group(1).upper() if priority_match else None
                    title = _PRIORITY_RE.sub("", rest)
                    title = title.strip().strip("-–—:|.").strip()
                    key = scheme.story_key(m.group(1))
                    add(ScopeItem(key, scheme.story_display(m.group(1)), "story", title, priority, number))
            continue
        if req_table_re is None:
            continue
        m = req_table_re.match(line)
        if m:
            cells = split_row(m.group(3))
            desc = clean_cell(cells[0]) if cells else ""
            key = scheme.req_key(m.group(1), m.group(2))
            add(ScopeItem(key, f"{m.group(1).upper()}-{m.group(2)}", "requirement", desc, None, number))
            continue
        m = req_bold_re.match(line) or req_plain_re.match(line)
        if m:
            key = scheme.req_key(m.group(1), m.group(2))
            desc = clean_cell(m.group(3))
            add(ScopeItem(key, f"{m.group(1).upper()}-{m.group(2)}", "requirement", desc, None, number))

    if config["spec"].get("require_stories", True) and not any(i.kind == "story" for i in items.values()):
        findings.append(Finding(
            VIOLATION,
            f"spec.md defines no {scheme.stories_label} (expected headings like "
            f"'### {(scheme.name + ' 1') if scheme.name else scheme.key + '-001'} - Title (Priority: P1)'); "
            "scope cannot be traced",
            rel,
        ))
    for item in items.values():
        if item.kind == "story" and re.search(r"\[[^\]]*title[^\]]*\]", item.title, re.I):
            findings.append(Finding(WARNING, f"{item.display} still has a template placeholder title: {item.title!r}", f"{rel}:{item.line}", item.display))
    if clarifications:
        findings.append(Finding(
            WARNING,
            f"spec.md still contains {clarifications} [NEEDS CLARIFICATION] marker(s); scope may change",
            rel,
        ))
    _attach_excerpts(items, lines)
    # Requirement mentions in spec that are never defined (e.g. 'see FR-099').
    defined = set(items)
    for number, line in enumerate(lines, start=1):
        for key, display in scheme.reqs_in(line):
            if key not in defined:
                findings.append(Finding(WARNING, f"spec.md mentions {display}, which it never defines", f"{rel}:{number}", display))
                defined.add(key)
    return SpecModel(path, items, findings, scheme.stories_label, scheme.key)


def _attach_excerpts(items: Dict[str, ScopeItem], lines: List[str], max_lines: int = 18) -> None:
    """Attach the spec text of each item: a story's section, a requirement's line."""
    for item in items.values():
        if item.kind == "requirement":
            item.excerpt = lines[item.line - 1].strip()
            continue
        start = item.line - 1
        h = heading(lines[start])
        level = h[0] if h else 3
        body: List[str] = [lines[start].strip()]
        for line in lines[start + 1:]:
            nh = heading(line)
            if nh and nh[0] <= level:
                break
            if line.strip() in ("---", "***", "___"):
                continue
            body.append(line.rstrip())
        while body and not body[-1].strip():
            body.pop()
        compact: List[str] = []
        for line in body:
            if not line.strip() and compact and not compact[-1].strip():
                continue
            compact.append(line)
        if len(compact) > max_lines:
            compact = compact[:max_lines] + ["[... see spec.md line %d]" % item.line]
        item.excerpt = "\n".join(compact)


def normalize_status(raw: str) -> str:
    value = clean_cell(raw)
    if not value:
        return "empty"
    lowered = value.lower()
    for glyph in COVERED_GLYPHS:
        if glyph in value:
            return "covered"
    for glyph in DEFERRED_GLYPHS:
        if glyph in value:
            return "deferred"
    letters = re.sub(r"[^a-z' -]", " ", lowered).strip()
    letters = re.sub(r"\s+", " ", letters)
    for word in PARTIAL_WORDS:
        if letters.startswith(word):
            return "partial"
    for word in DEFERRED_WORDS:
        if letters.startswith(word):
            return "deferred"
    for word in COVERED_WORDS:
        if letters == word or letters.startswith(word + " "):
            return "covered"
    return "invalid"


def _status_remainder(raw: str) -> str:
    """Text after the status keyword, e.g. 'deferred - phase 2' -> 'phase 2'."""
    value = clean_cell(raw)
    m = re.match(r"^\W*[A-Za-z' -]*?(deferred|out[ -]of[ -]scope|excluded|descoped|de-scoped|postponed|waived|dropped)\b\W*(.*)$", value, re.I)
    if m:
        return m.group(2).strip(" -:()–—")
    return ""


_TASK_ID_RE = re.compile(r"\bT\d{2,}\b")


def is_placeholder(value: str) -> bool:
    """True for template placeholders such as <where the plan handles it> or [TBD]."""
    v = value.strip()
    return bool(re.fullmatch(r"<[^<>]*>|\[[^\[\]]*\]|TBD|TODO|\?+|\.\.\.", v, re.I))


def _column_roles(header: List[str]) -> Dict[str, int]:
    names = [clean_cell(h).lower() for h in header]
    roles: Dict[str, int] = {}

    def claim(role: str, predicate) -> None:
        if role in roles:
            return
        for idx, name in enumerate(names):
            if idx in roles.values():
                continue
            if predicate(name):
                roles[role] = idx
                return

    claim("id", lambda n: bool(re.search(r"\bids?\b", n)) or n in ("item", "scope item", "story", "requirement", "story / requirement", "scope"))
    claim("status", lambda n: any(w in n for w in ("status", "decision", "coverage", "state", "verdict")))
    claim("tasks", lambda n: "task" in n)
    claim("reason", lambda n: any(w in n for w in ("reason", "rationale", "justification", "note", "comment", "why")))
    claim("reference", lambda n: any(w in n for w in ("plan", "where", "design", "reference", "section", "artifact", "how", "component", "addressed", "realized", "evidence")))
    claim("title", lambda n: any(w in n for w in ("title", "summary", "description", "name")))
    if "id" not in roles:
        roles["id"] = 0
    return roles


def parse_coverage_table(
    lines: List[str], section_name: str, scheme: IdScheme, rel: str, warn_if_empty: bool = True
) -> CoverageTable:
    """Parse markdown tables under the first heading that contains section_name."""
    findings: List[Finding] = []
    start = None
    level = 0
    title = None
    target = section_name.strip().lower()
    for idx, line in enumerate(lines):
        h = heading(line)
        if h and target in h[1].lower():
            start, level, title = idx + 1, h[0], h[1]
            break
    if start is None:
        return CoverageTable(False, None, [], findings)
    end = len(lines)
    for idx in range(start, len(lines)):
        h = heading(lines[idx])
        if h and h[0] <= level:
            end = idx
            break

    rows: List[CoverageRow] = []
    idx = start
    while idx < end:
        line = lines[idx]
        if line.strip().startswith("|") and idx + 1 < end and _SEPARATOR_RE.match(lines[idx + 1]):
            header = split_row(line)
            roles = _column_roles(header)
            idx += 2
            while idx < end and lines[idx].strip().startswith("|"):
                cells = split_row(lines[idx])
                number = idx + 1

                def cell(role: str) -> str:
                    pos = roles.get(role)
                    return cells[pos] if pos is not None and pos < len(cells) else ""

                id_cell = cell("id")
                keys = scheme.ids_in_cell(clean_cell(id_cell))
                if not keys:
                    if clean_cell(id_cell) and not re.fullmatch(r"\[.*\]|\.\.\.|-+|", clean_cell(id_cell)):
                        findings.append(Finding(WARNING, f"row without a recognizable scope ID: {clean_cell(id_cell)!r}", f"{rel}:{number}"))
                    idx += 1
                    continue
                status_raw = cell("status")
                state = normalize_status(status_raw) if "status" in roles else "covered"
                reason = clean_cell(cell("reason"))
                if not reason and state == "deferred":
                    reason = _status_remainder(status_raw)
                rows.append(CoverageRow(
                    keys=keys,
                    state=state,
                    status_raw=clean_cell(status_raw),
                    reference=clean_cell(cell("reference")),
                    reason=reason,
                    task_ids=_TASK_ID_RE.findall(cell("tasks")) if "tasks" in roles else _TASK_ID_RE.findall(cell("reference")),
                    line=number,
                ))
                idx += 1
            continue
        idx += 1
    if not rows and warn_if_empty:
        findings.append(Finding(WARNING, f"section '{title}' has no table rows with scope IDs", rel))
    return CoverageTable(True, title, rows, findings)


_TASK_LINE_RE = re.compile(r"^\s*[-*+]\s*\[([ xX])\]\s*(T\d+)\b(.*)$")


def parse_tasks(path: Path, scheme: IdScheme, config: Dict[str, Any]) -> TasksModel:
    if not path.is_file():
        raise ScopeGuardError(f"tasks.md not found: {path}")
    text = strip_html_comments(read_text(path))
    lines = text.split("\n")
    rel = path.name
    tasks: Dict[str, Task] = {}
    findings: List[Finding] = []
    inherit = bool(config["tasks"].get("inherit_story_from_phase", True))
    section_name = str(config["tasks"].get("section") or "Scope Coverage").lower()

    story_stack: List[Tuple[int, Optional[str]]] = []  # (heading level, story key)
    in_coverage_section = False
    coverage_level = 0
    for number, line in enumerate(lines, start=1):
        h = heading(line)
        if h:
            level, title = h
            if in_coverage_section and level <= coverage_level:
                in_coverage_section = False
            if section_name in title.lower():
                in_coverage_section, coverage_level = True, level
            while story_stack and story_stack[-1][0] >= level:
                story_stack.pop()
            m = scheme.story_phase_re.search(title)
            if m:
                story_stack.append((level, scheme.story_key(m.group(1))))
            continue
        if in_coverage_section:
            continue
        m = _TASK_LINE_RE.match(line)
        if not m:
            continue
        task_id = m.group(2).upper()
        body = m.group(3)
        task = Task(task_id=task_id, done=m.group(1).lower() == "x", text=body.strip(), line=number)
        for key, display in scheme.story_labels(body):
            task.stories.add(key)
            task.displays[key] = display
        if not task.stories and inherit:
            current = next((s for _, s in reversed(story_stack) if s), None)
            if current:
                task.inherited_story = current
        for key, display in scheme.reqs_in(body):
            task.requirements.add(key)
            task.displays[key] = display
        if task_id in tasks:
            findings.append(Finding(VIOLATION, f"task ID {task_id} is used twice (lines {tasks[task_id].line} and {number})", f"{rel}:{number}"))
            continue
        tasks[task_id] = task

    table = parse_coverage_table(lines, str(config["tasks"].get("section") or "Scope Coverage"), scheme, rel, warn_if_empty=False)
    return TasksModel(path, tasks, table, findings + table.findings)


# --------------------------------------------------------------------------- #
# Gates                                                                         #
# --------------------------------------------------------------------------- #


def _unknown_finding(config: Dict[str, Any], display: str, where: str, location: str) -> Optional[Finding]:
    level = config.get("unknown_ids", VIOLATION)
    if level == "ignore":
        return None
    return Finding(level, f"{where} references {display}, which spec.md does not define (renumbered, invented or stale scope)", location, display)


def _skeleton_row(item: ScopeItem, status: str = "covered", ref: str = "<where the plan handles it>") -> str:
    title = item.title or ""
    if item.priority:
        title = f"{title} ({item.priority})" if title else f"({item.priority})"
    title = title.replace("|", "\\|")
    if len(title) > 70:
        title = title[:67] + "..."
    return f"| {item.display} | {title} | {status} | {ref} | |"


def plan_skeleton_header() -> List[str]:
    return [
        "| ID | Title | Status | Plan reference | Reason (required if deferred) |",
        "|----|-------|--------|----------------|-------------------------------|",
    ]


def tasks_skeleton_header() -> List[str]:
    return [
        "| ID | Title | Status | Tasks | Reason (required if deferred) |",
        "|----|-------|--------|-------|-------------------------------|",
    ]


def traced_items(spec: SpecModel, include_requirements: bool) -> List[ScopeItem]:
    return [i for i in spec.items.values() if i.kind == "story" or include_requirements]


def load_plan_table(feature_dir: Path, scheme: IdScheme, config: Dict[str, Any]) -> Tuple[Optional[CoverageTable], List[str]]:
    plan_path = feature_dir / "plan.md"
    if not plan_path.is_file():
        return None, []
    lines = strip_html_comments(read_text(plan_path)).split("\n")
    return parse_coverage_table(lines, str(config["plan"].get("section") or "Scope Coverage"), scheme, "plan.md"), lines


def gate_plan(feature_dir: Path, spec: SpecModel, scheme: IdScheme, config: Dict[str, Any]) -> GateResult:
    cfg = config["plan"]
    plan_path = feature_dir / "plan.md"
    if not plan_path.is_file():
        raise ScopeGuardError(f"plan.md not found in {feature_dir} - run the plan phase first")
    table, plan_lines = load_plan_table(feature_dir, scheme, config)
    assert table is not None
    findings: List[Finding] = list(spec.findings) + list(table.findings)
    results: List[ItemResult] = []
    section = cfg.get("section") or "Scope Coverage"
    index = table.index()
    mention_mode = not table.found_section and not cfg.get("require_section", True)
    if not table.found_section and cfg.get("require_section", True):
        findings.append(Finding(
            VIOLATION,
            f"plan.md has no '## {section}' section; the plan must account for every user story and requirement "
            f"(install the scopeguard preset, or add the table shown below)",
            "plan.md",
        ))
    mentions: Set[str] = set()
    if mention_mode:
        for line in plan_lines:
            for key, _ in scheme.stories_in_cell(line) + scheme.reqs_in(line):
                mentions.add(key)

    missing: List[ScopeItem] = []
    for item in traced_items(spec, bool(cfg.get("check_requirements", True))):
        rows = index.get(item.key, [])
        if mention_mode:
            if item.key in mentions:
                results.append(ItemResult(item, PASS, "mentioned in plan.md"))
            else:
                results.append(ItemResult(item, VIOLATION, "not mentioned anywhere in plan.md", code="missing"))
                missing.append(item)
            continue
        if not rows:
            results.append(ItemResult(item, VIOLATION, f"missing from plan.md '{section}' - silently dropped from scope", code="missing"))
            missing.append(item)
            continue
        states = {r.state for r in rows}
        location = f"plan.md:{rows[0].line}"
        if "deferred" in states and states & {"covered", "partial"}:
            results.append(ItemResult(item, VIOLATION, "conflicting rows: listed both as covered and as deferred", location=location, code="conflict"))
            continue
        row = rows[0]
        if row.state in ("covered", "partial"):
            if is_placeholder(row.reference):
                results.append(ItemResult(item, VIOLATION, f"Plan reference is still a placeholder ({row.reference}); say where the plan handles it", location=location, code="placeholder"))
                continue
            if cfg.get("require_reference_for_covered") and not row.reference:
                results.append(ItemResult(item, VIOLATION, "marked covered but the plan reference cell is empty", location=location, code="no-reference"))
                continue
            detail = "covered" + (f" -> {row.reference}" if row.reference else "")
            if row.state == "partial":
                findings.append(Finding(WARNING, f"{item.display} is only partially covered in plan.md", location, item.display))
                detail = "partially covered" + (f" -> {row.reference}" if row.reference else "")
            elif not row.reference:
                findings.append(Finding(WARNING, f"{item.display} is marked covered without saying where the plan handles it", location, item.display))
            results.append(ItemResult(item, PASS, detail, location=location))
        elif row.state == "deferred":
            if not row.reason and cfg.get("require_reason_for_waiver", True):
                results.append(ItemResult(item, VIOLATION, "deferred without a reason (a waiver must say why)", location=location, code="no-reason"))
            else:
                results.append(ItemResult(item, WAIVED, f"deferred: {row.reason}" if row.reason else "deferred", location=location))
        elif row.state == "empty":
            results.append(ItemResult(item, VIOLATION, "row has an empty status (use covered or deferred)", location=location, code="bad-status"))
        else:
            results.append(ItemResult(item, VIOLATION, f"unrecognized status {row.status_raw!r} (use covered or deferred)", location=location, code="bad-status"))

    for row in table.rows:
        for key, display in row.keys:
            if key not in spec.items:
                finding = _unknown_finding(config, display, "plan.md Scope Coverage", f"plan.md:{row.line}")
                if finding:
                    findings.append(finding)

    result = GateResult("plan", feature_dir, spec, results, findings)
    if missing:
        result.skeleton_target = f'plan.md "## {section}"'
        result.skeleton = ([] if table.found_section else [f"## {section}", ""] + plan_skeleton_header()) + [
            _skeleton_row(i) for i in missing
        ]
    return result


def _plan_waivers(feature_dir: Path, scheme: IdScheme, config: Dict[str, Any]) -> Dict[str, CoverageRow]:
    table, _ = load_plan_table(feature_dir, scheme, config)
    if not table:
        return {}
    waivers = {}
    for row in table.rows:
        if row.state == "deferred":
            for key, _ in row.keys:
                waivers[key] = row
    return waivers


def carriers(item: ScopeItem, model: TasksModel) -> List[Task]:
    out = []
    for task in model.tasks.values():
        if item.kind == "story":
            if item.key in task.stories or (not task.stories and task.inherited_story == item.key):
                out.append(task)
        elif item.key in task.requirements:
            out.append(task)
    return out


def gate_tasks(feature_dir: Path, spec: SpecModel, scheme: IdScheme, config: Dict[str, Any]) -> GateResult:
    cfg = config["tasks"]
    tasks_path = feature_dir / "tasks.md"
    model = parse_tasks(tasks_path, scheme, config)
    findings: List[Finding] = list(spec.findings) + list(model.findings)
    plan_waivers = _plan_waivers(feature_dir, scheme, config)
    table_index = model.table.index()
    results: List[ItemResult] = []
    missing: List[ScopeItem] = []

    for item in traced_items(spec, bool(cfg.get("check_requirements", True))):
        carried = carriers(item, model)
        rows = table_index.get(item.key, [])
        mapped = [t for r in rows for t in r.task_ids if t in model.tasks]
        task_ids = sorted({t.task_id for t in carried} | set(mapped), key=lambda s: int(s[1:]))
        waiver = plan_waivers.get(item.key)
        if waiver is not None:
            reason = waiver.reason or "no reason given"
            if task_ids:
                findings.append(Finding(WARNING, f"{item.display} is deferred in plan.md but tasks.md still carries it ({', '.join(task_ids)})", "tasks.md", item.display))
            results.append(ItemResult(item, WAIVED, f"deferred in plan: {reason}", evidence=task_ids, location=f"plan.md:{waiver.line}"))
            continue
        if task_ids:
            results.append(ItemResult(item, PASS, f"carried by {', '.join(task_ids)}", evidence=task_ids))
            continue
        deferred_row = next((r for r in rows if r.state == "deferred"), None)
        if deferred_row is not None:
            if not deferred_row.reason and cfg.get("require_reason_for_waiver", True):
                results.append(ItemResult(item, VIOLATION, "deferred in tasks.md without a reason", location=f"tasks.md:{deferred_row.line}", code="no-reason"))
            else:
                results.append(ItemResult(item, WAIVED, f"deferred in tasks: {deferred_row.reason or 'no reason given'}", location=f"tasks.md:{deferred_row.line}"))
            continue
        if item.kind == "story":
            detail = f"no task carries {item.display} (expected tasks labelled [{item.display}])"
        else:
            detail = f"no task references {item.display} (mention it in a task or map it in the '{cfg.get('section')}' table)"
        results.append(ItemResult(item, VIOLATION, detail, code="missing"))
        missing.append(item)

    # Unknown story labels and requirement IDs.
    for task in model.tasks.values():
        for key in sorted(task.stories | task.requirements):
            if key not in spec.items:
                finding = _unknown_finding(config, task.displays.get(key, key), f"task {task.task_id}", f"tasks.md:{task.line}")
                if finding:
                    findings.append(finding)
        if task.inherited_story and task.inherited_story not in spec.items:
            finding = _unknown_finding(config, task.inherited_story, f"task {task.task_id} (via its phase heading)", f"tasks.md:{task.line}")
            if finding:
                findings.append(finding)
    for row in model.table.rows:
        for key, display in row.keys:
            if key not in spec.items:
                finding = _unknown_finding(config, display, "tasks.md Scope Coverage", f"tasks.md:{row.line}")
                if finding:
                    findings.append(finding)
        for task_id in row.task_ids:
            if task_id not in model.tasks:
                findings.append(Finding(VIOLATION, f"Scope Coverage row maps {', '.join(d for _, d in row.keys)} to {task_id}, which is not a task in tasks.md", f"tasks.md:{row.line}"))

    result = GateResult("tasks", feature_dir, spec, results, findings)
    if missing:
        result.skeleton_target = "tasks.md (add tasks, or rows in its Scope Coverage table)"
        lines = []
        for item in missing:
            if item.kind == "story":
                lines.append(f"- [ ] T### [{item.display}] <task that delivers {item.display}: {item.title}>")
            else:
                lines.append(f"- [ ] T### [{item.display}] <task that implements {item.display}> ({item.display})")
        result.skeleton = lines
    return result


def gate_implement(feature_dir: Path, spec: SpecModel, scheme: IdScheme, config: Dict[str, Any]) -> GateResult:
    cfg = config["implement"]
    model = parse_tasks(feature_dir / "tasks.md", scheme, config)
    findings: List[Finding] = list(spec.findings) + [f for f in model.findings if f.level == VIOLATION]
    plan_waivers = _plan_waivers(feature_dir, scheme, config)
    table_index = model.table.index()
    results: List[ItemResult] = []
    for item in traced_items(spec, bool(cfg.get("check_requirements", True))):
        if item.key in plan_waivers:
            results.append(ItemResult(item, WAIVED, f"deferred in plan: {plan_waivers[item.key].reason or 'no reason'}"))
            continue
        rows = table_index.get(item.key, [])
        carried = {t.task_id: t for t in carriers(item, model)}
        for row in rows:
            for task_id in row.task_ids:
                if task_id in model.tasks:
                    carried[task_id] = model.tasks[task_id]
        if not carried:
            deferred_row = next((r for r in rows if r.state == "deferred"), None)
            if deferred_row is not None:
                results.append(ItemResult(item, WAIVED, f"deferred in tasks: {deferred_row.reason or 'no reason'}"))
            else:
                results.append(ItemResult(item, VIOLATION, "no task carries this item, so it cannot have been implemented", code="missing"))
            continue
        ordered = sorted(carried.values(), key=lambda t: int(t.task_id[1:]))
        open_tasks = [t.task_id for t in ordered if not t.done]
        evidence = [t.task_id for t in ordered]
        if open_tasks:
            results.append(ItemResult(item, VIOLATION, f"{len(open_tasks)} of {len(ordered)} tasks still open: {', '.join(open_tasks)}", evidence=evidence, code="open"))
        else:
            results.append(ItemResult(item, PASS, f"all {len(ordered)} tasks done", evidence=evidence))
    return GateResult("implement", feature_dir, spec, results, findings)


# --------------------------------------------------------------------------- #
# Feature resolution                                                            #
# --------------------------------------------------------------------------- #


def find_project_root(explicit: Optional[str]) -> Path:
    if explicit:
        root = Path(explicit).resolve()
        if not root.is_dir():
            raise ScopeGuardError(f"--root is not a directory: {explicit}")
        return root
    env_root = os.environ.get("SPECIFY_INIT_DIR")
    if env_root and Path(env_root).is_dir():
        return Path(env_root).resolve()
    current = Path.cwd().resolve()
    for candidate in [current] + list(current.parents):
        if (candidate / ".specify").is_dir():
            return candidate
    return current


def _git_branch(root: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(root), capture_output=True, text=True, timeout=10,
        )
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _feature_dirs(root: Path) -> List[Path]:
    specs = root / "specs"
    if not specs.is_dir():
        return []
    return sorted(d for d in specs.iterdir() if d.is_dir() and (d / "spec.md").is_file())


def resolve_feature_dirs(root: Path, feature_dir: Optional[str], all_features: bool, config: Dict[str, Any]) -> List[Path]:
    if feature_dir:
        p = Path(feature_dir)
        if not p.is_absolute():
            p = (Path.cwd() / p) if (Path.cwd() / p).exists() else (root / p)
        p = p.resolve()
        if not p.is_dir():
            raise ScopeGuardError(f"feature directory not found: {feature_dir}")
        return [p]
    if all_features:
        excludes = [str(x) for x in (config.get("features", {}).get("exclude") or [])]
        dirs = [d for d in _feature_dirs(root) if not any(fnmatch.fnmatch(d.name, pat) for pat in excludes)]
        if not dirs:
            raise ScopeGuardError(f"no feature directories with spec.md under {root / 'specs'}")
        return dirs
    env_dir = os.environ.get("SPECIFY_FEATURE_DIRECTORY", "")
    if env_dir:
        p = Path(env_dir)
        return [(p if p.is_absolute() else root / p).resolve()]
    feature_json = root / ".specify" / "feature.json"
    if feature_json.is_file():
        try:
            data = json.loads(read_text(feature_json))
            stored = data.get("feature_directory") if isinstance(data, dict) else None
        except ValueError:
            stored = None
        if stored:
            p = Path(stored)
            p = (p if p.is_absolute() else root / p).resolve()
            if p.is_dir():
                return [p]
    candidates = _feature_dirs(root)
    branch = os.environ.get("SPECIFY_FEATURE", "") or _git_branch(root)
    if branch:
        leaf = branch.split("/")[-1]
        for d in candidates:
            if d.name == leaf:
                return [d]
        prefix = re.match(r"^(\d{3,}|\d{8}-\d{6})-", leaf)
        if prefix:
            matches = [d for d in candidates if d.name.startswith(prefix.group(1) + "-")]
            if len(matches) == 1:
                return matches
    if len(candidates) == 1:
        return candidates
    if not candidates:
        raise ScopeGuardError(f"no feature found: {root / 'specs'} has no directory containing spec.md")
    names = ", ".join(d.name for d in candidates[:8])
    raise ScopeGuardError(
        "cannot tell which feature to check (no SPECIFY_FEATURE_DIRECTORY, .specify/feature.json or matching branch). "
        f"Pass --feature-dir specs/<feature> or --all. Features: {names}"
    )


def rel_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


# --------------------------------------------------------------------------- #
# Rendering                                                                     #
# --------------------------------------------------------------------------- #

MARK = {PASS: "[PASS]  ", VIOLATION: "[FAIL]  ", WAIVED: "[WAIVED]", WARNING: "[WARN]  "}


def _item_label(item: ScopeItem) -> str:
    title = item.title or ""
    if item.priority:
        title = f"{title} ({item.priority})".strip()
    if len(title) > 60:
        title = title[:57] + "..."
    return f"{item.display:<8} {title}".rstrip()


def render_gate_text(result: GateResult, root: Path, verbose: bool) -> str:
    out: List[str] = []
    spec = result.spec
    out.append(f"scopeGuard {__version__} | gate: {result.gate} | feature: {rel_path(result.feature_dir, root)}")
    out.append(f"spec scope: {len(spec.stories)} {spec.stories_label}, {len(spec.requirements)} requirements")
    out.append("")
    shown = [r for r in result.items if verbose or r.verdict != PASS]
    for r in shown:
        loc = f"  ({r.location})" if r.location and r.verdict != PASS else ""
        out.append(f"  {MARK[r.verdict]} {_item_label(r.item)}")
        out.append(f"             -> {r.detail}{loc}")
    hidden = len(result.items) - len(shown)
    if hidden:
        out.append(f"  {MARK[PASS]} {hidden} item(s) accounted for (use --verbose to list)")
    other = [f for f in result.findings if f.level == VIOLATION]
    if other:
        out.append("")
        out.append("Other violations:")
        for f in other:
            out.append(f"  {MARK[VIOLATION]} {f.message}" + (f"  ({f.location})" if f.location else ""))
    if result.warnings:
        out.append("")
        out.append("Warnings:")
        for f in result.warnings:
            out.append(f"  {MARK[WARNING]} {f.message}" + (f"  ({f.location})" if f.location else ""))
    c = result.counts()
    out.append("")
    out.append(
        f"RESULT: {result.verdict.upper()} | {c['violations']} violation(s), {c['pass']} pass, {c['waived']} waived, "
        f"{c['warnings']} warning(s) | coverage {c['pass']}/{c['in_scope']} in-scope items ({c['coverage_pct']}%)"
    )
    if result.skeleton:
        out.append("")
        out.append(f"To fix, account for each missing item in {result.skeleton_target}:")
        out.extend("  " + line for line in result.skeleton)
    if result.verdict == "fail" and (result.iteration is not None or verbose):
        to_resolve = [r for r in result.items if r.verdict == VIOLATION]
        if to_resolve:
            out.append("")
            out.append("RESOLVE - each item below with its text from spec.md:")
            for r in to_resolve:
                out.append(f"  {r.item.display} [{r.code or 'violation'}] {r.detail}")
                for line in (r.item.excerpt or "").split("\n"):
                    out.append(f"      > {line}" if line.strip() else "      >")
    if result.iteration is not None:
        out.append("")
        out.append(_iteration_line(result, root))
    return "\n".join(out)


def _iteration_line(result: GateResult, root: Path) -> str:
    it, mx = result.iteration, result.max_iterations
    if result.verdict == "pass":
        return f"ITERATION {it} of {mx}: PASS - nothing left to resolve."
    if result.escalated and not result.autocorrect:
        report = rel_path(result.escalation_report, root) if result.escalation_report else "(not written)"
        return (
            "AUTOCORRECT OFF (autocorrect.enabled: false): the gate does not fix anything. Report the "
            f"violations above to the user (summary in {report}) and stop the calling command; "
            "do not continue as if it succeeded."
        )
    if result.escalated:
        report = rel_path(result.escalation_report, root) if result.escalation_report else "(not written)"
        return (
            f"ESCALATE: still failing after {it} of {mx} resolution iterations. STOP resolving. "
            f"Complete the TODO(agent) fields in {report} and report the problem to the user; "
            f"do not continue the calling command as if it succeeded."
        )
    return (
        f"ITERATION {it} of {mx} used: resolve every item above in the artifact, then re-run this gate "
        f"with --iteration {it + 1}."
    )


def gate_to_dict(result: GateResult, root: Path) -> Dict[str, Any]:
    return {
        "gate": result.gate,
        "feature_dir": rel_path(result.feature_dir, root),
        "verdict": result.verdict,
        "summary": result.counts(),
        "items": [r.to_dict() for r in result.items],
        "findings": [f.to_dict() for f in result.findings],
        "fix_target": result.skeleton_target,
        "fix_skeleton": result.skeleton,
        "iteration": result.iteration,
        "max_iterations": result.max_iterations,
        "next_iteration": (result.iteration + 1) if (result.iteration is not None and result.verdict == "fail" and not result.escalated) else None,
        "escalated": result.escalated,
        "escalation_report": rel_path(result.escalation_report, root) if result.escalation_report else None,
    }


def render_gate_markdown(result: GateResult, root: Path) -> str:
    c = result.counts()
    icon = "PASS" if result.verdict == "pass" else "FAIL"
    out = [
        f"### scopeGuard - {result.gate} gate - `{rel_path(result.feature_dir, root)}` - **{icon}**",
        "",
        f"{c['violations']} violation(s) | {c['pass']} pass | {c['waived']} waived | {c['warnings']} warning(s) | "
        f"coverage {c['pass']}/{c['in_scope']} ({c['coverage_pct']}%)",
        "",
        "| ID | Title | Verdict | Detail |",
        "|----|-------|---------|--------|",
    ]
    for r in result.items:
        title = (r.item.title or "").replace("|", "\\|")
        out.append(f"| {r.item.display} | {title} | {r.verdict} | {r.detail.replace('|', '/')} |")
    extra = [f for f in result.findings]
    if extra:
        out.append("")
        for f in extra:
            out.append(f"- **{f.level}**: {f.message}" + (f" (`{f.location}`)" if f.location else ""))
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------- #
# Resolution loop: history and escalation                                       #
# --------------------------------------------------------------------------- #


def _open_ids(result: GateResult) -> List[str]:
    ids = [r.item.display for r in result.items if r.verdict == VIOLATION]
    ids += [f.item or (f.location or "general") for f in result.findings if f.level == VIOLATION]
    return ids


def update_history(result: GateResult) -> List[Dict[str, Any]]:
    """Record this iteration in <feature>/.scopeguard/history-<gate>.json (reset at iteration 0)."""
    from datetime import datetime

    path = result.feature_dir / ".scopeguard" / f"history-{result.gate}.json"
    entries: List[Dict[str, Any]] = []
    if result.iteration and path.is_file():
        try:
            data = json.loads(read_text(path))
            entries = [e for e in data.get("iterations", []) if isinstance(e, dict) and e.get("iteration", -1) < result.iteration]
        except (ValueError, AttributeError):
            entries = []
    entries.append({
        "iteration": result.iteration,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "verdict": result.verdict,
        "violations": len(result.violations),
        "open": _open_ids(result),
    })
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"gate": result.gate, "iterations": entries}, indent=2) + "\n", encoding="utf-8")
    return entries


def escalation_path(result: GateResult) -> Path:
    return result.feature_dir / f"scopeguard-escalation-{result.gate}.md"


def render_escalation(result: GateResult, root: Path) -> str:
    from datetime import datetime

    unresolved = [r for r in result.items if r.verdict == VIOLATION]
    other = [f for f in result.findings if f.level == VIOLATION]
    artifact = {"plan": "plan.md", "tasks": "tasks.md", "implement": "tasks.md"}.get(result.gate, "the artifact")
    if not result.autocorrect:
        outcome = (
            f"{len(unresolved)} scope item(s) missing; autocorrect is off (autocorrect.enabled: false), "
            f"so nothing was resolved ({datetime.now().strftime('%Y-%m-%d %H:%M')})"
        )
        intro = (
            f"The {result.gate} gate found the gaps below and, with autocorrect switched off, stopped without "
            f"changing anything. Fix `{{artifact}}` yourself (or switch autocorrect on in "
            "scopeguard-config.yml) and run the command again."
        )
    else:
        outcome = (
            f"unresolved after {result.iteration} of {result.max_iterations} resolution iterations "
            f"({datetime.now().strftime('%Y-%m-%d %H:%M')})"
        )
        intro = (
            f"The agent could not bring every scope item into the {result.gate} artifact. Each item below says "
            "what was tried, what blocks it and which decision is needed. Fix the blocker (or take the "
            "decision), then run the gate again."
        )
    out = [
        f"# scopeGuard escalation: {result.gate} gate",
        "",
        f"- **Feature**: `{rel_path(result.feature_dir, root)}`",
        f"- **Result**: {outcome}",
        f"- **Still open**: {len(unresolved)} scope item(s), {len(other)} other violation(s)",
        f"- **Artifact being resolved**: `{artifact}`",
        "",
        intro.replace("{artifact}", artifact),
        "",
    ]
    if result.history:
        out += ["## Iteration history", "", "| Iteration | Violations | Open items |", "|---|---|---|"]
        for entry in result.history:
            out.append(f"| {entry.get('iteration')} | {entry.get('violations')} | {', '.join(entry.get('open') or []) or '-'} |")
        out.append("")
    if unresolved:
        out += ["## Unresolved items", ""]
        for r in unresolved:
            first_open = next((e.get("iteration") for e in result.history if r.item.display in (e.get("open") or [])), result.iteration)
            title = r.item.title + (f" ({r.item.priority})" if r.item.priority else "")
            out += [
                f"### {r.item.display} - {title}",
                "",
                f"- **Problem**: {r.detail}" + (f" (`{r.location}`)" if r.location else ""),
                f"- **Open since**: iteration {first_open}",
                f"- **Spec text** (spec.md:{r.item.line}):",
                "",
            ]
            out += [f"  > {line}" if line.strip() else "  >" for line in (r.item.excerpt or "").split("\n")]
            if not result.autocorrect:
                out.append("")
                continue
            out += [
                "",
                "- **Attempted**: TODO(agent): what was changed in each iteration to include this item",
                "- **Blocker**: TODO(agent): why it could not be included (missing information, conflict with the "
                "constitution or another requirement, technical constraint, unclear acceptance criteria, ...)",
                "- **Decision needed**: TODO(agent): the concrete choice for the user (provide X, approve deferring "
                "with reason Y, change the spec, accept a partial design, ...)",
                "",
            ]
    if other:
        out += ["## Other violations", ""]
        for f in other:
            out.append(f"- {f.message}" + (f" (`{f.location}`)" if f.location else ""))
        if result.autocorrect:
            out += ["", "- **Blocker / decision needed**: TODO(agent)", ""]
    return "\n".join(out).rstrip() + "\n"


def apply_iteration(result: GateResult, iteration: int, max_iterations: int, root: Path, autocorrect: bool = True) -> None:
    result.autocorrect = autocorrect
    if not autocorrect:
        max_iterations = 0  # report and stop at the first failing check
    result.iteration = iteration
    result.max_iterations = max_iterations
    result.history = update_history(result)
    report = escalation_path(result)
    if result.verdict == "fail" and iteration >= max_iterations:
        result.escalated = True
        with open(report, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(render_escalation(result, root))
        result.escalation_report = report
    elif result.verdict == "pass" and report.is_file():
        report.unlink()  # a stale problem report from an earlier escalation


# --------------------------------------------------------------------------- #
# configure: apply the config to Spec Kit's hook registry                       #
# --------------------------------------------------------------------------- #

HOOK_GATES = {
    # (event, command) -> gate whose enabled flag also applies
    ("before_plan", "speckit.scopeguard.inventory"): "plan",
    ("after_plan", "speckit.scopeguard.plan"): "plan",
    ("before_tasks", "speckit.scopeguard.inventory"): "tasks",
    ("after_tasks", "speckit.scopeguard.tasks"): "tasks",
    ("after_implement", "speckit.scopeguard.implement"): "implement",
}


def desired_hook_states(integration: str, config: Dict[str, Any]) -> Dict[Tuple[str, str], bool]:
    states = {}
    for (event, command), gate in HOOK_GATES.items():
        enabled = bool(config[gate].get("enabled", True)) and integration != "embedded"
        if gate in ("plan", "tasks"):
            enabled = enabled and integration == "hooks"
        states[(event, command)] = enabled
    return states


def _scalar(value: str) -> str:
    return value.strip().strip("'\"")


def set_hook_flags(text: str, desired: Dict[Tuple[str, str], bool]) -> Tuple[str, List[Dict[str, Any]]]:
    """Set `enabled:` on scopeguard hook entries of a Spec Kit extensions.yml, preserving formatting."""
    lines = text.split("\n")
    out: List[str] = []
    found: List[Dict[str, Any]] = []
    in_hooks = False
    event: Optional[str] = None
    i = 0
    while i < len(lines):
        line = lines[i]
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if stripped and indent == 0:
            in_hooks = stripped == "hooks:"
            event = None
            out.append(line)
            i += 1
            continue
        item = re.match(r"^(\s*)-\s+(.*)$", line)
        if in_hooks and item is None:
            ev = re.match(r"^\s+([A-Za-z0-9_]+):\s*$", line)
            if ev:
                event = ev.group(1)
            out.append(line)
            i += 1
            continue
        if not (in_hooks and item and event):
            out.append(line)
            i += 1
            continue
        item_indent = len(item.group(1))
        block = [line]
        j = i + 1
        while j < len(lines) and (not lines[j].strip() or len(lines[j]) - len(lines[j].lstrip(" ")) > item_indent):
            block.append(lines[j])
            j += 1
        fields: Dict[str, Tuple[int, str]] = {}
        for k, bline in enumerate(block):
            body = bline.strip()[2:] if k == 0 else bline.strip()
            m = re.match(r"^([A-Za-z0-9_]+):\s*(.*)$", body)
            if m and (k == 0 or len(bline) - len(bline.lstrip(" ")) == item_indent + 2):
                fields[m.group(1)] = (k, m.group(2))
        ext = _scalar(fields.get("extension", (0, ""))[1])
        cmd = _scalar(fields.get("command", (0, ""))[1])
        key = (event, cmd)
        if ext == "scopeguard" and key in desired:
            want = desired[key]
            current = _scalar(fields["enabled"][1]).lower() not in ("false", "no", "off") if "enabled" in fields else True
            if "enabled" in fields:
                k = fields["enabled"][0]
                prefix = block[k][: len(block[k]) - len(block[k].lstrip(" "))]
                if k == 0:
                    block[0] = re.sub(r"enabled:\s*\S+", f"enabled: {'true' if want else 'false'}", block[0])
                else:
                    block[k] = f"{prefix}enabled: {'true' if want else 'false'}"
            else:
                block.insert(1, " " * (item_indent + 2) + f"enabled: {'true' if want else 'false'}")
            found.append({"event": event, "command": cmd, "was": current, "now": want})
        out.extend(block)
        i = j
    return "\n".join(out), found


def hook_entries(text: str) -> List[Tuple[str, Dict[str, str]]]:
    """(event, {field: scalar}) for each entry of the `hooks:` map of a Spec Kit extensions.yml, read line by line the
    way set_hook_flags reads it (the config reader without PyYAML does not read lists of mappings)."""
    lines = text.split("\n")
    out: List[Tuple[str, Dict[str, str]]] = []
    in_hooks = False
    event: Optional[str] = None
    i = 0
    while i < len(lines):
        line = lines[i]
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if stripped and indent == 0 and not stripped.startswith("#"):
            in_hooks, event = stripped == "hooks:", None
            i += 1
            continue
        item = re.match(r"^(\s*)-\s+(.*)$", line)
        if not (in_hooks and item and event):
            ev = re.match(r"^\s+([A-Za-z0-9_]+):\s*$", line) if in_hooks and item is None else None
            if ev:
                event = ev.group(1)
            i += 1
            continue
        item_indent = len(item.group(1))
        fields: Dict[str, str] = {}
        body = [(item_indent + 2, item.group(2))]
        j = i + 1
        while j < len(lines) and (not lines[j].strip() or len(lines[j]) - len(lines[j].lstrip(" ")) > item_indent):
            body.append((len(lines[j]) - len(lines[j].lstrip(" ")), lines[j].strip()))
            j += 1
        for field_indent, content in body:
            m = re.match(r"^([A-Za-z0-9_]+):\s*(.*)$", content)
            if m and field_indent == item_indent + 2:
                fields[m.group(1)] = _scalar(_strip_yaml_comment(m.group(2)))
        out.append((event, fields))
        i = j
    return out


def hooks_not_run(root: Path, event: str) -> List[str]:
    """The other extensions' enabled hooks of `event` (after_plan, after_tasks): a command that stops at the gate never
    reaches its Mandatory Post-Execution Hooks, so these do not run this time."""
    ext_yml = root / EXTENSIONS_YML
    if not ext_yml.is_file():
        return []
    out = []
    for ev, fields in hook_entries(read_text(ext_yml)):
        if ev != event or fields.get("extension", "scopeguard") == "scopeguard":
            continue
        if fields.get("enabled", "true").lower() in ("false", "no", "off", "0"):
            continue
        out.append(f"{fields['extension']}: {fields.get('command', '?')}"
                   + (" (optional)" if fields.get("optional", "").lower() == "true" else ""))
    return out


def configure(root: Path, config: Dict[str, Any], sources: List[str], dry_run: bool) -> Tuple[str, Dict[str, Any], int]:
    eff, note = effective_integration(root, config)
    ext_yml = root / EXTENSIONS_YML
    if not ext_yml.is_file():
        raise ScopeGuardError(f"{EXTENSIONS_YML.as_posix()} not found - is the scopeguard extension installed in {root}?")
    original = read_text(ext_yml)
    updated, found = set_hook_flags(original, desired_hook_states(eff, config))
    if not found:
        raise ScopeGuardError(
            "no scopeguard hooks found in .specify/extensions.yml - reinstall the extension "
            "(specify extension add scopeguard ... --force)"
        )
    changed = [f for f in found if f["was"] != f["now"]]
    if changed and not dry_run:
        try:
            import yaml  # type: ignore

            yaml.safe_load(updated)  # never write a file Spec Kit cannot read
        except ImportError:
            pass
        except Exception as exc:
            raise ScopeGuardError(f"refusing to write .specify/extensions.yml: result would not parse ({exc})")
        # keep the file's line ending: Spec Kit writes it with the platform's (CRLF on Windows), so git shows one line
        eol = "\r\n" if b"\r\n" in ext_yml.read_bytes() else "\n"
        with open(ext_yml, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(updated.replace("\n", eol))

    ac = config["autocorrect"]
    out = [
        f"scopeGuard {__version__} | configure{' (dry run)' if dry_run else ''}",
        f"config: {', '.join(rel_path(Path(s), root) for s in sources) or 'defaults (no scopeguard-config.yml found)'}",
        "",
        f"  integration   : {config['integration']}" + (f" -> running as '{eff}'" if eff != config["integration"] else ""),
        f"  autocorrect   : {'on, max ' + str(ac['max_iterations']) + ' iteration(s), then escalate' if ac['enabled'] else 'off (gates report and stop)'}",
        f"  gates         : plan {'on' if config['plan']['enabled'] else 'off'}, tasks {'on' if config['tasks']['enabled'] else 'off'}, "
        f"implement {'on' if config['implement']['enabled'] else 'off'}",
        f"  mode          : {config['mode']}",
        "",
    ]
    if eff == "inline":
        out.append("  /speckit.plan and /speckit.tasks run the scope gate as a mandatory step of their own.")
    elif eff == "embedded":
        out.append("  scopeGuard runs only when another tool calls its command line (for example archiGuard's gate")
        out.append("  runner): all scopeGuard hooks are off and the inline steps are skipped.")
    else:
        out.append("  The scope gates run as separate scopeGuard commands from the Spec Kit hooks.")
    if note and eff == "embedded":
        out += ["", f"  NOTE: {note}."]
    elif note:
        out += ["", f"  NOTE: {note}.",
                "  Install it with: specify preset add --from "
                "https://github.com/rlgdev/spec-kit-scopeguard/releases/latest/download/scopeguard-preset.zip"]
    out += ["", "  Hooks in .specify/extensions.yml:"]
    for f in found:
        change = "" if f["was"] == f["now"] else f"   (was {'on' if f['was'] else 'off'})"
        out.append(f"    {f['event']:<16} {f['command']:<32} {'on' if f['now'] else 'off'}{change}")
    out += ["", f"  {len(changed)} hook setting(s) {'would change' if dry_run else 'changed'}."]
    data = {
        "tool": TOOL, "version": __version__, "command": "configure", "dry_run": dry_run,
        "integration": config["integration"], "effective_integration": eff, "note": note,
        "autocorrect": ac, "gates": {g: config[g]["enabled"] for g in ("plan", "tasks", "implement")},
        "mode": config["mode"], "hooks": found, "changed": len(changed),
    }
    return "\n".join(out), data, EXIT_PASS


# --------------------------------------------------------------------------- #
# Inventory / report / compare                                                  #
# --------------------------------------------------------------------------- #


def inventory(feature_dir: Path, scheme: IdScheme, config: Dict[str, Any]) -> Dict[str, Any]:
    spec = parse_spec(feature_dir / "spec.md", scheme, config)
    waivers = _plan_waivers(feature_dir, scheme, config)
    table, _ = load_plan_table(feature_dir, scheme, config)
    plan_index = table.index() if table else {}
    items = []
    for item in spec.items.values():
        row = (plan_index.get(item.key) or [None])[0]
        items.append({
            "id": item.display,
            "kind": item.kind,
            "title": item.title,
            "priority": item.priority,
            "spec_line": item.line,
            "plan_status": row.state if row else None,
            "in_scope": item.key not in waivers,
        })
    return {"spec": spec, "items": items, "plan_table_found": bool(table and table.found_section), "plan_rows": len(table.rows) if table else 0}


def render_inventory_text(feature_dir: Path, root: Path, inv: Dict[str, Any], config: Dict[str, Any]) -> str:
    spec: SpecModel = inv["spec"]
    out = [
        f"scopeGuard {__version__} | scope inventory | feature: {rel_path(feature_dir, root)}",
        f"{len(spec.stories)} {spec.stories_label}, {len(spec.requirements)} requirements "
        f"(traced prefixes: {spec.story_key}, {', '.join(config['ids']['requirement_prefixes']) or '-'})",
        "",
    ]
    for entry in inv["items"]:
        status = ""
        if entry["plan_status"]:
            status = f"  [plan: {entry['plan_status']}]"
        prio = f" ({entry['priority']})" if entry["priority"] else ""
        title = entry["title"] or ""
        if len(title) > 80:
            title = title[:77] + "..."
        out.append(f"  {entry['id']:<8} {title}{prio}{status}")
    if spec.findings:
        out.append("")
        for f in spec.findings:
            out.append(f"  {MARK[f.level]} {f.message}" + (f"  ({f.location})" if f.location else ""))
    section = config["plan"].get("section") or "Scope Coverage"
    out.append("")
    out.append("SCOPE CONTRACT")
    out.append(
        f"- plan.md must contain a '## {section}' table with one row per ID above. Status 'covered' (say where the "
        "plan handles it) or 'deferred' (only with a reason the user approved). No ID may be left out."
    )
    out.append(
        f"- tasks.md must carry every ID not deferred in the plan: {spec.stories_label} through tasks labelled "
        f"{IdScheme(config).label_example}, "
        "requirements by naming the ID in a task description or in tasks.md's Scope Coverage table."
    )
    out.append("- Never renumber, merge or drop IDs from spec.md to make a gate pass.")
    if not inv["plan_rows"]:
        out.append("")
        out.append("Starting point for the plan.md coverage table (fill in the Plan reference column):")
        if not inv["plan_table_found"]:
            out.append(f"## {section}")
            out.append("")
        out.extend(plan_skeleton_header())
        traced = traced_items(spec, bool(config["plan"].get("check_requirements", True)))
        out.extend(_skeleton_row(i) for i in traced)
    return "\n".join(out)


PHASES = ("plan", "tasks", "implement")


def phase_matrix(feature_dir: Path, scheme: IdScheme, config: Dict[str, Any]) -> Dict[str, Any]:
    spec = parse_spec(feature_dir / "spec.md", scheme, config)
    gates: Dict[str, Optional[GateResult]] = {}
    gates["plan"] = gate_plan(feature_dir, spec, scheme, config) if (feature_dir / "plan.md").is_file() else None
    has_tasks = (feature_dir / "tasks.md").is_file()
    gates["tasks"] = gate_tasks(feature_dir, spec, scheme, config) if has_tasks else None
    gates["implement"] = gate_implement(feature_dir, spec, scheme, config) if has_tasks else None
    rows = []
    for item in spec.items.values():
        row = {"id": item.display, "kind": item.kind, "title": item.title, "priority": item.priority}
        for phase in PHASES:
            gate = gates[phase]
            res = next((r for r in gate.items if r.item.key == item.key), None) if gate else None
            row[phase] = {"verdict": res.verdict, "code": res.code, "detail": res.detail, "evidence": res.evidence} if res else None
        rows.append(row)
    summary = {}
    for phase in PHASES:
        gate = gates[phase]
        summary[phase] = gate.counts() if gate else None
    return {"spec": spec, "rows": rows, "summary": summary, "gates": gates}


def _cell(entry: Optional[Dict[str, Any]], phase: str) -> str:
    if not entry:
        return "-"
    verdict = entry["verdict"]
    if verdict == PASS:
        if phase == "tasks" and entry["evidence"]:
            return "ok " + ",".join(entry["evidence"][:4]) + ("..." if len(entry["evidence"]) > 4 else "")
        return "ok"
    if verdict == WAIVED:
        return "waived"
    code = entry.get("code")
    if code == "open":
        return "OPEN"
    if code == "missing":
        return "MISSING"
    return "INVALID"


def render_report_markdown(feature_dir: Path, root: Path, matrix: Dict[str, Any]) -> str:
    spec: SpecModel = matrix["spec"]
    out = [
        f"## scopeGuard coverage report - `{rel_path(feature_dir, root)}`",
        "",
        f"{len(spec.stories)} {spec.stories_label}, {len(spec.requirements)} requirements traced.",
        "",
        "| Phase | Verdict | Pass | Waived | Violations | Coverage |",
        "|-------|---------|------|--------|------------|----------|",
    ]
    for phase in PHASES:
        s = matrix["summary"][phase]
        gate = matrix["gates"][phase]
        if not s:
            out.append(f"| {phase} | not run (artifact missing) | | | | |")
            continue
        out.append(f"| {phase} | {gate.verdict} | {s['pass']} | {s['waived']} | {s['violations']} | {s['pass']}/{s['in_scope']} ({s['coverage_pct']}%) |")
    out += ["", "| ID | Title | Plan | Tasks | Implement |", "|----|-------|------|-------|-----------|"]
    for row in matrix["rows"]:
        title = (row["title"] or "").replace("|", "\\|")
        if row["priority"]:
            title += f" ({row['priority']})"
        if len(title) > 60:
            title = title[:57] + "..."
        out.append(f"| {row['id']} | {title} | {_cell(row['plan'], 'plan')} | {_cell(row['tasks'], 'tasks')} | {_cell(row['implement'], 'implement')} |")
    return "\n".join(out) + "\n"


def render_compare_markdown(a: Tuple[str, Path, Dict[str, Any]], b: Tuple[str, Path, Dict[str, Any]], root: Path) -> Tuple[str, int]:
    label_a, dir_a, ma = a
    label_b, dir_b, mb = b
    rows_a = {r["id"]: r for r in ma["rows"]}
    rows_b = {r["id"]: r for r in mb["rows"]}
    ids: List[str] = []
    for rid in list(rows_a) + list(rows_b):
        if rid not in ids:
            ids.append(rid)
    out = [
        f"## scopeGuard comparison - {label_a} vs {label_b}",
        "",
        f"- {label_a}: `{rel_path(dir_a, root)}`",
        f"- {label_b}: `{rel_path(dir_b, root)}`",
        "",
        "| Phase | " + label_a + " coverage | " + label_b + " coverage |",
        "|-------|------|------|",
    ]
    for phase in PHASES:
        sa, sb = ma["summary"][phase], mb["summary"][phase]
        fa = f"{sa['pass']}/{sa['in_scope']} ({sa['coverage_pct']}%)" if sa else "-"
        fb = f"{sb['pass']}/{sb['in_scope']} ({sb['coverage_pct']}%)" if sb else "-"
        out.append(f"| {phase} | {fa} | {fb} |")
    out += [
        "",
        f"| ID | Title | Plan {label_a} | Plan {label_b} | Tasks {label_a} | Tasks {label_b} | Impl {label_a} | Impl {label_b} | Diff |",
        "|----|-------|---|---|---|---|---|---|---|",
    ]
    differences = 0
    for rid in ids:
        ra, rb = rows_a.get(rid), rows_b.get(rid)
        title = ((ra or rb)["title"] or "").replace("|", "\\|")
        if len(title) > 50:
            title = title[:47] + "..."
        cells = []
        diff = False
        for phase in PHASES:
            ca = _cell(ra[phase], phase) if ra else "not in spec"
            cb = _cell(rb[phase], phase) if rb else "not in spec"
            va = ra[phase]["verdict"] if ra and ra[phase] else ("absent" if not ra else None)
            vb = rb[phase]["verdict"] if rb and rb[phase] else ("absent" if not rb else None)
            if va != vb:
                diff = True
            cells.append((ca, cb))
        if diff:
            differences += 1
        out.append(
            f"| {rid} | {title} | {cells[0][0]} | {cells[0][1]} | {cells[1][0]} | {cells[1][1]} | {cells[2][0]} | {cells[2][1]} | {'**yes**' if diff else ''} |"
        )
    out += ["", f"{differences} scope item(s) differ between the two runs."]
    return "\n".join(out) + "\n", differences


# --------------------------------------------------------------------------- #
# CLI                                                                           #
# --------------------------------------------------------------------------- #


def _configure_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            if stream.isatty():
                stream.reconfigure(errors="replace")  # type: ignore[attr-defined]
            else:
                stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError, OSError):
            pass


def _write_out(path: Optional[str], content: str, append: bool) -> None:
    if not path:
        return
    target = Path(path)
    if target.parent and not target.parent.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "a" if append else "w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
        if append:
            handle.write("\n")


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", help="project root (default: nearest directory containing .specify/)")
    common.add_argument("--feature-dir", help="feature directory, e.g. specs/001-my-feature (default: active feature)")
    common.add_argument("--all", action="store_true", help="run for every feature under specs/ (CI mode)")
    common.add_argument("--config", help="config file (default: .specify/extensions/scopeguard/scopeguard-config.yml)")
    common.add_argument("--json", action="store_true", help="machine-readable JSON output")
    common.add_argument("--format", choices=("text", "json", "md"), help="output format (default: text)")
    common.add_argument("--out", help="also write a Markdown report to this file")
    common.add_argument("--append", action="store_true", help="append to --out instead of overwriting (e.g. $GITHUB_STEP_SUMMARY)")
    common.add_argument("--save", action="store_true", help="report: also write scopeguard-report.md into each feature directory")
    common.add_argument("--verbose", "-v", action="store_true", help="list passing items too")
    common.add_argument("--report-only", action="store_true", help="never fail (exit 0); same as mode: report")
    common.add_argument(
        "--iteration", type=int, metavar="N",
        help="resolution loop: N resolve-and-recheck iterations done so far (0 = first check). "
        "Records history; at N >= autocorrect.max_iterations a failing gate escalates (exit 3, problem report)",
    )
    common.add_argument(
        "--via", choices=("inline", "hook"),
        help="who is calling: the inline step inside /speckit.plan|tasks or a Spec Kit hook. "
        "The call is skipped (exit 0) when the configured integration says the other one runs the gate",
    )

    parser = argparse.ArgumentParser(
        prog="scopeguard",
        description="Deterministic scope-coverage gates for GitHub Spec Kit: no user story or requirement "
        "is silently dropped between spec, plan, tasks and implement.",
    )
    parser.add_argument("--version", action="version", version=f"scopeguard {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True
    sub.add_parser("inventory", parents=[common], help="list the scope IDs defined in spec.md and the scope contract")
    sub.add_parser("plan", parents=[common], help="gate: every spec item is accounted for in plan.md")
    sub.add_parser("tasks", parents=[common], help="gate: every in-scope item is carried by tasks.md")
    sub.add_parser("implement", parents=[common], help="gate: every task carrying an in-scope item is done")
    check = sub.add_parser("check", parents=[common], help="run every gate whose artifact exists (plan, tasks)")
    check.add_argument("--implement", action="store_true", help="include the implement gate")
    sub.add_parser("report", parents=[common], help="coverage matrix across all phases (informational)")
    configure_parser = sub.add_parser(
        "configure", parents=[common],
        help="apply scopeguard-config.yml: switch the scopeGuard hooks on or off for the chosen integration",
    )
    configure_parser.add_argument("--dry-run", action="store_true", help="show what would change, change nothing")
    cmp_parser = sub.add_parser("compare", parents=[common], help="compare scope coverage of two feature directories (lab runs)")
    cmp_parser.add_argument("dir_a", help="first feature directory (run A)")
    cmp_parser.add_argument("dir_b", help="second feature directory (run B)")
    cmp_parser.add_argument("--labels", default="A,B", help="labels for the two runs, comma separated (default: A,B)")
    cmp_parser.add_argument("--fail-on-diff", action="store_true", help="exit 1 when coverage differs")
    return parser


def _output_format(args: argparse.Namespace) -> str:
    if args.json:
        return "json"
    return args.format or "text"


def run(argv: Optional[Sequence[str]] = None) -> int:
    _configure_stdout()
    parser = build_parser()
    args = parser.parse_args(argv)
    fmt = _output_format(args)
    try:
        root = find_project_root(args.root)
        config, sources = load_config(root, args.config)
        if args.report_only:
            config["mode"] = "report"
        scheme = IdScheme(config)

        if args.command == "configure":
            text, data, code = configure(root, config, sources, args.dry_run)
            print(json.dumps(data, indent=2) if fmt == "json" else text)
            return code

        integration_note: Optional[str] = None
        if getattr(args, "via", None):
            eff, integration_note = effective_integration(root, config)
            wanted = "inline" if args.via == "inline" else "hooks"
            if eff != wanted:
                if eff == "embedded":
                    msg = (
                        f"scopeGuard: {args.command} skipped here - integration is 'embedded', so scopeGuard runs only "
                        "when the tool that embeds it calls it (for example archiGuard's gate runner). Nothing to do; "
                        "continue."
                    )
                    if integration_note:
                        msg += f" Note: {integration_note}."
                elif eff == "inline":
                    msg = (
                        f"scopeGuard: {args.command} skipped here - integration is 'inline', so this step runs "
                        "inside /speckit.plan and /speckit.tasks. Nothing to do; continue. (Run the scopeguard "
                        "'configure' command to switch these hooks off.)"
                    )
                else:
                    msg = (
                        f"scopeGuard: {args.command} skipped here - integration is '{eff}', so this step runs "
                        "through the scopeGuard hooks instead. Nothing to do; continue."
                    )
                    if integration_note:
                        msg += f" Note: {integration_note}."
                if fmt == "json":
                    print(json.dumps({"tool": TOOL, "version": __version__, "command": args.command,
                                      "verdict": "skipped", "integration": eff, "message": msg}, indent=2))
                else:
                    print(msg)
                return EXIT_PASS
            if integration_note and fmt != "json":
                print(f"scopeGuard: note: {integration_note}.")

        if args.command == "compare":
            labels = [s.strip() for s in args.labels.split(",")] + ["A", "B"]
            dirs = []
            for d in (args.dir_a, args.dir_b):
                p = Path(d)
                p = (p if p.is_absolute() else (Path.cwd() / p)).resolve()
                if not (p / "spec.md").is_file():
                    raise ScopeGuardError(f"{d} has no spec.md")
                dirs.append(p)
            ma = phase_matrix(dirs[0], scheme, config)
            mb = phase_matrix(dirs[1], scheme, config)
            md, diffs = render_compare_markdown((labels[0], dirs[0], ma), (labels[1], dirs[1], mb), root)
            if fmt == "json":
                print(json.dumps({
                    "tool": TOOL, "version": __version__, "command": "compare", "differences": diffs,
                    labels[0]: {"feature_dir": str(dirs[0]), "summary": ma["summary"], "rows": ma["rows"]},
                    labels[1]: {"feature_dir": str(dirs[1]), "summary": mb["summary"], "rows": mb["rows"]},
                }, indent=2))
            else:
                print(md)
            _write_out(args.out, md, args.append)
            return EXIT_FAIL if (args.fail_on_diff and diffs and config["mode"] == "enforce") else EXIT_PASS

        features = resolve_feature_dirs(root, args.feature_dir, args.all, config)

        if args.command == "inventory":
            payload = []
            texts = []
            for fd in features:
                inv = inventory(fd, scheme, config)
                texts.append(render_inventory_text(fd, root, inv, config))
                payload.append({
                    "feature_dir": rel_path(fd, root),
                    "items": inv["items"],
                    "findings": [f.to_dict() for f in inv["spec"].findings],
                })
            if fmt == "json":
                print(json.dumps({"tool": TOOL, "version": __version__, "command": "inventory", "features": payload}, indent=2))
            else:
                print("\n\n".join(texts))
            return EXIT_PASS

        if args.command == "report":
            docs, payload = [], []
            for fd in features:
                matrix = phase_matrix(fd, scheme, config)
                doc = render_report_markdown(fd, root, matrix)
                docs.append(doc)
                if args.save:
                    _write_out(str(fd / "scopeguard-report.md"), doc, False)
                payload.append({"feature_dir": rel_path(fd, root), "summary": matrix["summary"], "rows": matrix["rows"]})
            md = "\n".join(docs)
            if fmt == "json":
                print(json.dumps({"tool": TOOL, "version": __version__, "command": "report", "features": payload}, indent=2))
            else:
                print(md)
            _write_out(args.out, md, args.append)
            return EXIT_PASS

        results: List[GateResult] = []
        for fd in features:
            spec = parse_spec(fd / "spec.md", scheme, config)
            gates: List[str]
            if args.command == "check":
                gates = []
                if config["plan"].get("enabled", True) and (fd / "plan.md").is_file():
                    gates.append("plan")
                if config["tasks"].get("enabled", True) and (fd / "tasks.md").is_file():
                    gates.append("tasks")
                if getattr(args, "implement", False) and config["implement"].get("enabled", True) and (fd / "tasks.md").is_file():
                    gates.append("implement")
                if not gates:
                    print(f"scopeGuard: {rel_path(fd, root)} has no plan.md or tasks.md yet - nothing to check", file=sys.stderr)
            else:
                gates = [args.command]
            for gate in gates:
                if not config[gate].get("enabled", True):
                    print(f"scopeGuard: {gate} gate disabled in config", file=sys.stderr)
                    continue
                fn = {"plan": gate_plan, "tasks": gate_tasks, "implement": gate_implement}[gate]
                results.append(fn(fd, spec, scheme, config))

        if args.iteration is not None:
            if args.iteration < 0:
                raise ScopeGuardError("--iteration must be 0 or greater")
            for r in results:
                apply_iteration(r, args.iteration, config["autocorrect"]["max_iterations"], root, config["autocorrect"]["enabled"])
        failed = any(r.verdict == "fail" for r in results)
        escalated = any(r.escalated for r in results)
        if fmt == "json":
            print(json.dumps({
                "tool": TOOL,
                "version": __version__,
                "command": args.command,
                "mode": config["mode"],
                "config_sources": sources,
                "verdict": ("escalate" if escalated else "fail") if failed else "pass",
                "gates": [gate_to_dict(r, root) for r in results],
            }, indent=2))
        elif fmt == "md":
            print("\n".join(render_gate_markdown(r, root) for r in results))
        else:
            print("\n\n".join(render_gate_text(r, root, args.verbose) for r in results))
            if config["mode"] == "report" and failed:
                print("\n(report mode: violations do not fail this run)")
            if getattr(args, "via", None) == "inline" and escalated and config["mode"] == "enforce":
                for gate in sorted({r.gate for r in results if r.escalated}):
                    skipped = hooks_not_run(root, f"after_{gate}")
                    if skipped:
                        print(f"\nNOT RUN: /speckit.{gate} ends here, so these after_{gate} hooks of other extensions do "
                              f"not run: {'; '.join(skipped)}. Tell the user; they run when the command is run again and passes.")
        if args.out:
            _write_out(args.out, "\n".join(render_gate_markdown(r, root) for r in results), args.append)
        if failed and config["mode"] == "enforce":
            return EXIT_ESCALATE if escalated else EXIT_FAIL
        return EXIT_PASS
    except ScopeGuardError as exc:
        if fmt == "json":
            print(json.dumps({"tool": TOOL, "version": __version__, "verdict": "error", "error": str(exc)}, indent=2))
        print(f"scopeGuard: ERROR: {exc}", file=sys.stderr)
        return EXIT_ERROR


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
