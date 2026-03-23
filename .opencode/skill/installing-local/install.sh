#!/bin/bash
# Local install script for Agent Brain development
# Usage: ./install.sh
#
# This script:
# 1. Verifies Python 3.11 is available
# 2. Kills ALL running agent-brain servers
# 3. Uninstalls ALL old versions (CLI + server)
# 4. Builds fresh packages
# 5. Installs with uv tool
# 6. Verifies installed code is NEW (not stale)
# 7. Deploys plugin
# 8. Runs verification checks

set -e

USE_PATH_DEPS=0
RESTORE_PYPI=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --use-path-deps)
      USE_PATH_DEPS=1
      ;;
    --restore-pypi)
      RESTORE_PYPI=1
      ;;
    -h|--help)
      echo "Usage: ./install.sh [--use-path-deps] [--restore-pypi]"
      echo "  --use-path-deps   Switch CLI dependency to local path (for fast local dev builds)"
      echo "  --restore-pypi    Switch CLI dependency back to PyPI (matches server version) before release"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
  shift
done

if [[ $USE_PATH_DEPS -eq 1 && $RESTORE_PYPI -eq 1 ]]; then
  echo "ERROR: Choose either --use-path-deps or --restore-pypi, not both."
  exit 1
fi

REPO_ROOT="${HOME}/clients/spillwave/src/agent-brain"
PLUGIN_CACHE="$HOME/.claude/plugins/agent-brain"
UV_TOOL_CLI="$HOME/.local/share/uv/tools/agent-brain-cli"
UV_TOOL_SERVER="$HOME/.local/share/uv/tools/agent-brain-server"

echo "=== Step 1: Verify Python 3.11 Available ==="

if ! python3.11 --version > /dev/null 2>&1; then
    echo "ERROR: Python 3.11 required but not found"
    echo "Install with: brew install python@3.11"
    exit 1
fi
python3.11 --version
echo "Python 3.11 OK"

echo ""
echo "=== Step 2: Kill ALL Running Servers (Aggressive) ==="

# Kill by process name (force)
pkill -9 -f "agent_brain_server" 2>/dev/null || true
pkill -9 -f "uvicorn" 2>/dev/null || true

# Kill by port range (8000-8010)
for port in $(seq 8000 8010); do
  pid=$(lsof -i :$port -t 2>/dev/null || true)
  if [ -n "$pid" ]; then
    echo "Killing process on port $port (PID: $pid)"
    kill -9 $pid 2>/dev/null || true
  fi
done

sleep 2

# Verify no servers running (pgrep returns 1 if no match, which is success for us)
if pgrep -f "agent_brain_server" > /dev/null 2>&1; then
    echo "WARNING: Some servers may still be running"
    pgrep -fl "agent_brain_server" || true
else
    echo "All servers stopped"
fi

echo ""
echo "=== Step 3: Uninstall ALL Old Versions ==="

# Uninstall from uv tool (both CLI and server)
uv tool uninstall agent-brain-cli 2>/dev/null || true
uv tool uninstall agent-brain-server 2>/dev/null || true

# Remove ALL cached tool environments
rm -rf "$UV_TOOL_CLI" 2>/dev/null || true
rm -rf "$UV_TOOL_SERVER" 2>/dev/null || true

# Also remove any stale pipx installs
pipx uninstall agent-brain-cli 2>/dev/null || true
pipx uninstall agent-brain-server 2>/dev/null || true

echo "All old installations removed"

echo ""
echo "=== Step 4: Clean and Build Fresh Packages ==="

rm -rf "$REPO_ROOT/agent-brain-server/dist"
rm -rf "$REPO_ROOT/agent-brain-cli/dist"

# Toggle dependency for local vs PyPI
CLI_PYPROJECT="$REPO_ROOT/agent-brain-cli/pyproject.toml"
if [[ $USE_PATH_DEPS -eq 1 ]]; then
  if grep -q 'agent-brain-rag = {path = "../agent-brain-server"' "$CLI_PYPROJECT"; then
    echo "CLI already using path dependency."
  else
    echo "Switching CLI dependency to local path (develop=true)..."
    perl -0pi -e 's|agent-brain-rag = [^\n]+|agent-brain-rag = {path = "../agent-brain-server", develop = true}|g' "$CLI_PYPROJECT"
    (cd "$REPO_ROOT/agent-brain-cli" && poetry lock)
  fi
fi

if [[ $RESTORE_PYPI -eq 1 ]]; then
  VERSION=$(grep '^version = ' "$REPO_ROOT/agent-brain-server/pyproject.toml" | cut -d'"' -f2)
  if grep -q 'agent-brain-rag = {path = "../agent-brain-server"' "$CLI_PYPROJECT"; then
    echo "Restoring CLI dependency to PyPI (^$VERSION)..."
    perl -0pi -e "s|agent-brain-rag = [^\\n]+|agent-brain-rag = \"^$VERSION\"|g" "$CLI_PYPROJECT"
    (cd "$REPO_ROOT/agent-brain-cli" && poetry lock)
  else
    echo "CLI dependency already pointing to PyPI."
  fi
fi

cd "$REPO_ROOT/agent-brain-server"
echo "Building server..."
poetry build

cd "$REPO_ROOT/agent-brain-cli"
echo "Building CLI..."
poetry build

echo ""
echo "=== Step 5: Install with uv tool ==="

cd "$REPO_ROOT"

# Find the latest wheels
CLI_WHEEL=$(ls -t "$REPO_ROOT/agent-brain-cli/dist/"agent_brain_cli-*.whl | head -1)
SERVER_WHEEL=$(ls -t "$REPO_ROOT/agent-brain-server/dist/"agent_brain_rag-*.whl | head -1)

echo "Installing CLI: $CLI_WHEEL"

# When using path deps, the CLI wheel already includes the server dependency via path reference
# When using PyPI deps, we need to install the local server wheel explicitly
if [[ $USE_PATH_DEPS -eq 1 ]]; then
    echo "Mode: Path dependencies (server linked via local path)"
    uv tool install "$CLI_WHEEL" --force --python 3.11
else
    echo "Mode: PyPI dependencies (including local server wheel)"
    echo "With server: $SERVER_WHEEL"
    uv tool install "$CLI_WHEEL" --with "$SERVER_WHEEL" --force --python 3.11
fi

echo ""
echo "=== Step 6: Verify Installed Code is NEW ==="

# Check the config loader has new search order (check file directly, not import)
PROVIDER_CONFIG="$HOME/.local/share/uv/tools/agent-brain-cli/lib/python3.11/site-packages/agent_brain_server/config/provider_config.py"

if grep -q "AGENT_BRAIN_CONFIG" "$PROVIDER_CONFIG" && grep -q ".claude/agent-brain" "$PROVIDER_CONFIG"; then
    CONFIG_CHECK="NEW_CODE"
elif grep -q "DOC_SERVE_CONFIG" "$PROVIDER_CONFIG" || grep -q ".claude/doc-serve" "$PROVIDER_CONFIG"; then
    CONFIG_CHECK="OLD_CODE"
else
    CONFIG_CHECK="UNKNOWN"
fi

if [ "$CONFIG_CHECK" = "OLD_CODE" ]; then
    echo "ERROR: Old code still installed! Found DOC_SERVE references."
    echo "The uv cache may be corrupted. Try:"
    echo "  rm -rf ~/.cache/uv"
    echo "  Then run this script again."
    exit 1
elif [ "$CONFIG_CHECK" = "NEW_CODE" ]; then
    echo "Verified: New code installed (AGENT_BRAIN_CONFIG + .claude/agent-brain)"
else
    echo "WARNING: Could not verify code version"
fi

echo ""
echo "=== Step 7: Path Sanity Check ==="

AGENT_BRAIN_PATH=$(which agent-brain)
echo "agent-brain location: $AGENT_BRAIN_PATH"

if [[ "$AGENT_BRAIN_PATH" != *".local/bin/agent-brain"* ]]; then
    echo "WARNING: agent-brain not in expected location (~/.local/bin/)"
    echo "Check your PATH for conflicts"
fi

agent-brain --version

echo ""
echo "=== Step 8: Deploy Plugin ==="

rm -rf "$PLUGIN_CACHE"
cp -r "$REPO_ROOT/agent-brain-plugin" "$PLUGIN_CACHE"
echo "Plugin deployed to: $PLUGIN_CACHE"

# Version check
CLI_VERSION=$(agent-brain --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "unknown")
PLUGIN_VERSION=$(grep -oE '"version":\s*"[0-9]+\.[0-9]+\.[0-9]+"' "$PLUGIN_CACHE/.claude-plugin/plugin.json" 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "unknown")

echo "CLI version: $CLI_VERSION"
echo "Plugin version: $PLUGIN_VERSION"

if [ "$CLI_VERSION" != "$PLUGIN_VERSION" ] && [ "$PLUGIN_VERSION" != "unknown" ]; then
    echo "WARNING: Version mismatch between CLI and plugin"
fi

echo ""
echo "=== Local Install Complete! ==="
echo ""
echo "Installed:"
echo "  CLI: $AGENT_BRAIN_PATH"
echo "  Plugin: $PLUGIN_CACHE"
echo ""
echo "Next steps:"
echo "  1. Go to your project directory"
echo "  2. Ensure .claude/agent-brain/config.yaml exists"
echo "  3. Run: agent-brain start"
echo ""
echo "If other Claude instances had servers running, restart them:"
echo "  agent-brain stop && agent-brain start"
