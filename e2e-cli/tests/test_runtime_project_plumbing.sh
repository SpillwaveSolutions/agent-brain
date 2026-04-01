#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
E2E_ROOT="$REPO_ROOT/e2e-cli"
RUN_ID="runtime-project-plumbing-$$"
RUNS_DIR="$REPO_ROOT/e2e_workdir/$RUN_ID"
ADAPTER_NAME="codex"

export REPO_ROOT E2E_ROOT RUN_ID RUNS_DIR ADAPTER_NAME

source "$E2E_ROOT/lib/harness.sh"
source "$E2E_ROOT/lib/runtime_parity.sh"

fail() {
  echo "$1" >&2
  exit 1
}

snapshot_tree() {
  local dir="$1"
  python3 - "$dir" <<'PY'
from pathlib import Path
import hashlib
import json
import sys

root = Path(sys.argv[1])
entries = []
for path in sorted(p for p in root.rglob("*") if p.is_file()):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    entries.append({"path": str(path.relative_to(root)), "sha256": digest})
print(json.dumps(entries, sort_keys=True))
PY
}

assert_equals() {
  local actual="$1"
  local expected="$2"
  local label="$3"
  if [[ "$actual" != "$expected" ]]; then
    fail "$label: expected '$expected' but got '$actual'"
  fi
}

assert_file() {
  local path="$1"
  [[ -f "$path" ]] || fail "Expected file: $path"
}

assert_dir() {
  local path="$1"
  [[ -d "$path" ]] || fail "Expected directory: $path"
}

TEMPLATE_DIR="$(runtime_fixture_template_dir)"
TEMPLATE_BEFORE="$(snapshot_tree "$TEMPLATE_DIR")"

workspace_create "runtime-project-plumbing" >/dev/null
PROJECT_DIR="$(runtime_workspace_prepare codex "$SCENARIO_WORKSPACE")"
RUNTIME_ROOT="$SCENARIO_WORKSPACE/codex-runtime"

assert_equals "$PROJECT_DIR" "$SCENARIO_WORKSPACE/codex-runtime/project" "project dir"
assert_dir "$PROJECT_DIR"
assert_dir "$RUNTIME_ROOT/cleanup"
assert_dir "$RUNTIME_ROOT/logs"
assert_file "$PROJECT_DIR/README.md"
assert_file "$PROJECT_DIR/docs/fixture-doc.md"
assert_file "$PROJECT_DIR/src/sample_module.py"

assert_equals "$(runtime_expected_target_relpath codex)" ".codex/skills/agent-brain" "codex relpath"
assert_equals "$(runtime_expected_target_relpath opencode)" ".opencode/plugins/agent-brain" "opencode relpath"
assert_equals "$(runtime_expected_target_relpath gemini)" ".gemini/plugins/agent-brain" "gemini relpath"

TEST_BIN_DIR="$RUNS_DIR/fake-bin"
mkdir -p "$TEST_BIN_DIR"
POETRY_LOG="$RUNS_DIR/fake-poetry.log"
POETRY_PWD_LOG="$RUNS_DIR/fake-poetry.pwd"

cat > "$TEST_BIN_DIR/poetry" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" > "$POETRY_LOG"
pwd > "$POETRY_PWD_LOG"
printf '{\n  "status": "installed",\n  "target_dir": "%s"\n}\n' "$FAKE_TARGET_DIR"
EOF
chmod +x "$TEST_BIN_DIR/poetry"

export PATH="$TEST_BIN_DIR:$PATH"
export POETRY_LOG POETRY_PWD_LOG

export FAKE_TARGET_DIR="$PROJECT_DIR/.codex/skills/agent-brain"
INSTALL_OUTPUT="$(runtime_install_project_local codex "$PROJECT_DIR")"
assert_equals "$(cat "$POETRY_PWD_LOG")" "$REPO_ROOT/agent-brain-cli" "poetry cwd"
assert_equals "$(cat "$POETRY_LOG")" "run agent-brain install-agent --agent codex --project --path $PROJECT_DIR --json" "poetry command"
echo "$INSTALL_OUTPUT" | grep -q '"target_dir"' || fail "install output missing target_dir"
mkdir -p "$FAKE_TARGET_DIR"
VERIFY_OUTPUT="$(runtime_verify_install codex "$RUNTIME_ROOT" "$FAKE_TARGET_DIR" "$INSTALL_OUTPUT" "printf '{\"status\":\"ok\"}\n'")"
echo "$VERIFY_OUTPUT" | grep -q '"status":"verified"' || fail "verify_install should report verified"

runtime_is_forbidden_global_path "$HOME/.codex/skills/agent-brain"
runtime_is_forbidden_global_path "$HOME/.config/opencode/plugins/agent-brain"
runtime_is_forbidden_global_path "$HOME/.config/gemini/plugins/agent-brain"

if runtime_is_forbidden_global_path "$PROJECT_DIR/.codex/skills/agent-brain"; then
  fail "project-local install path was treated as forbidden"
fi

set +e
export FAKE_TARGET_DIR="$HOME/.codex/skills/agent-brain"
FORBIDDEN_OUTPUT="$(runtime_install_project_local codex "$PROJECT_DIR" 2>&1)"
FORBIDDEN_EXIT=$?
set -e
if [[ $FORBIDDEN_EXIT -eq 0 ]]; then
  fail "expected forbidden global target to fail"
fi
echo "$FORBIDDEN_OUTPUT" | grep -q '"error_type":"forbidden_global_path"' || fail "missing forbidden global error_type"
echo "$FORBIDDEN_OUTPUT" | grep -q '"remediation":"' || fail "missing remediation"
assert_file "$RUNTIME_ROOT/logs/failure.log"

workspace_clean "$SCENARIO_WORKSPACE"
[[ ! -d "$SCENARIO_WORKSPACE/codex-runtime/project" ]] || fail "project directory should be removed on success"
assert_file "$SCENARIO_WORKSPACE/scenario.log"

TEMPLATE_AFTER="$(snapshot_tree "$TEMPLATE_DIR")"
assert_equals "$TEMPLATE_AFTER" "$TEMPLATE_BEFORE" "fixture template changed"

rm -rf "$RUNS_DIR"
echo "runtime project plumbing passed"
