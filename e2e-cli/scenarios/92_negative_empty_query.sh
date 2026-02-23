#!/usr/bin/env bash
# Scenario: Search with empty/missing query
# Tests: Server returns appropriate error for invalid query

scenario_name() { echo "negative-empty-query"; }
scenario_requires_hooks() { return 1; }
scenario_requires_server() { return 0; }

scenario_run() {
    local workspace="$1"
    assert_reset

    # Try to search with an empty query
    local output
    output=$(adapter_invoke "$workspace" \
        "Run this exact shell command and show me the output: curl -s -w '\n%{http_code}' -X POST http://127.0.0.1:${SERVER_PORT}/query -H 'Content-Type: application/json' -d '{\"mode\": \"hybrid\", \"top_k\": 5}'" \
        60)

    assert_success "empty query produced output" test -n "$output"

    # Verify via direct API call — missing "query" field
    local http_code
    http_code=$(curl -s -o /dev/null -w '%{http_code}' \
        -X POST "http://127.0.0.1:${SERVER_PORT}/query" \
        -H "Content-Type: application/json" \
        -d '{"mode": "hybrid", "top_k": 5}' 2>/dev/null)

    # Should get 422 (validation error) for missing required field
    assert_success "server returns client error for missing query" \
        test "$http_code" = "422"

    assert_all_passed
}
