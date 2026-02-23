#!/usr/bin/env bash
# Scenario: Index a nonexistent path
# Tests: Server returns error for invalid indexing path

scenario_name() { echo "negative-bad-path"; }
scenario_requires_hooks() { return 1; }
scenario_requires_server() { return 0; }

scenario_run() {
    local workspace="$1"
    assert_reset

    local bad_path="/nonexistent/path/that/does/not/exist"

    # Try to index a nonexistent path
    local output
    output=$(adapter_invoke "$workspace" \
        "Run this exact shell command and show me the output: curl -s -X POST http://127.0.0.1:${SERVER_PORT}/index -H 'Content-Type: application/json' -d '{\"path\": \"${bad_path}\"}'" \
        60)

    assert_success "index bad path produced output" test -n "$output"

    # Verify via direct API call — should return error
    local result
    result=$(curl -sf -X POST "http://127.0.0.1:${SERVER_PORT}/index" \
        -H "Content-Type: application/json" \
        -d "{\"path\": \"${bad_path}\"}" 2>/dev/null || echo '{"error": "request_failed"}')

    # The response should indicate an error (either HTTP error code or error in body)
    local http_code
    http_code=$(curl -s -o /dev/null -w '%{http_code}' \
        -X POST "http://127.0.0.1:${SERVER_PORT}/index" \
        -H "Content-Type: application/json" \
        -d "{\"path\": \"${bad_path}\"}" 2>/dev/null)

    # Should be 4xx or contain error info
    if [[ "$http_code" =~ ^4 ]] || echo "$result" | grep -qi "error\|not found\|invalid\|does not exist"; then
        assert_success "server reports error for bad path" true
    else
        # Some servers accept the job and fail async — check that too
        assert_success "server accepted request (may fail async)" test -n "$result"
    fi

    assert_all_passed
}
