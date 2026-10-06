#!/usr/bin/env bash
# End-to-end check against a real Spec Kit install (used by CI; runnable locally):
#   1. builds the archives and serves dist/ on localhost
#   2. specify init, then installs scopeGuard and its preset from the archives
#   3. the rendered skills wrap /speckit.plan and /speckit.tasks; configure switches the hooks off (inline) and back (hooks)
#   4. the example feature: the composed plan template carries the Scope Coverage table; the empty plan and the
#      plan that dropped US3 fail the gate
#
# Usage: tools/e2e-speckit.sh       (needs `specify` on PATH, git, python3)
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${E2E_PORT:-8764}"
WORK="$(mktemp -d)"
trap 'kill "${SERVER:-}" 2>/dev/null || true; rm -rf "$WORK"' EXIT
PY="$(command -v python3 || command -v python)"

fail() { echo "E2E FAIL: $*" >&2; exit 1; }
expect() {  # expect <exit code> <command...>
    local want="$1"; shift
    set +e; "$@" > "$WORK/out.txt" 2>&1; local got=$?; set -e
    if [[ "$got" != "$want" ]]; then cat "$WORK/out.txt"; fail "expected exit $want, got $got: $*"; fi
}
contains() { grep -qF -- "$1" "$WORK/out.txt" || { cat "$WORK/out.txt"; fail "output lacks: $1"; }; }

"$PY" "$REPO/tools/build.py" >/dev/null
mkdir -p "$WORK/www"
cp "$REPO/dist/scopeguard.zip" "$REPO/dist/scopeguard-preset.zip" "$WORK/www/"
(cd "$WORK/www" && exec "$PY" -m http.server "$PORT" --bind 127.0.0.1 >/dev/null 2>&1) &
SERVER=$!
sleep 2
BASE="http://127.0.0.1:$PORT"

echo "== specify $(specify version 2>/dev/null | grep -o 'CLI Version *[0-9.]*' | grep -o '[0-9.]*$' || echo '?')"
cd "$WORK"
# --non-interactive arrived after 0.12.17 (the oldest supported Spec Kit, in the CI matrix): fall back without it
specify init lab --integration claude --script sh --ignore-agent-tools --non-interactive >/dev/null 2>&1 \
    || specify init lab --integration claude --script sh --ignore-agent-tools >/dev/null
cd lab
git init -q -b main && git config user.email e2e@example.com && git config user.name e2e && git config commit.gpgsign false
printf 'y\ny\n' | specify extension add scopeguard --from "$BASE/scopeguard.zip" >/dev/null
specify preset add --from "$BASE/scopeguard-preset.zip" >/dev/null
SG=(bash .specify/extensions/scopeguard/scripts/bash/scopeguard.sh)

echo "== registration and rendered skills"
specify extension list | grep -i scopeguard >/dev/null || fail "scopeguard not listed"
grep -q "speckit.scopeguard.plan" .specify/extensions.yml || fail "after_plan hook not registered"
grep -rq "bash .specify/extensions/scopeguard/scripts/bash/scopeguard.sh plan --iteration N" .claude || fail "plan command not rendered"
grep -q "scopeGuard (B): scope gate" .claude/skills/speckit-plan/SKILL.md || fail "plan wrap missing"
grep -q "scopeGuard (B): scope gate" .claude/skills/speckit-tasks/SKILL.md || fail "tasks wrap missing"
grep -q "setup-plan.sh --json" .claude/skills/speckit-plan/SKILL.md || fail "plan skill lost its setup step"

echo "== configure"
expect 0 "${SG[@]}" configure
contains "integration"
"$PY" - <<'PY'
import re
text = open(".specify/extensions.yml").read()
block = text[text.index("command: speckit.scopeguard.plan"):]
assert re.search(r"enabled:\s*false", block.split("- extension")[0]), "after_plan hook not switched off"
PY
SCOPEGUARD_INTEGRATION=hooks "${SG[@]}" configure --json | "$PY" -c "import json,sys; d=json.load(sys.stdin); assert d['effective_integration']=='hooks' and d['changed']==4, d"
expect 0 "${SG[@]}" configure

echo "== the example feature"
bash .specify/scripts/bash/create-new-feature.sh --json --short-name team-board "Team board" >/dev/null 2>&1
fd=$(find specs -mindepth 1 -maxdepth 1 -type d | head -1)
cp "$REPO/examples/missing-story/specs/001-team-board/spec.md" "$fd/spec.md"
SPECIFY_FEATURE_DIRECTORY="$fd" bash .specify/scripts/bash/setup-plan.sh --json >/dev/null 2>&1
grep -q "## Scope Coverage" "$fd/plan.md" || fail "the composed plan template lacks the Scope Coverage table"
expect 1 "${SG[@]}" plan --feature-dir "$fd"
cp "$REPO/examples/missing-story/specs/001-team-board/plan.md" "$fd/plan.md"
set +e; "${SG[@]}" plan --feature-dir "$fd" --json > "$WORK/gate.json"; code=$?; set -e
[[ $code == 1 ]] || fail "the plan that dropped US3 must fail the gate (exit $code)"
"$PY" - "$WORK/gate.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
bad = {i["id"] for i in d["gates"][0]["items"] if i["verdict"] == "violation"}
assert "US3" in bad, bad
PY

echo "E2E PASS"
