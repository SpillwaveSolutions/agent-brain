#!/usr/bin/env bash
# Fail if any plugin/marketplace manifest version drifts from the server
# package version. Going from 1 manifest to 5+ (issue #239) multiplies the
# failure mode that left marketplace users on 2.0.0 for years.
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

EXPECTED="$(grep '^version = ' agent-brain-server/pyproject.toml | cut -d'"' -f2)"
if [[ -z "$EXPECTED" ]]; then
  echo "ERROR: could not read version from agent-brain-server/pyproject.toml" >&2
  exit 1
fi

fail=0
check_json() {
  local path="$1"
  local jq_expr="$2"
  local label="${3:-$path}"
  if [[ ! -f "$path" ]]; then
    echo "ERROR: missing $label" >&2
    fail=1
    return
  fi
  local got
  got="$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); v=$jq_expr; print(v)" "$path")"
  if [[ "$got" != "$EXPECTED" ]]; then
    echo "ERROR: $label is '$got'; expected '$EXPECTED'" >&2
    fail=1
  else
    echo "ok $label = $got"
  fi
}

check_toml_version() {
  local path="$1"
  local got
  got="$(grep '^version = ' "$path" | cut -d'"' -f2)"
  if [[ "$got" != "$EXPECTED" ]]; then
    echo "ERROR: $path is '$got'; expected '$EXPECTED'" >&2
    fail=1
  else
    echo "ok $path = $got"
  fi
}

check_py_version() {
  local path="$1"
  local got
  got="$(grep -E '^__version__ = ' "$path" | cut -d'"' -f2)"
  if [[ "$got" != "$EXPECTED" ]]; then
    echo "ERROR: $path is '$got'; expected '$EXPECTED'" >&2
    fail=1
  else
    echo "ok $path = $got"
  fi
}

check_toml_version agent-brain-cli/pyproject.toml
check_toml_version agent-brain-uds/pyproject.toml
check_toml_version agent-brain-mcp/pyproject.toml
check_py_version agent-brain-server/agent_brain_server/__init__.py
check_py_version agent-brain-cli/agent_brain_cli/__init__.py
check_py_version agent-brain-uds/agent_brain_uds/__init__.py
check_py_version agent-brain-mcp/agent_brain_mcp/__init__.py

check_json agent-brain-plugin/.claude-plugin/plugin.json 'd["version"]'
check_json .claude-plugin/marketplace.json 'd["plugins"][0]["version"]' ".claude-plugin/marketplace.json plugins[0].version"
check_json agent-brain-plugin/plugin.json 'd["version"]'
check_json agent-brain-plugin/.codex-plugin/plugin.json 'd["version"]'
check_json agent-brain-plugin/.cursor-plugin/plugin.json 'd["version"]'
check_json agent-brain-plugin/.grok-plugin/marketplace.json 'd["version"]' "agent-brain-plugin/.grok-plugin/marketplace.json version"
check_json agent-brain-plugin/.grok-plugin/marketplace.json 'd["plugins"][0]["version"]' "agent-brain-plugin/.grok-plugin/marketplace.json plugins[0].version"

if [[ "$fail" -ne 0 ]]; then
  echo "Plugin/package versions drifted from $EXPECTED" >&2
  exit 1
fi
echo "✓ All package and plugin manifests are $EXPECTED"
