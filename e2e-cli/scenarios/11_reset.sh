#!/usr/bin/env bash
# Scenario: Reset the index
# Tests: agent-brain reset clears all indexed documents

scenario_name() { echo "reset"; }
scenario_requires_hooks() { return 1; }
scenario_requires_server() { return 0; }

scenario_run() {
    local workspace="$1"
    assert_reset

    # Reset index via direct API call
    local http_code
    http_code=$(curl -sL -o /dev/null -w '%{http_code}' \
        -X DELETE "http://127.0.0.1:${SERVER_PORT}/index/" 2>/dev/null)

    assert_success "reset returns success (got ${http_code})" test "$http_code" = "200"

    # Wait for reset to take effect — the server reinitializes storage
    sleep 5

    # Verify document count is 0
    local count
    count=$(get_doc_count)
    assert_success "document count is zero after reset (got ${count})" test "$count" -eq 0

    assert_all_passed
}
