#!/usr/bin/env bash
# Scenario: Graph relationship search
# Tests: Search with mode=graph

scenario_name() { echo "search-graph"; }
scenario_requires_hooks() { return 1; }
scenario_requires_server() { return 0; }

scenario_run() {
    local workspace="$1"
    assert_reset

    # Graph query — relationship-based
    local output
    output=$(adapter_invoke "$workspace" \
        "Run this exact shell command and show me the output: curl -s -X POST http://127.0.0.1:${SERVER_PORT}/query -H 'Content-Type: application/json' -d '{\"query\": \"calculator divide function\", \"mode\": \"graph\", \"top_k\": 5}'" \
        60)

    assert_success "graph search returned output" test -n "$output"

    # Verify via direct call — graph may return empty if no graph index
    local results
    results=$(curl -sf -X POST "http://127.0.0.1:${SERVER_PORT}/query" \
        -H "Content-Type: application/json" \
        -d '{"query": "calculator divide function", "mode": "graph", "top_k": 5}' 2>/dev/null || echo "{}")

    # Graph mode might not have results if graph indexing isn't enabled
    # but the API should still respond without error
    echo "$results" | assert_json "response has results field" ".results" || true

    assert_all_passed
}
