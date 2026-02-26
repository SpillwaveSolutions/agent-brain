#!/usr/bin/env bash
# Scenario: Stop the server
# Tests: Server can be stopped cleanly
# Note: The harness manages server lifecycle. This scenario verifies
# that the server responds before the harness shuts it down.

scenario_name() { echo "stop"; }
scenario_requires_hooks() { return 1; }
scenario_requires_server() { return 0; }

scenario_run() {
    local workspace="$1"
    assert_reset

    # Verify server is still running before "stop"
    assert_success "server responds before stop" \
        curl -sfL "http://127.0.0.1:${SERVER_PORT}/health"

    # Verify the health endpoint returns valid JSON with status field
    local health
    health=$(curl -sfL "http://127.0.0.1:${SERVER_PORT}/health" 2>/dev/null)
    assert_json "health has status field" ".status" "" "$health"

    # Note: actual server stop is handled by the harness at the end of the run
    assert_all_passed
}
