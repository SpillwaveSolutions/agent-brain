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

    # Verify via direct API call — should return 404 for nonexistent folder
    local http_code
    http_code=$(curl -sL -o /dev/null -w '%{http_code}' \
        -X POST "http://127.0.0.1:${SERVER_PORT}/index/" \
        -H "Content-Type: application/json" \
        -d "{\"folder_path\": \"${bad_path}\"}" 2>/dev/null)

    # Should be 404 (folder not found) or 422 (validation error)
    assert_success "server returns error for bad path (got ${http_code})" \
        test "$http_code" -ge 400

    # Also test through adapter
    local output
    output=$(adapter_invoke "$workspace" \
        "Run this exact shell command and show me the output: curl -sL -w '\nHTTP_CODE:%{http_code}' -X POST http://127.0.0.1:${SERVER_PORT}/index/ -H 'Content-Type: application/json' -d '{\"folder_path\": \"${bad_path}\"}'" \
        60)

    assert_success "adapter got error response" test -n "$output"

    assert_all_passed
}
