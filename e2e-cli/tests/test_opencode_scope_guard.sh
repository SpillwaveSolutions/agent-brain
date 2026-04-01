#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
E2E_ROOT="$REPO_ROOT/e2e-cli"
RUN_ID="opencode-scope-guard-$$"
RUNS_DIR="$REPO_ROOT/e2e_workdir/$RUN_ID"
ADAPTER_NAME="opencode"

export REPO_ROOT E2E_ROOT RUN_ID RUNS_DIR ADAPTER_NAME

source "$E2E_ROOT/lib/harness.sh"
source "$E2E_ROOT/lib/runtime_parity.sh"

fail() {
  echo "$1" >&2
  exit 1
}

workspace_create "opencode-scope-guard" >/dev/null
PROJECT_DIR="$(runtime_workspace_prepare opencode "$SCENARIO_WORKSPACE")"
RUNTIME_ROOT="$SCENARIO_WORKSPACE/opencode-runtime"

BEFORE_FILE="$RUNS_DIR/opencode-before.txt"
AFTER_FILE="$RUNS_DIR/opencode-after.txt"
printf 'baseline\n' > "$BEFORE_FILE"
printf 'baseline\nmutation\n' > "$AFTER_FILE"

set +e
MUTATION_OUTPUT="$(runtime_parity_detect_global_mutation "$BEFORE_FILE" "$AFTER_FILE" "$RUNTIME_ROOT" 2>&1)"
MUTATION_EXIT=$?
set -e

if [[ $MUTATION_EXIT -eq 0 ]]; then
  fail "expected global mutation detection to fail"
fi

echo "$MUTATION_OUTPUT" | grep -q '"runtime":"opencode"' || fail "missing runtime in mutation output"
echo "$MUTATION_OUTPUT" | grep -q '"error_type":"global_path_mutated"' || fail "missing global_path_mutated error"
echo "$MUTATION_OUTPUT" | grep -q '"remediation":"' || fail "missing remediation"
[[ -d "$PROJECT_DIR" ]] || fail "expected project-local opencode workspace"
[[ -f "$RUNTIME_ROOT/logs/failure.log" ]] || fail "expected failure log"

rm -rf "$RUNS_DIR"
echo "opencode scope guard passed"
