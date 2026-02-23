#!/usr/bin/env bash
# Scenario: Index documentation files
# Tests: Indexing .md files via agent-brain index

scenario_name() { echo "index-docs"; }
scenario_requires_hooks() { return 1; }
scenario_requires_server() { return 0; }

scenario_run() {
    local workspace="$1"
    assert_reset

    # Copy doc fixtures to workspace
    fixtures_copy "$workspace" docs
    local docs_path="$workspace/fixtures-docs"

    # Get initial doc count
    local initial_count
    initial_count=$(get_doc_count)

    # Index docs via Claude
    local output
    output=$(adapter_invoke "$workspace" \
        "Run this exact shell command and show me the output: curl -s -X POST http://127.0.0.1:${SERVER_PORT}/index -H 'Content-Type: application/json' -d '{\"path\": \"${docs_path}\"}'" \
        120)

    assert_success "index command produced output" test -n "$output"

    # Wait for indexing to complete
    wait_for_indexing 60

    # Verify document count increased
    local new_count
    new_count=$(get_doc_count)
    assert_gt "document count increased" "$new_count" "$initial_count" || true

    assert_all_passed
}
