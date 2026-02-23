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
    local output
    output=$(adapter_invoke "$workspace" \
        "Run this exact shell command and show me the output: curl -s -o /dev/null -w '%{http_code}' -X POST http://127.0.0.1:${bad_port}/query -H 'Content-Type: application/json' -d '{\"query\": \"test\", \"mode\": \"hybrid\"}' --connect-timeout 5 || echo 'CONNECTION_REFUSED'" \
        30)

    # Should show connection refused or error
    assert_success "got output from failed connection attempt" test -n "$output"

    # Verify direct: curl to a bad port should fail
    local http_code
    http_code=$(curl -s -o /dev/null -w '%{http_code}' \
        -X POST "http://127.0.0.1:${bad_port}/query" \
        -H "Content-Type: application/json" \
        -d '{"query": "test"}' \
        --connect-timeout 5 2>/dev/null || echo "000")

    assert_success "connection refused returns error code" test "$http_code" = "000"

    assert_all_passed
}
