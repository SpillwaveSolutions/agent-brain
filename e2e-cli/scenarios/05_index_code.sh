#!/usr/bin/env bash
# Scenario: Index code files
# Tests: Indexing .py and .ts files via agent-brain index

scenario_name() { echo "index-code"; }
scenario_requires_hooks() { return 1; }
scenario_requires_server() { return 0; }

scenario_run() {
    local workspace="$1"
    assert_reset

    # Copy code fixtures to workspace
    fixtures_copy "$workspace" code
    local code_path="$workspace/fixtures-code"

    # Get current doc count
    local initial_count
    initial_count=$(get_doc_count)

    # Index code files via Claude
    local output
    output=$(adapter_invoke "$workspace" \
        "Run this exact shell command and show me the output: curl -s -X POST http://127.0.0.1:${SERVER_PORT}/index -H 'Content-Type: application/json' -d '{\"path\": \"${code_path}\", \"include_code\": true}'" \
        120)

    assert_success "index code command produced output" test -n "$output"

    # Wait for indexing
    wait_for_indexing 60

    # Verify count increased
    local new_count
    new_count=$(get_doc_count)
    assert_gt "code document count increased" "$new_count" "$initial_count" || true

    assert_all_passed
}
