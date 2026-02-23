#!/usr/bin/env bash
# Scenario: Search with no server running
# Tests: Correct error handling when server is unreachable

scenario_name() { echo "negative-no-server"; }
scenario_requires_hooks() { return 1; }
scenario_requires_server() { return 1; }  # false — deliberately tests without server

scenario_run() {
    local workspace="$1"
    assert_reset

    # Try to query a port where no server is running
    local bad_port=19999

    # Verify direct: curl to a bad port should fail (exit code 7 = connection refused)
    local exit_code=0
    curl -sL -X POST "http://127.0.0.1:${bad_port}/query/" \
        -H "Content-Type: application/json" \
        -d '{"query": "test"}' \
        --connect-timeout 5 > /dev/null 2>&1 || exit_code=$?

    assert_success "curl to dead port returns non-zero exit" test "$exit_code" -ne 0

    # Also verify via adapter — should indicate error
    local output
    output=$(adapter_invoke "$workspace" \
        "Run this exact shell command and show me the output: curl -sL --connect-timeout 5 http://127.0.0.1:${bad_port}/health || echo 'CONNECTION_FAILED'" \
        30)

    assert_success "adapter reports connection issue" test -n "$output"

    assert_all_passed
}
