# Plan: E2E Integration Test Suite (Claude CLI Driver)

## 1. Objective
Create a robust, automated integration test suite that verifies the entire `agent-brain` lifecycle (Install → Init → Start → Index → Search) by driving the system using the `claude` CLI. This ensures that the plugin, CLI, and server components interact correctly in a realistic, isolated environment.

## 2. Architecture & Strategy
We will use a **Bash-based test runner** (`e2e/bin/run_integration.sh`) that acts as the orchestrator. It will:
1.  **Isolate**: Create a temporary sandbox in `e2e/tmp/` (git-ignored) with its own `$HOME` to prevent polluting the developer's user configuration.
2.  **Inject**: Load the `agent-brain-plugin` dynamically using the `claude --plugin-dir` flag.
3.  **Drive**: Issue natural language commands to the `claude` CLI to perform tasks, simulating a real user.
4.  **Verify**: Check exit codes, file existence, server health endpoints (`/health`), and search output content.

### Directory Structure
```text
e2e/
├── bin/
│   └── run_integration.sh      # The main executable test runner
├── fixtures/
│   ├── src/                    # Dummy Python code for indexing tests
│   └── docs/                   # Dummy Markdown docs for indexing tests
└── tmp/                        # Runtime sandbox (created/deleted by script)
    ├── home/                   # Fake user home (isolates .claude/config)
    ├── work/                   # Working directory for the agent
    └── logs/                   # Server and test logs
```

## 3. Test Flow Steps

### Step 1: Environment Setup
*   Clean `e2e/tmp`.
*   Create `e2e/tmp/home` and `e2e/tmp/work`.
*   Set `export HOME=.../e2e/tmp/home` to isolate the Claude CLI config.
*   Copy `e2e/fixtures/src` and `e2e/fixtures/docs` into the work directory.

### Step 2: Initialization
*   **Command**: `claude -p "Initialize the agent brain here."`
*   **Verification**: Check that `.agent-brain/config.yaml` is created.

### Step 3: Server Start
*   **Command**: `claude -p "Start the agent brain server in the background."`
*   **Mechanism**: The agent uses the `agent_brain_start` tool.
*   **Verification**: Poll `http://localhost:8000/health` until it returns 200 OK.

### Step 4: Indexing
*   **Command A**: `claude -p "Index the ./src folder."`
*   **Command B**: `claude -p "Index the ./docs folder."`
*   **Verification**: Check `agent-brain status` (via CLI or API) to ensure documents are processed.

### Step 5: Search & Validation
*   **Command**: `claude -p "Search for 'coffee' and 'ConfigLoader' and show me the results."`
*   **Verification**: Capture the standard output and use `grep` to verify it contains expected keywords from both the code and documentation fixtures.

### Step 6: Teardown
*   Send a stop signal to the server (pkill or `agent-brain stop`).
*   Report success/failure.

## 4. Implementation Details

### The Test Runner Script (`e2e/bin/run_integration.sh`)
This script will act as the "CI" entry point.

```bash
#!/bin/bash
set -e

# Configuration
BASE_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
E2E_DIR="$BASE_DIR/e2e"
TMP_DIR="$E2E_DIR/tmp"
PLUGIN_DIR="$BASE_DIR/agent-brain-plugin"

# Export fake HOME for isolation
export HOME="$TMP_DIR/home"
mkdir -p "$HOME" "$TMP_DIR/work"

# Copy fixtures
cp -r "$E2E_DIR/fixtures/src" "$TMP_DIR/work/"
cp -r "$E2E_DIR/fixtures/docs" "$TMP_DIR/work/"
cd "$TMP_DIR/work"

echo "=== 1. Initialize ==="
claude --plugin-dir "$PLUGIN_DIR" 
       --allowedTools "agent_brain_init" 
       -p "Initialize the agent brain."

echo "=== 2. Start Server ==="
claude --plugin-dir "$PLUGIN_DIR" 
       --allowedTools "Bash,agent_brain_start" 
       -p "Start the agent brain server in the background."

# Wait for health
echo "Waiting for server..."
until curl -s http://localhost:8000/health | grep "ok"; do sleep 1; done

echo "=== 3. Indexing ==="
claude --plugin-dir "$PLUGIN_DIR" --allowedTools "agent_brain_index" -p "Index ./src"
claude --plugin-dir "$PLUGIN_DIR" --allowedTools "agent_brain_index" -p "Index ./docs"

echo "=== 4. Search ==="
RESULT=$(claude --plugin-dir "$PLUGIN_DIR" --allowedTools "agent_brain_search" 
         -p "Search for 'ConfigLoader' and 'coffee'.")

echo "$RESULT"
if echo "$RESULT" | grep -q "ConfigLoader"; then
    echo "SUCCESS"
else
    echo "FAILURE"
    exit 1
fi
```
