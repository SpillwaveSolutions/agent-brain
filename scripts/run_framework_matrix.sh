#!/usr/bin/env bash
# run_framework_matrix.sh — Sequential self-bootstrapping runner for all 7 framework
# smoke tests (5 Python + Mastra + Vercel AI SDK via one `pnpm test` invocation).
#
# USAGE:
#   From the repo root:
#     FRAMEWORK_MATRIX=1 bash scripts/run_framework_matrix.sh
#     bash scripts/run_framework_matrix.sh --force
#
# GATE (opt-in, SLOW):
#   This runner is intentionally NOT in `task before-push`. It is gated behind
#   FRAMEWORK_MATRIX=1 (env var) or --force (first argument). Without either gate,
#   it prints the opt-in message and exits 0 without running any test.
#
# Called by:
#   - `task mcp:framework-matrix` (the Taskfile operator target)
#   - Nightly CI workflow (FRAMEWORK_MATRIX=1 task mcp:framework-matrix)
#
# Exit codes:
#   0 — all frameworks passed (or gate unset — no-op)
#   1 — one or more framework legs hard-failed (not a graceful skip)
#
# Framework legs:
#   Python (5): openai-agents, langchain, llama-index, pydantic-ai, autogen
#     - bootstrap: bash framework-matrix/bootstrap_venv.sh <fw>
#     - run:       framework-matrix/<fw>/.venv/bin/pytest framework-matrix/<fw>/ -m framework
#   TypeScript (2 — Mastra + Vercel AI SDK, one pnpm test invocation):
#     - cd framework-matrix/ts && pnpm install --frozen-lockfile && pnpm test

set -euo pipefail

# ---------------------------------------------------------------------------
# Step 1: GATE CHECK — exit 0 (no-op) unless FRAMEWORK_MATRIX=1 or --force
# ---------------------------------------------------------------------------
FORCE=0
if [ "${1:-}" = "--force" ]; then
    FORCE=1
    shift || true
fi

MATRIX_ENABLED="${FRAMEWORK_MATRIX:-0}"

if [ "$FORCE" = "0" ] && [ "$MATRIX_ENABLED" != "1" ]; then
    echo "framework-matrix: slow + opt-in; set FRAMEWORK_MATRIX=1 (or pass --force) to run"
    exit 0
fi

# ---------------------------------------------------------------------------
# Step 2: cd to the repository root so all relative paths resolve
# ---------------------------------------------------------------------------
if git rev-parse --show-toplevel >/dev/null 2>&1; then
    cd "$(git rev-parse --show-toplevel)"
else
    # Fallback when not inside a git work tree (e.g. bare clone or CI overlay).
    cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
fi

# ---------------------------------------------------------------------------
# Step 3: Run all framework legs sequentially; record per-framework results
# ---------------------------------------------------------------------------

# Result tracking: "PASS", "FAIL", or "SKIP"
declare -A RESULTS

PYTHON_FRAMEWORKS=("openai-agents" "langchain" "llama-index" "pydantic-ai" "autogen")

echo "============================================================"
echo "  Agent Brain Framework Matrix"
echo "  Running ${#PYTHON_FRAMEWORKS[@]} Python + 1 TypeScript suite"
echo "============================================================"
echo ""

# ---------------------------------------------------------------------------
# PYTHON LEGS (5 frameworks — each self-bootstrapped with its own venv)
# ---------------------------------------------------------------------------
for FW in "${PYTHON_FRAMEWORKS[@]}"; do
    echo "------------------------------------------------------------"
    echo "  [Python] $FW"
    echo "------------------------------------------------------------"

    # SETUP: self-bootstrap the per-framework venv (idempotent; exit 3 on pin drift)
    echo "  --> Bootstrapping $FW venv ..."
    if ! bash framework-matrix/bootstrap_venv.sh "$FW"; then
        echo "  BOOTSTRAP FAILED for $FW (exit $?)" >&2
        RESULTS["$FW"]="FAIL"
        echo ""
        continue
    fi

    # RUN: use the framework's OWN venv python to run only the framework-marked tests
    echo "  --> Running pytest for $FW ..."
    VENV_PYTEST="framework-matrix/$FW/.venv/bin/pytest"
    if [ ! -x "$VENV_PYTEST" ]; then
        echo "  ERROR: $VENV_PYTEST not found — bootstrap may have failed silently" >&2
        RESULTS["$FW"]="FAIL"
        echo ""
        continue
    fi

    # Capture pytest exit code without aborting the whole loop.
    # pytest exit 0 = all passed; exit 1 = some failed; exit 5 = no tests collected
    # (treated as skip/pass since tests skip gracefully without OPENAI_API_KEY).
    set +e
    "$VENV_PYTEST" "framework-matrix/$FW/" -m framework
    PY_EXIT=$?
    set -e

    if [ "$PY_EXIT" = "0" ] || [ "$PY_EXIT" = "5" ]; then
        # exit 5 means "no tests collected" — framework tests skipped gracefully
        RESULTS["$FW"]="PASS"
    elif [ "$PY_EXIT" = "4" ]; then
        # exit 4 means "usage error" — treat as failure
        echo "  pytest usage error for $FW (exit 4)" >&2
        RESULTS["$FW"]="FAIL"
    else
        echo "  pytest FAILED for $FW (exit $PY_EXIT)" >&2
        RESULTS["$FW"]="FAIL"
    fi

    # TEARDOWN: each framework is fully set up, run, and torn down before the next
    # so heavy dep trees don't collide and orphan subprocesses don't accumulate.
    # The per-framework venv is isolated; no persistent state carries between frameworks.
    echo "  --> $FW done (result: ${RESULTS[$FW]})"
    echo ""
done

# ---------------------------------------------------------------------------
# TYPESCRIPT LEG — Mastra (FRAME-06) + Vercel AI SDK (FRAME-07)
# Both run inside a single `pnpm test` invocation via vitest.
# ---------------------------------------------------------------------------
TS_FW="typescript"
echo "------------------------------------------------------------"
echo "  [TypeScript] Mastra + Vercel AI SDK (pnpm test)"
echo "------------------------------------------------------------"
echo "  --> Installing TS dependencies (pnpm install --frozen-lockfile) ..."

TS_DIR="framework-matrix/ts"

if [ ! -d "$TS_DIR" ]; then
    echo "  ERROR: $TS_DIR directory not found" >&2
    RESULTS["$TS_FW"]="FAIL"
else
    set +e
    (
        cd "$TS_DIR"
        pnpm install --frozen-lockfile && pnpm test
    )
    TS_EXIT=$?
    set -e

    if [ "$TS_EXIT" = "0" ]; then
        RESULTS["$TS_FW"]="PASS"
    else
        echo "  TypeScript pnpm test FAILED (exit $TS_EXIT)" >&2
        RESULTS["$TS_FW"]="FAIL"
    fi
fi

echo "  --> TypeScript done (result: ${RESULTS[$TS_FW]})"
echo ""

# ---------------------------------------------------------------------------
# SUMMARY — print per-framework PASS/FAIL summary and exit accordingly
# ---------------------------------------------------------------------------
echo "============================================================"
echo "  Framework Matrix Summary"
echo "============================================================"

OVERALL_FAIL=0

for FW in "${PYTHON_FRAMEWORKS[@]}" "$TS_FW"; do
    STATUS="${RESULTS[$FW]:-UNKNOWN}"
    printf "  %-20s  %s\n" "$FW" "$STATUS"
    if [ "$STATUS" = "FAIL" ] || [ "$STATUS" = "UNKNOWN" ]; then
        OVERALL_FAIL=1
    fi
done

echo "============================================================"

if [ "$OVERALL_FAIL" = "1" ]; then
    echo "  RESULT: FAILED (one or more framework legs hard-failed)"
    exit 1
else
    echo "  RESULT: PASSED (all framework legs passed or skipped gracefully)"
    exit 0
fi
