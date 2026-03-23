# Local Install Skill

Builds and installs Agent Brain CLI/Server locally for rapid development and testing.

## When to Use

- After making code changes to agent-brain-server or agent-brain-cli
- When you need to test the plugin in another Claude instance
- When setting up a fresh development environment
- When the user says "local install", "install locally", "build and install", or "deploy for testing"

## Prerequisites

- `uv` installed (`brew install uv` or `pip install uv`)
- `poetry` installed for building packages
- **Python 3.11 available** (required for chromadb compatibility - 3.12+ fails)

## Execution Steps

### Step 0: Full Reset (before fresh plugin tests)

Use this when you need a truly clean environment (no cached wheels, no stale plugins, no lingering state).

**Use the dedicated removal script:**

```bash
# Standard removal (kills servers, uninstalls tools, clears caches, removes plugin)
.claude/skills/installing-local/remove.sh

# With PyPI dependency restoration
.claude/skills/installing-local/remove.sh --restore-pypi

# Zero-state cleanup (also removes ~/.claude/agent-brain and ./.claude/agent-brain)
.claude/skills/installing-local/remove.sh --restore-pypi --zero-state
```

Or use the `/ag-remove-local-install` command which runs this script.

<details>
<summary>Manual steps (if script unavailable)</summary>

```bash
# Stop any running servers
pkill -9 -f "agent_brain_server" 2>/dev/null || true
pkill -9 -f "uvicorn" 2>/dev/null || true
for p in $(seq 8000 8010); do kill -9 "$(lsof -i :$p -t 2>/dev/null)" 2>/dev/null || true; done

# Remove tool installs and caches
uv tool uninstall agent-brain-cli agent-brain-server 2>/dev/null || true
pipx uninstall agent-brain-cli 2>/dev/null || true
pipx uninstall agent-brain-server 2>/dev/null || true
rm -rf ~/.local/share/uv/tools/agent-brain-cli ~/.local/share/uv/tools/agent-brain-server
rm -rf ~/.cache/uv ~/.cache/pip

# Clear plugin caches/deploys
rm -rf ~/.claude/plugins/cache/agent-brain-marketplace ~/.claude/plugins/agent-brain

# Optional: wipe runtime/state for a zero-carryover test (back up first if needed)
# rm -rf ~/.claude/agent-brain ./.claude/agent-brain
```
</details>

### Local vs PyPI dependency toggle

- `./install.sh --use-path-deps` switches `agent-brain-cli` to depend on the local server via path (develop=true) and relocks. Use for rapid local dev.
- `./install.sh --restore-pypi` switches the dependency back to PyPI (`^<server_version>`) and relocks. Run before release or pushing changes.
- Default (no flags) leaves dependencies as-is and just rebuilds/installs wheels.

### Step 1: Verify Python 3.11 Available

```bash
# Check Python 3.11 is available
python3.11 --version || { echo "ERROR: Python 3.11 required but not found"; exit 1; }
```

### Step 2: Kill ALL Running Servers (Aggressive)

**CRITICAL:** Old server processes use old code. Kill everything with `-9`.

```bash
# Kill by process name (force)
pkill -9 -f "agent_brain_server" 2>/dev/null || true
pkill -9 -f "uvicorn" 2>/dev/null || true

# Kill by port range (8000-8010)
for port in $(seq 8000 8010); do
  pid=$(lsof -i :$port -t 2>/dev/null)
  if [ -n "$pid" ]; then
    echo "Killing process on port $port (PID: $pid)"
    kill -9 $pid 2>/dev/null || true
  fi
done

sleep 2

# Verify no servers running
pgrep -f "agent_brain_server" && { echo "WARNING: Servers still running!"; exit 1; } || echo "All servers stopped"
```

### Step 3: Uninstall ALL Old Versions

**CRITICAL:** Remove BOTH CLI and server tools to avoid stale code.

```bash
# Uninstall CLI from uv tool
uv tool uninstall agent-brain-cli 2>/dev/null || true

# Uninstall server from uv tool (if installed separately)
uv tool uninstall agent-brain-server 2>/dev/null || true

# Remove ALL cached tool environments
rm -rf ~/.local/share/uv/tools/agent-brain-cli 2>/dev/null || true
rm -rf ~/.local/share/uv/tools/agent-brain-server 2>/dev/null || true

# Also check for stale pipx installs
pipx uninstall agent-brain-cli 2>/dev/null || true
pipx uninstall agent-brain-server 2>/dev/null || true

echo "All old installations removed"
```

### Step 4: Clean and Build Fresh Packages

```bash
cd /Users/richardhightower/clients/spillwave/src/doc-serve

# Clean old builds
rm -rf agent-brain-server/dist agent-brain-cli/dist

# Build server package
(cd agent-brain-server && poetry build)

# Build CLI package
(cd agent-brain-cli && poetry build)
```

### Step 5: Install with uv tool

**IMPORTANT:** Install CLI with server as explicit `--with` dependency to ensure both are fresh.

```bash
cd /Users/richardhightower/clients/spillwave/src/doc-serve

# Install CLI with fresh server wheel as dependency
uv tool install ./agent-brain-cli/dist/agent_brain_cli-*.whl \
  --with ./agent-brain-server/dist/agent_brain_rag-*.whl \
  --force --python 3.11
```

### Step 6: Verify Installed Code is NEW

**CRITICAL:** Check the installed `_find_config_file` has the new search order.

```bash
# Dump the config loader source
python3.11 - <<'PY'
import inspect, textwrap
import agent_brain_server.config.provider_config as pc
src = inspect.getsource(pc._find_config_file)
print(src[:500])
PY
```

**Expected output should contain:**
- `AGENT_BRAIN_CONFIG` (not `DOC_SERVE_CONFIG`)
- `AGENT_BRAIN_STATE_DIR`
- `.claude/agent-brain/config.yaml` (not `.claude/doc-serve/`)

**If you see `DOC_SERVE_CONFIG` or `.claude/doc-serve`, the old build is still active!**

### Step 7: Path Sanity Check

```bash
# Verify agent-brain points to uv tools location
which agent-brain
# Should be: ~/.local/bin/agent-brain (symlink to uv tools)

agent-brain --version
```

### Step 8: Deploy Plugin

**⚠️ CRITICAL: MUST DELETE MARKETPLACE CACHE ⚠️**

The marketplace cache contains OLD versions with invalid flags like `--daemon`. **YOU MUST DELETE IT** or other Claude instances will use stale cached plugins.

```bash
# MANDATORY: Delete marketplace cache (contains stale --daemon references)
rm -rf ~/.claude/plugins/cache/agent-brain-marketplace
echo "✓ Marketplace cache deleted"

# Remove old plugin and copy fresh version
rm -rf ~/.claude/plugins/agent-brain
cp -r /Users/richardhightower/clients/spillwave/src/doc-serve/agent-brain-plugin ~/.claude/plugins/agent-brain

# Verify plugin version matches CLI version
echo "CLI version: $(agent-brain --version)"
echo "Plugin version: $(grep version ~/.claude/plugins/agent-brain/.claude-plugin/plugin.json 2>/dev/null || echo 'N/A')"

# Verify NO --daemon references anywhere
if grep -r "\-\-daemon" ~/.claude/plugins/agent-brain/ 2>/dev/null; then
  echo "✗ ERROR: --daemon still found in plugin!"
  exit 1
else
  echo "✓ No --daemon references in plugin"
fi
```

**After deploying:** Other Claude instances MUST be restarted to pick up the new plugin.

### Step 9: Verify CLI Auto-Discovery of Server URL

**CRITICAL:** The CLI should auto-discover the server URL from `runtime.json`, not default to 8000.

```bash
# Verify get_server_url function reads runtime.json
python3.11 - <<'PY'
import inspect
import agent_brain_cli.config as cfg
src = inspect.getsource(cfg.get_server_url)
if "runtime.json" in src:
    print("✓ CLI config reads runtime.json for URL discovery")
else:
    print("✗ ERROR: CLI does not read runtime.json!")
    exit(1)
PY
```

### Step 10: Smoke Test - Server Writes runtime.json

Start server and verify runtime.json is written with correct URL:

```bash
cd /path/to/your/project  # Must have .claude/agent-brain/config.json
agent-brain start
sleep 5

# Verify runtime.json was created
if [ ! -f .claude/agent-brain/runtime.json ]; then
  echo "✗ ERROR: runtime.json not created!"
  exit 1
fi

# Read the actual port from runtime.json
ACTUAL_PORT=$(cat .claude/agent-brain/runtime.json | grep -o '"port": [0-9]*' | cut -d' ' -f2)
ACTUAL_URL=$(cat .claude/agent-brain/runtime.json | grep -o '"base_url": "[^"]*"' | cut -d'"' -f4)
echo "✓ Server running on port: $ACTUAL_PORT"
echo "✓ Server URL: $ACTUAL_URL"

# Verify CLI picks up the correct URL (should NOT be 8000 if server started on different port)
CLI_URL=$(python3.11 -c "from agent_brain_cli.config import get_server_url; print(get_server_url())")
echo "✓ CLI discovered URL: $CLI_URL"

# Test job queue endpoint using discovered URL
curl -s "$ACTUAL_URL/index/jobs" | head -20
# Expected: JSON with jobs array, not 404

# Stop test server
agent-brain stop
```

### Step 11: Verify Foreground Mode Also Writes runtime.json

```bash
cd /path/to/your/project

# Start in foreground (background it for testing)
agent-brain start --foreground &
SERVER_PID=$!
sleep 5

# Verify runtime.json exists (NEW: foreground mode now writes it)
if [ -f .claude/agent-brain/runtime.json ]; then
  echo "✓ Foreground mode writes runtime.json"
  cat .claude/agent-brain/runtime.json | grep -E '"port"|"base_url"'
else
  echo "✗ ERROR: Foreground mode did not write runtime.json"
fi

# Clean up
kill $SERVER_PID 2>/dev/null || true
```

## Quick One-Liner

For rapid iteration (stop → uninstall → clean → build → install → verify → deploy):

```bash
cd /Users/richardhightower/clients/spillwave/src/doc-serve && \
  pkill -9 -f "agent_brain_server" 2>/dev/null; \
  pkill -9 -f "uvicorn" 2>/dev/null; \
  for p in $(seq 8000 8010); do kill -9 $(lsof -i :$p -t 2>/dev/null) 2>/dev/null; done; \
  sleep 2 && \
  uv tool uninstall agent-brain-cli 2>/dev/null; \
  uv tool uninstall agent-brain-server 2>/dev/null; \
  rm -rf ~/.local/share/uv/tools/agent-brain-cli && \
  rm -rf ~/.local/share/uv/tools/agent-brain-server && \
  rm -rf agent-brain-server/dist agent-brain-cli/dist && \
  (cd agent-brain-server && poetry build) && \
  (cd agent-brain-cli && poetry build) && \
  uv tool install ./agent-brain-cli/dist/agent_brain_cli-*.whl \
    --with ./agent-brain-server/dist/agent_brain_rag-*.whl \
    --force --python 3.11 && \
  rm -rf ~/.claude/plugins/cache/agent-brain-marketplace && \
  rm -rf ~/.claude/plugins/agent-brain && \
  cp -r agent-brain-plugin ~/.claude/plugins/agent-brain && \
  agent-brain --version && \
  echo "Local install complete! RESTART OTHER CLAUDE INSTANCES!"
```

## Post-Install: Starting in Other Projects

When using Agent Brain in another project (not doc-serve), start with `--path`:

```bash
cd /path/to/your/project
agent-brain start --path .
```

Or ensure you run from the project root so config is found via walk-up.

## Post-Install: Other Claude Instances

**IMPORTANT:** If other Claude instances were running servers before this install:
1. Those servers are using OLD code (in memory)
2. You MUST restart them: `agent-brain stop && agent-brain start`

## Config Presence Check

Before starting, ensure config exists in target project:

```bash
ls /path/to/project/.claude/agent-brain/config.yaml
```

If missing, create Ollama default:
```bash
mkdir -p /path/to/project/.claude/agent-brain
cat > /path/to/project/.claude/agent-brain/config.yaml <<'EOF'
embedding:
  provider: ollama
  model: nomic-embed-text
  base_url: http://localhost:11434/v1

summarization:
  provider: ollama
  model: llama3.2:latest
  base_url: http://localhost:11434/v1
EOF
```

## Troubleshooting

### Symptom Table

| Symptom | Cause | Fix |
|---------|-------|-----|
| `409` on `agent-brain index` | Old server still running | Kill all servers (Step 2) and restart |
| `404` on `/index/jobs` | Old server binary | Reinstall from scratch (full skill) |
| "OpenAI key missing" at startup | Config not found | Check config exists, run config search dump |
| "ANTHROPIC_API_KEY required" | Using old defaults | Config not being read; verify Step 6 |
| Jobs queue but never process | JobWorker not started | Check server logs for errors |
| CLI hits wrong port (8000) | runtime.json not found | Server didn't write runtime.json or CLI on wrong version |
| "Connection refused" on port 8000 | Server on different port, CLI defaulted | Verify runtime.json exists, check Step 9 |
| No runtime.json after start | Server failed to start or old CLI | Check server logs, reinstall CLI |
| **"No such option: --daemon"** | **Stale marketplace cache** | **DELETE `~/.claude/plugins/cache/agent-brain-marketplace/` AND restart Claude** |
| Other Claude uses wrong commands | Stale plugin cache | Delete cache, redeploy plugin, restart other Claude instances |

### Verify Config Search Order

If config isn't being found, dump the search function:

```bash
python3.11 - <<'PY'
import inspect
import agent_brain_server.config.provider_config as pc
print(inspect.getsource(pc._find_config_file))
PY
```

Should show:
1. `AGENT_BRAIN_CONFIG` env var
2. `AGENT_BRAIN_STATE_DIR` or `DOC_SERVE_STATE_DIR` (legacy)
3. CWD `config.yaml`
4. Walk up for `.claude/agent-brain/config.yaml`
5. `~/.agent-brain/config.yaml`
6. `~/.config/agent-brain/config.yaml`

### chroma-hnswlib build fails

Python 3.12+ doesn't work. Use 3.11:
```bash
uv tool install ... --python 3.11
```

### agent-brain command not found

Ensure `~/.local/bin` is in PATH:
```bash
export PATH="$HOME/.local/bin:$PATH"
```

### Old version still running after install

Force kill everything:
```bash
pkill -9 -f "agent_brain_server"
pkill -9 -f "uvicorn"
for p in $(seq 8000 8010); do kill -9 $(lsof -i :$p -t 2>/dev/null) 2>/dev/null; done
```

## Related

- `/agent-brain-start` - Start the server after install
- `/agent-brain-config` - Configure providers (Ollama, OpenAI, etc.)
