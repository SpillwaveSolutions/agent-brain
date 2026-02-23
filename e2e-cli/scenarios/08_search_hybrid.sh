#!/usr/bin/env bash
# Scenario: Hybrid search (BM25 + Vector)
# Tests: Search with mode=hybrid

scenario_name() { echo "search-hybrid"; }
scenario_requires_hooks() { return 1; }
scenario_requires_server() { return 0; }

scenario_run() {
    local workspace="$1"
    assert_reset

    # Hybrid query
    local output
    output=$(adapter_invoke "$workspace" \
        "Run this exact shell command and show me the output: curl -s -X POST http://127.0.0.1:${SERVER_PORT}/query -H 'Content-Type: application/json' -d '{\"query\": \"configuration environment variables\", \"mode\": \"hybrid\", \"top_k\": 5}'" \
        60)

    assert_success "hybrid search returned output" test -n "$output"

    # Verify via direct call
    local results
    results=$(curl -sf -X POST "http://127.0.0.1:${SERVER_PORT}/query" \
        -H "Content-Type: application/json" \
        -d '{"query": "configuration environment variables", "mode": "hybrid", "top_k": 5}' 2>/dev/null || echo "{}")

    echo "$results" | assert_json "results field exists" ".results" || true
    echo "$results" | assert_json "mode is hybrid" ".mode" "hybrid" || true

    assert_all_passed
}
