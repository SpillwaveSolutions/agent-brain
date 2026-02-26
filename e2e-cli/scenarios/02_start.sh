#!/usr/bin/env bash
# Scenario: Start Agent Brain server
# Tests: Server is running and accessible after start
# Note: The harness manages the server lifecycle directly — this scenario
# verifies the server is reachable and healthy.

scenario_name() { echo "start"; }
scenario_requires_hooks() { return 1; }
scenario_requires_server() { return 0; }  # true — needs server running

scenario_run() {
    local workspace="$1"
    assert_reset

    # Server should already be running (started by harness)
    # Verify health endpoint responds
    local health
    health=$(curl -sfL "http://127.0.0.1:${SERVER_PORT}/health" 2>/dev/null || echo "")

    assert_contains "health endpoint responds" "status" "$health"
    assert_success "server port is open" curl -sfL "http://127.0.0.1:${SERVER_PORT}/health"

    assert_all_passed
}
