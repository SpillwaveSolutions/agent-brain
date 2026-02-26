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
        "Run this exact shell command and show me the output: curl -sL -X POST http://127.0.0.1:${SERVER_PORT}/query/ -H 'Content-Type: application/json' -d '{\"query\": \"calculator divide function\", \"mode\": \"graph\", \"top_k\": 5}'" \
        60)

    assert_success "graph search returned output" test -n "$output"

    # Verify via direct call — graph may return error if GraphRAG not enabled
    local results http_code
    http_code=$(curl -sL -o /dev/null -w "%{http_code}" -X POST "http://127.0.0.1:${SERVER_PORT}/query/" \
        -H "Content-Type: application/json" \
        -d '{"query": "calculator divide function", "mode": "graph", "top_k": 5}' 2>/dev/null || echo "000")
    results=$(curl -sL -X POST "http://127.0.0.1:${SERVER_PORT}/query/" \
        -H "Content-Type: application/json" \
        -d '{"query": "calculator divide function", "mode": "graph", "top_k": 5}' 2>/dev/null || echo "{}")

    # Graph mode returns .results if enabled, or .detail error if disabled (500)
    # Both are valid — the API should respond coherently either way
    if [[ "$http_code" == "200" ]]; then
        assert_json "response has results field" ".results" "" "$results"
    else
        assert_json "graph-disabled returns error detail" ".detail" "" "$results"
    fi

    assert_all_passed
}
