#!/usr/bin/env bash
# Scenario: Reset the index
# Tests: agent-brain reset clears all indexed documents

scenario_name() { echo "reset"; }
scenario_requires_hooks() { return 1; }
scenario_requires_server() { return 0; }

scenario_run() {
    local workspace="$1"
    assert_reset

    # Reset index via API
    local output
    output=$(adapter_invoke "$workspace" \
        "Run this exact shell command and show me the output: curl -s -X DELETE http://127.0.0.1:${SERVER_PORT}/index" \
        60)

    assert_success "reset command produced output" test -n "$output"

    # Verify document count is 0
    sleep 2  # Give server a moment to process
    local count
    count=$(get_doc_count)
    assert_success "document count is zero after reset" test "$count" -eq 0

    assert_all_passed
}
