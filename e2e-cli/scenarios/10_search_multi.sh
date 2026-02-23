#!/usr/bin/env bash
# Scenario: Multi-mode fusion search
# Tests: Search with mode=multi (BM25 + Vector + Graph with RRF)

scenario_name() { echo "search-multi"; }
scenario_requires_hooks() { return 1; }
scenario_requires_server() { return 0; }

scenario_run() {
    local workspace="$1"
    assert_reset

    # Multi-mode comprehensive query
    local output
    output=$(adapter_invoke "$workspace" \
        "Run this exact shell command and show me the output: curl -s -X POST http://127.0.0.1:${SERVER_PORT}/query -H 'Content-Type: application/json' -d '{\"query\": \"search modes hybrid retrieval\", \"mode\": \"multi\", \"top_k\": 5}'" \
        90)

    assert_success "multi search returned output" test -n "$output"

    # Verify via direct call
    local results
    results=$(curl -sf -X POST "http://127.0.0.1:${SERVER_PORT}/query" \
        -H "Content-Type: application/json" \
        -d '{"query": "search modes hybrid retrieval", "mode": "multi", "top_k": 5}' 2>/dev/null || echo "{}")

    echo "$results" | assert_json "results field exists" ".results" || true

    assert_all_passed
}
