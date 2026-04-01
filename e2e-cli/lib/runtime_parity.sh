#!/usr/bin/env bash
set -euo pipefail

# Helper functions used by runtime parity scenarios and guards.
E2E_ROOT="${E2E_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
REPO_ROOT="${REPO_ROOT:-$(cd "$E2E_ROOT/.." && pwd)}"

_runtime_parity_abs_path() {
  python3 - "$1" <<'PY'
from pathlib import Path
import sys

print(Path(sys.argv[1]).expanduser().resolve())
PY
}

runtime_fixture_template_dir() {
  echo "${E2E_ROOT}/fixtures/runtime-project-template"
}

runtime_expected_target_relpath() {
  local runtime="$1"
  case "$runtime" in
    codex) echo ".codex/skills/agent-brain" ;;
    opencode) echo ".opencode/plugins/agent-brain" ;;
    gemini) echo ".gemini/plugins/agent-brain" ;;
    *)
      echo "unsupported runtime: $runtime" >&2
      return 1
      ;;
  esac
}

runtime_is_forbidden_global_path() {
  local abs_path
  abs_path="$(_runtime_parity_abs_path "$1")"

  local forbidden_roots=(
    "${HOME}/.codex"
    "${HOME}/.config/opencode"
    "${HOME}/.config/gemini"
  )

  local root
  for root in "${forbidden_roots[@]}"; do
    local abs_root
    abs_root="$(_runtime_parity_abs_path "$root")"
    case "${abs_path}/" in
      "${abs_root}/"*)
        return 0
        ;;
    esac
  done

  return 1
}

runtime_assert_repo_owned_project_dir() {
  local project_dir="$1"
  local abs_project
  abs_project="$(_runtime_parity_abs_path "$project_dir")"

  if runtime_is_forbidden_global_path "$abs_project"; then
    echo "forbidden global install path: $abs_project" >&2
    return 1
  fi

  local allowed_roots=(
    "${REPO_ROOT}/e2e_workdir"
  )
  if [[ -n "${RUNTIME_PARITY_ALLOWED_ROOTS:-}" ]]; then
    IFS=':' read -r -a extra_roots <<< "${RUNTIME_PARITY_ALLOWED_ROOTS}"
    allowed_roots+=("${extra_roots[@]}")
  fi

  local root
  for root in "${allowed_roots[@]}"; do
    [[ -n "$root" ]] || continue
    local abs_root
    abs_root="$(_runtime_parity_abs_path "$root")"
    case "${abs_project}/" in
      "${abs_root}/"*)
        return 0
        ;;
    esac
  done

  echo "project dir must live under repo-owned runtime workdir: $abs_project" >&2
  return 1
}

runtime_workspace_root() {
  local runtime="$1"
  local scenario_root="$2"
  printf '%s/%s-runtime\n' "${scenario_root%/}" "$runtime"
}

runtime_workspace_prepare() {
  local runtime="$1"
  local scenario_root="$2"
  local template_dir
  template_dir="$(runtime_fixture_template_dir)"
  local runtime_root
  runtime_root="$(runtime_workspace_root "$runtime" "$scenario_root")"
  local project_dir="${runtime_root}/project"
  local abs_project
  abs_project="$(_runtime_parity_abs_path "$project_dir")"
  local abs_template
  abs_template="$(_runtime_parity_abs_path "$template_dir")"

  runtime_expected_target_relpath "$runtime" >/dev/null
  runtime_assert_repo_owned_project_dir "$abs_project"

  [[ -d "$template_dir" ]] || {
    echo "runtime parity fixture template missing: $template_dir" >&2
    return 1
  }

  if [[ "$abs_project" == "$abs_template" ]]; then
    echo "refusing to use the checked-in fixture as the runtime workspace" >&2
    return 1
  fi

  mkdir -p "$runtime_root/cleanup" "$runtime_root/logs"
  rm -rf "$project_dir"
  mkdir -p "$project_dir"
  cp -R "$template_dir/." "$project_dir/"

  echo "$project_dir"
}

runtime_failure_log_path() {
  local workspace="$1"
  printf '%s/logs/failure.log\n' "${workspace%/}"
}

runtime_write_failure_log() {
  local workspace="$1"
  local runtime="$2"
  local error_type="$3"
  local details="$4"
  local log_file
  log_file="$(runtime_failure_log_path "$workspace")"
  mkdir -p "$(dirname "$log_file")"
  printf '%s [%s] %s: %s\n' "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" "$runtime" "$error_type" "$details" >> "$log_file"
}

runtime_failure_json() {
  local runtime="$1"
  local error_type="$2"
  local details="$3"
  local remediation="$4"
  local workspace="$5"
  printf '{"runtime":"%s","status":"failed","error_type":"%s","details":"%s","remediation":"%s","workspace":"%s"}\n' \
    "$(printf '%s' "$runtime" | sed 's/"/\\"/g')" \
    "$(printf '%s' "$error_type" | sed 's/"/\\"/g')" \
    "$(printf '%s' "$details" | sed ':a;N;$!ba;s/\n/\\n/g; s/"/\\"/g')" \
    "$(printf '%s' "$remediation" | sed ':a;N;$!ba;s/\n/\\n/g; s/"/\\"/g')" \
    "$(printf '%s' "$workspace" | sed 's/"/\\"/g')"
}

runtime_emit_failure() {
  local runtime="$1"
  local workspace="$2"
  local error_type="$3"
  local details="$4"
  local remediation="$5"
  runtime_write_failure_log "$workspace" "$runtime" "$error_type" "$details"
  runtime_failure_json "$runtime" "$error_type" "$details" "$remediation" "$workspace"
  return 1
}

runtime_extract_target_dir() {
  local payload="$1"
  printf '%s\n' "$payload" | tr -d '\n' | sed -n 's/.*"target_dir"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p'
}

runtime_json_looks_valid() {
  local payload="$1"
  [[ "$payload" == *"{"* ]] && [[ "$payload" == *"}"* ]]
}

runtime_install_project_local() {
  local runtime="$1"
  local project_dir="$2"
  shift 2

  local abs_project
  abs_project="$(_runtime_parity_abs_path "$project_dir")"
  local runtime_root
  runtime_root="$(cd "$(dirname "$project_dir")" && pwd)"
  if ! runtime_assert_repo_owned_project_dir "$abs_project"; then
    runtime_emit_failure "$runtime" "$runtime_root" "forbidden_global_path" \
      "project dir must live under repo-owned runtime workdir: $abs_project" \
      "Use --project --path <repo-owned-dir> under e2e_workdir and retry."
    return 1
  fi

  local expected_relpath
  expected_relpath="$(runtime_expected_target_relpath "$runtime")"
  local expected_target="${abs_project}/${expected_relpath}"
  local output

  output="$(
    cd "$REPO_ROOT/agent-brain-cli" &&
      poetry run agent-brain install-agent --agent "$runtime" \
        --project \
        --path "$project_dir" \
        --json \
        "$@"
  )"

  local target_dir
  target_dir="$(runtime_extract_target_dir "$output")"
  if [[ -z "$target_dir" ]]; then
    runtime_emit_failure "$runtime" "$runtime_root" "malformed_json" \
      "install-agent JSON output missing target_dir" \
      "Inspect the raw installer output in the scenario logs and ensure the runtime emits valid JSON."
    return 1
  fi

  local abs_target
  abs_target="$(_runtime_parity_abs_path "$target_dir")"
  if runtime_is_forbidden_global_path "$abs_target"; then
    runtime_emit_failure "$runtime" "$runtime_root" "forbidden_global_path" \
      "forbidden global install target resolved: $abs_target" \
      "Use --project --path <repo-owned-dir> under e2e_workdir and inspect the offending target."
    return 1
  fi
  if [[ "$abs_target" != "$expected_target" ]]; then
    runtime_emit_failure "$runtime" "$runtime_root" "install_verification_failed" \
      "unexpected install target: $abs_target (expected $expected_target)" \
      "Inspect the installer mapping for the runtime and confirm target_dir resolves inside the project workspace."
    return 1
  fi

  printf '%s\n' "$output"
}

runtime_verify_install() {
  local runtime="$1"
  local workspace="$2"
  local expected_target="$3"
  local install_json="$4"
  local dry_probe_cmd="${5:-}"

  mkdir -p "${workspace%/}/logs"

  if [[ ! -d "$workspace" ]]; then
    runtime_emit_failure "$runtime" "$workspace" "install_verification_failed" \
      "runtime workspace missing: $workspace" \
      "Recreate the runtime workspace under e2e_workdir before re-running verification."
    return 1
  fi
  if [[ ! -d "$expected_target" ]]; then
    runtime_emit_failure "$runtime" "$workspace" "install_verification_failed" \
      "expected install target missing: $expected_target" \
      "Verify the installer created the project-local target directory before runtime execution."
    return 1
  fi
  if [[ ! -d "${workspace%/}/logs" ]]; then
    runtime_emit_failure "$runtime" "$workspace" "install_verification_failed" \
      "runtime log directory missing: ${workspace%/}/logs" \
      "Ensure the workspace scaffolding created logs/ before runtime verification."
    return 1
  fi

  local parsed_target
  parsed_target="$(runtime_extract_target_dir "$install_json")"
  if [[ -z "$parsed_target" ]]; then
    runtime_emit_failure "$runtime" "$workspace" "malformed_json" \
      "install verification payload missing target_dir" \
      "Inspect the runtime command and preserve the raw output in logs."
    return 1
  fi

  local abs_parsed_target abs_expected_target
  abs_parsed_target="$(_runtime_parity_abs_path "$parsed_target")"
  abs_expected_target="$(_runtime_parity_abs_path "$expected_target")"
  if [[ "$abs_parsed_target" != "$abs_expected_target" ]]; then
    runtime_emit_failure "$runtime" "$workspace" "install_verification_failed" \
      "install JSON target mismatch: $abs_parsed_target != $abs_expected_target" \
      "Inspect the installer JSON and confirm target_dir points to the project-local runtime workspace."
    return 1
  fi

  if [[ -n "$dry_probe_cmd" ]]; then
    local probe_output
    if ! probe_output="$(eval "$dry_probe_cmd" 2>&1)"; then
      runtime_emit_failure "$runtime" "$workspace" "missing_cli" \
        "dry probe command failed: $probe_output" \
        "Install the runtime CLI or place a test double in PATH before running parity verification."
      return 1
    fi
    if ! runtime_json_looks_valid "$probe_output"; then
      runtime_emit_failure "$runtime" "$workspace" "malformed_json" \
        "dry probe returned non-JSON output: $probe_output" \
        "Inspect the runtime command and preserve the raw output in logs."
      return 1
    fi
  fi

  printf '{"runtime":"%s","status":"verified","target_dir":"%s","workspace":"%s"}\n' \
    "$runtime" "$abs_expected_target" "$workspace"
}

runtime_parity_install_opencode_project() {
  local workspace="$1"
  shift
  runtime_install_project_local opencode "$workspace" "$@"
}

runtime_parity_snapshot_global_opencode() {
  local snapshot_file="$1"
  local config_dir="${HOME}/.config/opencode"
  mkdir -p "$config_dir"
  find "$config_dir" -print | sort > "$snapshot_file"
}

runtime_parity_detect_global_mutation() {
  local before="$1"
  local after="$2"
  local workspace="${3:-}"
  if ! diff -u "$before" "$after" >/tmp/gsd-runtime-diff.log; then
    if [[ -n "$workspace" ]]; then
      runtime_emit_failure "opencode" "$workspace" "global_path_mutated" \
        "$(cat /tmp/gsd-runtime-diff.log)" \
        "Use --project --path <repo-owned-dir>, inspect the mutation diff, and remove writes to ~/.config/opencode."
    fi
    echo "global_path_mutated" >&2
    cat /tmp/gsd-runtime-diff.log >&2
    return 1
  fi
  return 0
}
