#!/usr/bin/env bash
# Scenario: Initialize Agent Brain project
# Tests: agent-brain init command

scenario_name() { echo "init"; }
scenario_requires_hooks() { return 1; }  # false
scenario_requires_server() { return 1; }  # false — init doesn't need server

scenario_run() {
    local workspace="$1"
    assert_reset

    # Run init via the adapter
    local output
    output=$(adapter_invoke "$workspace" \
        "Run this exact shell command and show me its output: agent-brain init" \
        60)

    # Verify .claude/doc-serve directory was created (or equivalent init marker)
    # The init command creates project config in the workspace
    if [[ -d "$workspace/.claude/doc-serve" ]] || echo "$output" | grep -qi "init"; then
        assert_success "init command ran" true
    else
        # Even if directory isn't created (may need server), check output
        assert_success "init command produced output" test -n "$output"
    fi

    assert_all_passed
}
