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
    "${E2E_ROOT}/.runs"
    "${REPO_ROOT}/.tmp"
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

  echo "project dir must live under repo-owned runtime runs: $abs_project" >&2
  return 1
}

runtime_workspace_prepare() {
  local runtime="$1"
  local scenario_root="$2"
  local template_dir
  template_dir="$(runtime_fixture_template_dir)"
  local project_dir="${scenario_root%/}/project"
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

  mkdir -p "$scenario_root"
  rm -rf "$project_dir"
  mkdir -p "$project_dir"
  cp -R "$template_dir/." "$project_dir/"

  echo "$project_dir"
}

runtime_install_project_local() {
  local runtime="$1"
  local project_dir="$2"
  shift 2

  local abs_project
  abs_project="$(_runtime_parity_abs_path "$project_dir")"
  runtime_assert_repo_owned_project_dir "$abs_project"

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
  target_dir="$(
    python3 -c '
import json
import sys

payload = json.loads(sys.argv[1])
target_dir = payload.get("target_dir")
if not target_dir:
    raise SystemExit(1)
print(target_dir)
' "$output"
  )" || {
    echo "install-agent JSON output missing target_dir" >&2
    return 1
  }

  local abs_target
  abs_target="$(_runtime_parity_abs_path "$target_dir")"
  if runtime_is_forbidden_global_path "$abs_target"; then
    echo "forbidden global install target resolved: $abs_target" >&2
    return 1
  fi
  if [[ "$abs_target" != "$expected_target" ]]; then
    echo "unexpected install target: $abs_target (expected $expected_target)" >&2
    return 1
  fi

  printf '%s\n' "$output"
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
  if ! diff -u "$before" "$after" >/tmp/gsd-runtime-diff.log; then
    echo "global_path_mutated" >&2
    cat /tmp/gsd-runtime-diff.log >&2
    return 1
  fi
  return 0
}
