#!/usr/bin/env bash
set -euo pipefail

E2E_ROOT="${E2E_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
REPO_ROOT="${REPO_ROOT:-$(cd "$E2E_ROOT/.." && pwd)}"
RUNTIME_WORKDIR_ROOT="${RUNTIME_WORKDIR_ROOT:-${REPO_ROOT}/e2e_workdir}"
SERVER_HOST="${SERVER_HOST:-127.0.0.1}"
SERVER_PORT="${SERVER_PORT:-8000}"
SERVER_LOG_DIR="${SERVER_LOG_DIR:-${RUNTIME_WORKDIR_ROOT}/server}"
SERVER_PID_FILE="${SERVER_PID_FILE:-${SERVER_LOG_DIR}/agent-brain-server.pid}"
SERVER_STDOUT_LOG="${SERVER_STDOUT_LOG:-${SERVER_LOG_DIR}/server.log}"

log_info() { printf '[INFO] %s\n' "$*"; }
log_warn() { printf '[WARN] %s\n' "$*" >&2; }
log_fail() { printf '[FAIL] %s\n' "$*" >&2; }
log_ok() { printf '[ OK ] %s\n' "$*"; }
log_step() { printf '[STEP] %s\n' "$*"; }

assert_reset() {
  _ASSERT_TOTAL=0
  _ASSERT_PASSED=0
}

_assert_record() {
  local success="$1"
  local label="$2"
  _ASSERT_TOTAL=$((_ASSERT_TOTAL + 1))
  if [[ "$success" == "1" ]]; then
    _ASSERT_PASSED=$((_ASSERT_PASSED + 1))
    log_ok "$label"
    return 0
  fi
  log_fail "$label"
  return 1
}

assert_success() {
  local label="$1"
  shift
  if "$@"; then
    _assert_record 1 "$label"
  else
    _assert_record 0 "$label"
  fi
}

assert_failure() {
  local label="$1"
  shift
  if "$@"; then
    _assert_record 0 "$label"
  else
    _assert_record 1 "$label"
  fi
}

assert_contains() {
  local label="$1"
  local needle="$2"
  local haystack="$3"
  if [[ "$haystack" == *"$needle"* ]]; then
    _assert_record 1 "$label"
  else
    _assert_record 0 "$label"
  fi
}

assert_matches() {
  local label="$1"
  local pattern="$2"
  local haystack="$3"
  if [[ "$haystack" =~ $pattern ]]; then
    _assert_record 1 "$label"
  else
    _assert_record 0 "$label"
  fi
}

assert_json() {
  local label="$1"
  local field="$2"
  local expected="$3"
  local payload="$4"
  local key="${field#.}"
  local value
  value="$(printf '%s\n' "$payload" | tr -d '\n' | sed -n "s/.*\"${key}\"[[:space:]]*:[[:space:]]*\"\\{0,1\\}\\([^\",}]*\\)\"\\{0,1\\}.*/\\1/p")"
  if [[ -z "$value" && "$payload" != *"\"${key}\""* ]]; then
    _assert_record 0 "$label"
    return 1
  fi
  if [[ -n "$expected" && "$value" != "$expected" ]]; then
    _assert_record 0 "$label"
    return 1
  fi
  _assert_record 1 "$label"
}

assert_gt() {
  local label="$1"
  local actual="$2"
  local threshold="$3"
  if (( actual > threshold )); then
    _assert_record 1 "$label"
  else
    _assert_record 0 "$label"
  fi
}

assert_all_passed() {
  [[ "${_ASSERT_TOTAL:-0}" -eq "${_ASSERT_PASSED:-0}" ]]
}

workspace_create() {
  local scenario_name="$1"
  SCENARIO_WORKSPACE="${RUNTIME_WORKDIR_ROOT}/${RUN_ID}/${ADAPTER_NAME}/${scenario_name}"
  SCENARIO_LOG="${SCENARIO_WORKSPACE}/scenario.log"
  export SCENARIO_WORKSPACE SCENARIO_LOG RUNTIME_WORKDIR_ROOT
  mkdir -p "${SCENARIO_WORKSPACE}/cleanup" "${SCENARIO_WORKSPACE}/logs"
  : > "$SCENARIO_LOG"
  log_step "Workspace created: $SCENARIO_WORKSPACE"
}

workspace_clean() {
  local workspace="$1"
  rm -rf "${workspace%/}/project"
  local runtime_project
  for runtime_project in "${workspace%/}"/*-runtime/project; do
    [[ -e "$runtime_project" ]] || continue
    rm -rf "$runtime_project"
    log_step "Workspace cleaned: $runtime_project"
  done
  log_step "Workspace cleaned: ${workspace%/}/project"
}

workspace_preserve() {
  local workspace="$1"
  log_warn "Workspace preserved: $workspace"
}

server_is_running() {
  curl -sfL "http://${SERVER_HOST}:${SERVER_PORT}/health" >/dev/null 2>&1
}

server_start() {
  if server_is_running; then
    log_step "Server already running on ${SERVER_HOST}:${SERVER_PORT}"
    return 0
  fi

  mkdir -p "$SERVER_LOG_DIR"
  (
    cd "$REPO_ROOT/agent-brain-server"
    poetry run agent-brain-serve >"$SERVER_STDOUT_LOG" 2>&1
  ) &
  local pid=$!
  printf '%s\n' "$pid" > "$SERVER_PID_FILE"

  local attempts=0
  until server_is_running; do
    attempts=$((attempts + 1))
    if (( attempts >= 30 )); then
      log_fail "Server failed to start; see $SERVER_STDOUT_LOG"
      return 1
    fi
    sleep 1
  done

  log_step "Server started on ${SERVER_HOST}:${SERVER_PORT}"
}

server_stop() {
  if [[ -f "$SERVER_PID_FILE" ]]; then
    local pid
    pid="$(cat "$SERVER_PID_FILE")"
    if kill -0 "$pid" >/dev/null 2>&1; then
      kill "$pid" >/dev/null 2>&1 || true
      wait "$pid" 2>/dev/null || true
    fi
    rm -f "$SERVER_PID_FILE"
    log_step "Server stopped"
  fi
}

assert_reset
