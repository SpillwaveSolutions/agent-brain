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
        "Run this exact shell command and show me the output: curl -sL -X POST http://127.0.0.1:${SERVER_PORT}/query/ -H 'Content-Type: application/json' -d '{\"query\": \"configuration environment variables\", \"mode\": \"hybrid\", \"top_k\": 5}'" \
        60)

    assert_success "hybrid search returned output" test -n "$output"

    # Verify via direct call
    local results
    results=$(curl -sfL -X POST "http://127.0.0.1:${SERVER_PORT}/query/" \
        -H "Content-Type: application/json" \
        -d '{"query": "configuration environment variables", "mode": "hybrid", "top_k": 5}' 2>/dev/null || echo "{}")

    echo "$results" | assert_json "response has results field" ".results" || true
    echo "$results" | assert_json "response has total_results" ".total_results" || true

    assert_all_passed
}
