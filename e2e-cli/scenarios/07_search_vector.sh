#!/usr/bin/env bash
# Scenario: Vector (semantic) search
# Tests: Search with mode=vector

scenario_name() { echo "search-vector"; }
scenario_requires_hooks() { return 1; }
scenario_requires_server() { return 0; }

scenario_run() {
    local workspace="$1"
    assert_reset

    # Semantic query — concept rather than exact keywords
    local output
    output=$(adapter_invoke "$workspace" \
        "Run this exact shell command and show me the output: curl -sL -X POST http://127.0.0.1:${SERVER_PORT}/query/ -H 'Content-Type: application/json' -d '{\"query\": \"how does document embedding work\", \"mode\": \"vector\", \"top_k\": 5}'" \
        60)

    assert_success "vector search returned output" test -n "$output"

    # Verify via direct call
    local results
    results=$(curl -sfL -X POST "http://127.0.0.1:${SERVER_PORT}/query/" \
        -H "Content-Type: application/json" \
        -d '{"query": "how does document embedding work", "mode": "vector", "top_k": 5}' 2>/dev/null || echo "{}")

    assert_json "response has results field" ".results" "" "$results"
    assert_json "response has query_time_ms" ".query_time_ms" "" "$results"

    assert_all_passed
}
