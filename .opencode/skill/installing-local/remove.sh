#!/bin/bash
# Remove local Agent Brain installations, caches, and plugin artifacts
# Usage: ./remove.sh [--restore-pypi] [--zero-state]
#
# This script ONLY removes - it does NOT build or install anything.
# Use install.sh for rebuilding after removal.

RESTORE_PYPI=0
ZERO_STATE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --restore-pypi)
      RESTORE_PYPI=1
      ;;
    --zero-state)
      ZERO_STATE=1
      ;;
    -h|--help)
      echo "Usage: ./remove.sh [--restore-pypi] [--zero-state]"
      echo "  --restore-pypi   Restore CLI dependency to PyPI (^<server_version>)"
      echo "  --zero-state     Also remove ~/.config/agent-brain and ./.claude/agent-brain (BACK UP FIRST)"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
  shift
done

# Script is at .claude/skills/installing-local/remove.sh - go up 4 levels to repo root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

echo "=== Agent Brain Local Removal ==="
echo "Repo root: $REPO_ROOT"
echo ""

# --- Step 1: Kill servers ---
echo "=== Step 1: Kill Running Servers ==="
pkill -9 -f "agent_brain_server" 2>/dev/null || true
pkill -9 -f "uvicorn" 2>/dev/null || true

for port in $(seq 8000 8010); do
  pid=$(lsof -i :$port -t 2>/dev/null)
  if [ -n "$pid" ]; then
    echo "  Killing process on port $port (PID: $pid)"
    kill -9 "$pid" 2>/dev/null || true
  fi
done
sleep 1
echo "  Servers stopped"
echo ""

# --- Step 2: Uninstall tools ---
echo "=== Step 2: Uninstall Tools ==="

# uv tool
uv tool uninstall agent-brain-cli 2>/dev/null && echo "  Uninstalled agent-brain-cli (uv)" || echo "  agent-brain-cli not installed via uv"
uv tool uninstall agent-brain-server 2>/dev/null && echo "  Uninstalled agent-brain-server (uv)" || echo "  agent-brain-server not installed via uv"

# Remove uv tool directories
rm -rf "$HOME/.local/share/uv/tools/agent-brain-cli" 2>/dev/null && echo "  Removed uv tool CLI dir" || true
rm -rf "$HOME/.local/share/uv/tools/agent-brain-server" 2>/dev/null && echo "  Removed uv tool server dir" || true

# pipx
pipx uninstall agent-brain-cli 2>/dev/null && echo "  Uninstalled agent-brain-cli (pipx)" || echo "  agent-brain-cli not installed via pipx"
pipx uninstall agent-brain-server 2>/dev/null && echo "  Uninstalled agent-brain-server (pipx)" || echo "  agent-brain-server not installed via pipx"

# Remove binary symlinks (uv sometimes leaves these behind)
for bin in agent-brain agent-brain-serve; do
  for bindir in "$HOME/.local/bin" "/usr/local/bin"; do
    if [ -f "$bindir/$bin" ] || [ -L "$bindir/$bin" ]; then
      rm -f "$bindir/$bin" 2>/dev/null && echo "  Removed binary: $bindir/$bin" || true
    fi
  done
done
echo ""

# --- Step 3: Clear caches ---
echo "=== Step 3: Clear Caches ==="
if [ -d "$HOME/.cache/uv" ]; then
  rm -rf "$HOME/.cache/uv"
  echo "  Cleared uv cache"
else
  echo "  No uv cache found"
fi

pip cache remove agent-brain-rag 2>/dev/null || true
pip cache remove agent-brain-cli 2>/dev/null || true
echo "  pip cache cleanup attempted"
echo ""

# --- Step 4: Remove config and plugin artifacts ---
echo "=== Step 4: Remove Config and Plugin Artifacts ==="

# XDG config dir (~/.config/agent-brain) — always remove for clean slate
if [ -d "$HOME/.config/agent-brain" ]; then
  rm -rf "$HOME/.config/agent-brain"
  echo "  Removed ~/.config/agent-brain"
else
  echo "  No ~/.config/agent-brain found"
fi

# Legacy home config (~/.agent-brain)
if [ -d "$HOME/.agent-brain" ]; then
  rm -rf "$HOME/.agent-brain"
  echo "  Removed ~/.agent-brain"
fi
echo ""

echo "=== Step 4b: Remove Plugin Artifacts ==="
if [ -d "$HOME/.claude/plugins/cache/agent-brain-marketplace" ]; then
  rm -rf "$HOME/.claude/plugins/cache/agent-brain-marketplace"
  echo "  Removed marketplace cache"
else
  echo "  No marketplace cache found"
fi

if [ -d "$HOME/.claude/plugins/agent-brain" ]; then
  rm -rf "$HOME/.claude/plugins/agent-brain"
  echo "  Removed deployed plugin"
else
  echo "  No deployed plugin found"
fi
echo ""

# --- Step 5: Restore PyPI dependency (optional) ---
if [[ $RESTORE_PYPI -eq 1 ]]; then
  echo "=== Step 5: Restore CLI Dependency to PyPI ==="
  CLI_PYPROJECT="$REPO_ROOT/agent-brain-cli/pyproject.toml"
  if [ -f "$CLI_PYPROJECT" ]; then
    VERSION=$(grep '^version = ' "$REPO_ROOT/agent-brain-server/pyproject.toml" 2>/dev/null | cut -d'"' -f2)
    if grep -q 'agent-brain-rag = {path = "../agent-brain-server"' "$CLI_PYPROJECT"; then
      echo "  Found path dependency, restoring to PyPI (^$VERSION)..."
      perl -0pi -e "s|agent-brain-rag = [^\\n]+|agent-brain-rag = \"^$VERSION\"|g" "$CLI_PYPROJECT"
      (cd "$REPO_ROOT/agent-brain-cli" && poetry lock --no-update 2>/dev/null)
      echo "  CLI dependency restored to PyPI"
    else
      echo "  CLI dependency already pointing to PyPI"
    fi
  else
    echo "  CLI pyproject.toml not found (not in repo root?)"
  fi
  echo ""
fi

# --- Step 6: Zero-state cleanup (optional) ---
if [[ $ZERO_STATE -eq 1 ]]; then
  echo "=== Step 6: Zero-State Cleanup ==="
  echo "  WARNING: Removing all Agent Brain state directories!"

  # Primary state dir (current)
  if [ -d "$HOME/.config/agent-brain" ]; then
    rm -rf "$HOME/.config/agent-brain"
    echo "  Removed ~/.config/agent-brain"
  fi

  # Legacy state dir (superseded, clean up if still present)
  if [ -d "$HOME/.claude/agent-brain" ]; then
    rm -rf "$HOME/.claude/agent-brain"
    echo "  Removed ~/.claude/agent-brain (legacy)"
  fi

  if [ -d "$REPO_ROOT/.claude/agent-brain" ]; then
    rm -rf "$REPO_ROOT/.claude/agent-brain"
    echo "  Removed project .claude/agent-brain"
  fi
  echo ""
fi

# --- Guaranteed clean: detect and remove any surviving binaries ---
_try_remove_binary() {
  local bin="$1"
  local found
  found=$(which "$bin" 2>/dev/null) || return 0  # already gone, nothing to do

  echo "  Still found: $found — detecting source..."

  case "$found" in
    "$HOME/.local/share/uv/"*|"$HOME/.local/bin/"*)
      echo "  Source: uv — running uv tool uninstall agent-brain-cli"
      uv tool uninstall agent-brain-cli 2>/dev/null || true
      rm -f "$found" 2>/dev/null || true
      ;;
    "$HOME/.local/share/pipx/"*|"$HOME/.local/pipx/"*)
      echo "  Source: pipx — running pipx uninstall agent-brain-cli"
      pipx uninstall agent-brain-cli 2>/dev/null || true
      ;;
    "/opt/homebrew/"*|"/usr/local/Cellar/"*|"/usr/local/bin/agent-brain"*)
      echo "  Source: homebrew — running brew uninstall agent-brain"
      brew uninstall agent-brain 2>/dev/null || brew uninstall agent-brain-cli 2>/dev/null || true
      rm -f "$found" 2>/dev/null || true
      ;;
    "$HOME/.pyenv/shims/"*)
      echo "  Source: pyenv shim — removing shim and rehashing"
      rm -f "$found" 2>/dev/null || true
      pyenv rehash 2>/dev/null || true
      ;;
    */site-packages/*|*/dist-packages/*)
      echo "  Source: pip install — running pip uninstall"
      pip uninstall -y agent-brain-cli agent-brain-rag 2>/dev/null || true
      pip3 uninstall -y agent-brain-cli agent-brain-rag 2>/dev/null || true
      ;;
    *)
      echo "  Source: unknown ($found) — attempting direct removal"
      rm -f "$found" 2>/dev/null || true
      ;;
  esac
}

echo "=== Guaranteed Clean: Binary Check ==="
for bin in agent-brain agent-brain-serve; do
  max_attempts=5
  attempt=0
  while which "$bin" >/dev/null 2>&1; do
    attempt=$((attempt + 1))
    if [ $attempt -gt $max_attempts ]; then
      echo "  ERROR: $bin still at $(which $bin) after $max_attempts attempts — manual removal required"
      break
    fi
    _try_remove_binary "$bin"
  done
  if ! which "$bin" >/dev/null 2>&1; then
    echo "  $bin: clean"
  fi
done
echo ""

# --- Final verification ---
echo "=== Verification ==="
if [ -d "$HOME/.config/agent-brain" ]; then
  echo "  WARNING: ~/.config/agent-brain still exists"
else
  echo "  ~/.config/agent-brain removed"
fi

if pgrep -f "agent_brain_server" >/dev/null 2>&1; then
  echo "  WARNING: agent_brain_server processes still running"
else
  echo "  No agent_brain_server processes running"
fi

if pgrep -f "uvicorn" >/dev/null 2>&1; then
  echo "  Note: uvicorn processes still running (may be from other projects)"
else
  echo "  No uvicorn processes running"
fi

echo ""
echo "=== Removal Complete ==="
echo ""
echo "To reinstall, run: /ag-install-local"
