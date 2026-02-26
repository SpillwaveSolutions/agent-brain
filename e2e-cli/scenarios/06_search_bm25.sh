#!/usr/bin/env bash
# Scenario: BM25 keyword search
# Tests: Search with mode=bm25

scenario_name() { echo "search-bm25"; }
scenario_requires_hooks() { return 1; }
scenario_requires_server() { return 0; }

scenario_run() {
    local workspace="$1"
    assert_reset

    # Search for a keyword we know is in the fixtures
    local output
    output=$(adapter_invoke "$workspace" \
        "Run this exact shell command and show me the output: curl -sL -X POST http://127.0.0.1:${SERVER_PORT}/query/ -H 'Content-Type: application/json' -d '{\"query\": \"ChromaDB vector store\", \"mode\": \"bm25\", \"top_k\": 5}'" \
        60)

    assert_success "bm25 search returned output" test -n "$output"

    # Verify results via direct API call
    local results
    results=$(curl -sfL -X POST "http://127.0.0.1:${SERVER_PORT}/query/" \
        -H "Content-Type: application/json" \
        -d '{"query": "ChromaDB vector store", "mode": "bm25", "top_k": 5}' 2>/dev/null || echo "{}")

    assert_json "response has results field" ".results" "" "$results"
    assert_json "response has total_results" ".total_results" "" "$results"

    assert_all_passed
}
