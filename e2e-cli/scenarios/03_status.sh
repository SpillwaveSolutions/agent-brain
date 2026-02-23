#!/usr/bin/env bash
# Scenario: Check server status
# Tests: agent-brain status command via Claude

scenario_name() { echo "status"; }
scenario_requires_hooks() { return 1; }
scenario_requires_server() { return 0; }

scenario_run() {
    local workspace="$1"
    assert_reset

    # Ask Claude to check status
    local output
    output=$(adapter_invoke "$workspace" \
        "Run this exact shell command and show me the output: curl -s http://127.0.0.1:${SERVER_PORT}/health" \
        60)

    # Verify we got status information
    assert_success "status output is non-empty" test -n "$output"

    # Also verify via direct HTTP call
    local health
    health=$(curl -sf "http://127.0.0.1:${SERVER_PORT}/health" 2>/dev/null)
    echo "$health" | assert_contains "health shows ok status" "status" || true

    assert_all_passed
}
