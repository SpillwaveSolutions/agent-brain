#!/usr/bin/env bash
# =============================================================================
# E2E CLI Adapter — Claude Code
# =============================================================================
# Invokes Agent Brain plugin commands through `claude -p` headless mode.
#
# Interface functions:
#   adapter_name, adapter_available, adapter_version,
#   adapter_supports_hooks, adapter_invoke, adapter_setup, adapter_teardown
# =============================================================================

# ---------------------------------------------------------------------------
# Adapter Interface
# ---------------------------------------------------------------------------

adapter_name() {
    echo "claude"
}

adapter_available() {
    command -v claude &>/dev/null
}

adapter_version() {
    claude --version 2>/dev/null || echo "unknown"
}

adapter_supports_hooks() {
    # Claude Code supports hooks
    return 0  # true
}

# ---------------------------------------------------------------------------
# Setup / Teardown
# ---------------------------------------------------------------------------

# Prepare the workspace for Claude Code.
# Copies plugin to workspace and sets up the .claude directory.
adapter_setup() {
    local workspace="$1"

    # Create a project-level .claude directory so claude recognizes the workspace
    mkdir -p "$workspace/.claude"

    # Create a minimal CLAUDE.md so the agent knows about Agent Brain
    cat > "$workspace/CLAUDE.md" <<'PROJ_EOF'
# E2E Test Project

This project uses Agent Brain for document indexing and search.
Use the agent-brain CLI commands to manage it.
PROJ_EOF

    log_step "Claude adapter: workspace prepared at $workspace"
}

adapter_teardown() {
    local workspace="$1"
    # Nothing special to clean up for Claude adapter
    log_step "Claude adapter: teardown complete"
}

# ---------------------------------------------------------------------------
# Command Invocation
# ---------------------------------------------------------------------------

# Invoke an Agent Brain command through Claude Code headless mode.
#
# Usage:
#   adapter_invoke <workspace> <prompt> [timeout_seconds]
#
# Returns:
#   Prints the raw output from claude -p to stdout.
#   Exit code: 0 on success, 1 on failure/timeout.
#
# The prompt should be a natural language instruction like:
#   "Run: agent-brain status"
#   "Run: agent-brain index /path/to/docs"
#   "Run: agent-brain query 'search terms' --mode hybrid"
adapter_invoke() {
    local workspace="$1"
    local prompt="$2"
    local timeout="${3:-120}"

    local output_file
    output_file=$(mktemp "${workspace}/claude-output-XXXXXX.txt")

    # Build the claude command
    # --output-format json: structured output for parsing
    # --no-session-persistence: don't carry state between invocations
    # --allowedTools: restrict to safe tools
    local exit_code=0
    timeout "$timeout" claude -p "$prompt" \
        --output-format text \
        --no-session-persistence \
        --allowedTools "Bash,Read,Write,Edit,Glob,Grep" \
        -d "$workspace" \
        > "$output_file" 2>&1 || exit_code=$?

    if [[ $exit_code -eq 124 ]]; then
        log_step "Claude invocation timed out after ${timeout}s"
        echo "TIMEOUT: Claude invocation exceeded ${timeout}s" > "$output_file"
        cat "$output_file"
        rm -f "$output_file"
        return 1
    fi

    cat "$output_file"
    # Append to scenario log if available
    if [[ -n "${SCENARIO_LOG:-}" ]]; then
        echo "--- claude -p output ---" >> "$SCENARIO_LOG"
        cat "$output_file" >> "$SCENARIO_LOG"
        echo "--- end claude -p output ---" >> "$SCENARIO_LOG"
    fi
    rm -f "$output_file"
    return $exit_code
}

# Invoke a CLI command directly (bypasses Claude, uses agent-brain CLI).
# Used for operations where we need deterministic behavior (server start/stop).
adapter_invoke_direct() {
    local workspace="$1"
    shift
    local cmd=("$@")

    cd "$REPO_ROOT/agent-brain-cli"
    DOC_SERVE_URL="${DOC_SERVE_URL:-http://127.0.0.1:${SERVER_PORT}}" \
        poetry run "${cmd[@]}" 2>&1
    local rc=$?
    cd "$REPO_ROOT"
    return $rc
}
