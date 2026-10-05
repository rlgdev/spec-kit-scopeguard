#!/usr/bin/env bash
# scopeGuard launcher (bash). Finds a Python 3.8+ interpreter and runs the
# deterministic engine in ../python/scopeguard.py with all arguments.
#
# Interpreter search order:
#   1. $SCOPEGUARD_PYTHON
#   2. python3 / python on PATH (Windows Store alias stubs are skipped)
#   3. the Python inside the uv tool environment of specify-cli
#   4. uv run --no-project python
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE="$SCRIPT_DIR/../python/scopeguard.py"

if [[ ! -f "$ENGINE" ]]; then
    echo "scopeGuard: ERROR: engine not found at $ENGINE" >&2
    exit 2
fi

_works() {
    "$@" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' >/dev/null 2>&1
}

PY=()
if [[ -n "${SCOPEGUARD_PYTHON:-}" ]]; then
    if ! _works "$SCOPEGUARD_PYTHON"; then
        echo "scopeGuard: ERROR: SCOPEGUARD_PYTHON='$SCOPEGUARD_PYTHON' is not a working Python 3.8+ interpreter." >&2
        exit 2
    fi
    PY=("$SCOPEGUARD_PYTHON")
else
    for candidate in python3 python; do
        if command -v "$candidate" >/dev/null 2>&1 && _works "$candidate"; then
            PY=("$candidate")
            break
        fi
    done
    if [[ ${#PY[@]} -eq 0 ]] && command -v uv >/dev/null 2>&1; then
        tool_dir="$(uv tool dir 2>/dev/null || true)"
        for candidate in "$tool_dir/specify-cli/bin/python" "$tool_dir/specify-cli/Scripts/python.exe"; do
            if [[ -n "$tool_dir" && -x "$candidate" ]] && _works "$candidate"; then
                PY=("$candidate")
                break
            fi
        done
        if [[ ${#PY[@]} -eq 0 ]]; then
            PY=(uv run --no-project --quiet python)
        fi
    fi
fi

if [[ ${#PY[@]} -eq 0 ]]; then
    echo "scopeGuard: ERROR: no Python 3.8+ interpreter found. Install Python or uv, or set SCOPEGUARD_PYTHON." >&2
    exit 2
fi

exec "${PY[@]}" "$ENGINE" "$@"
