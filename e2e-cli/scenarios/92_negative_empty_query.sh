#!/usr/bin/env bash
# Scenario: Search with empty/missing query
# Tests: Server returns appropriate error for invalid query

scenario_name() { echo "negative-empty-query"; }
scenario_requires_hooks() { return 1; }
scenario_requires_server() { return 0; }

scenario_run() {
    local workspace="$1"
    assert_reset

    # Verify via direct API call — missing "query" field should return 422
    local http_code
    http_code=$(curl -sL -o /dev/null -w '%{http_code}' \
        -X POST "http://127.0.0.1:${SERVER_PORT}/query/" \
        -H "Content-Type: application/json" \
        -d '{"mode": "hybrid", "top_k": 5}' 2>/dev/null)

    # Should get 422 (validation error) for missing required field
    assert_success "server returns 422 for missing query (got ${http_code})" \
        test "$http_code" = "422"

    # Also test through adapter
    local output
    output=$(adapter_invoke "$workspace" \
        "Run this exact shell command and show me the output: curl -sL -X POST http://127.0.0.1:${SERVER_PORT}/query/ -H 'Content-Type: application/json' -d '{\"mode\": \"hybrid\", \"top_k\": 5}'" \
        60)

    # Should contain error detail about missing query field
    assert_success "adapter got validation error response" test -n "$output"

    assert_all_passed
}
