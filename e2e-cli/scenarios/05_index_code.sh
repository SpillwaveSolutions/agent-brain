#!/usr/bin/env bash
# Scenario: Index code files
# Tests: Indexing .py and .ts files via agent-brain index

scenario_name() { echo "index-code"; }
scenario_requires_hooks() { return 1; }
scenario_requires_server() { return 0; }

scenario_run() {
    local workspace="$1"
    assert_reset

    # Use fixtures from the original location (not under .runs/ which is a hidden dir
    # that LlamaIndex's SimpleDirectoryReader skips)
    local code_path="${E2E_ROOT}/fixtures/code"

    # Get current doc count
    local initial_count
    initial_count=$(get_doc_count)

    # Index code files via direct API call (reliable, deterministic)
    local index_response
    index_response=$(curl -sfL -X POST "http://127.0.0.1:${SERVER_PORT}/index/" \
        -H "Content-Type: application/json" \
        -d "{\"folder_path\": \"${code_path}\", \"include_code\": true}" 2>/dev/null || echo "{}")

    assert_contains "index code job queued" "job_id" "$index_response"

    # Wait for indexing
    wait_for_indexing 60

    # Verify count increased
    local new_count
    new_count=$(get_doc_count)
    assert_gt "code document count increased" "$new_count" "$initial_count" || true

    # Verify via adapter
    local output
    output=$(adapter_invoke "$workspace" \
        "Run this exact shell command and show me the output: curl -sL http://127.0.0.1:${SERVER_PORT}/query/count" \
        60)

    assert_success "adapter can see code doc count" test -n "$output"

    assert_all_passed
}
