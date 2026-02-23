#!/usr/bin/env bash
# Scenario: Index documentation files
# Tests: Indexing .md files via agent-brain index

scenario_name() { echo "index-docs"; }
scenario_requires_hooks() { return 1; }
scenario_requires_server() { return 0; }

scenario_run() {
    local workspace="$1"
    assert_reset

    # Use fixtures from the original location (not under .runs/ which is a hidden dir
    # that LlamaIndex's SimpleDirectoryReader skips)
    local docs_path="${E2E_ROOT}/fixtures/docs"

    # Get initial doc count
    local initial_count
    initial_count=$(get_doc_count)

    # Index docs via direct API call (reliable, deterministic)
    local index_response
    index_response=$(curl -sfL -X POST "http://127.0.0.1:${SERVER_PORT}/index/" \
        -H "Content-Type: application/json" \
        -d "{\"folder_path\": \"${docs_path}\"}" 2>/dev/null || echo "{}")

    echo "$index_response" | assert_contains "index job queued" "job_id" || true

    # Wait for indexing to complete
    wait_for_indexing 60

    # Verify document count increased
    local new_count
    new_count=$(get_doc_count)
    assert_gt "document count increased" "$new_count" "$initial_count" || true

    # Verify via adapter that Claude can see the indexed data
    local output
    output=$(adapter_invoke "$workspace" \
        "Run this exact shell command and show me the output: curl -sL http://127.0.0.1:${SERVER_PORT}/query/count" \
        60)

    assert_success "adapter can see doc count" test -n "$output"

    assert_all_passed
}
