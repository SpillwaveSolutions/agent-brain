# E2E CLI Test Harness

End-to-end testing harness for Agent Brain plugin commands through CLI adapters. Tests the full workflow from initialization to search and cleanup using headless CLI invocation.

## Quick Start

```bash
# Run all scenarios with the Claude Code adapter
task e2e-cli

# Or directly
./e2e-cli/run.sh
```

## Prerequisites

- Agent Brain server dependencies installed (`cd agent-brain-server && poetry install`)
- `claude` CLI installed and configured (for Claude adapter)
- `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` environment variables set

## Usage

```bash
# Run all scenarios
./e2e-cli/run.sh

# Run with a specific adapter
./e2e-cli/run.sh --adapter claude

# Run a single scenario
./e2e-cli/run.sh --scenario search-hybrid

# List available scenarios
./e2e-cli/run.sh --list

# Dry run (show what would execute)
./e2e-cli/run.sh --dry-run

# Keep all workspaces (even passing ones)
./e2e-cli/run.sh --keep
```

## Scenarios

| # | Scenario | Description | Server |
|---|----------|-------------|--------|
| 01 | init | Initialize Agent Brain project | No |
| 02 | start | Verify server is running | Yes |
| 03 | status | Check server status | Yes |
| 04 | index-docs | Index .md documentation files | Yes |
| 05 | index-code | Index .py/.ts code files | Yes |
| 06 | search-bm25 | BM25 keyword search | Yes |
| 07 | search-vector | Vector semantic search | Yes |
| 08 | search-hybrid | Hybrid BM25+Vector search | Yes |
| 09 | search-graph | Graph relationship search | Yes |
| 10 | search-multi | Multi-mode fusion search | Yes |
| 11 | reset | Reset index and verify empty | Yes |
| 12 | stop | Verify server before shutdown | Yes |
| 90 | negative-no-server | Search with no server | No |
| 91 | negative-bad-path | Index nonexistent path | Yes |
| 92 | negative-empty-query | Search with missing query | Yes |

## Reports

After each run, reports are generated in `.runs/<run-id>/`:

- `report.json` — Machine-readable results
- `report.md` — Markdown summary for CI artifacts
- Terminal table — Printed to stdout

## Adding an Adapter

Create a new file in `adapters/<name>.sh` that exports these functions:

```bash
adapter_name()           # Return adapter name (e.g., "opencode")
adapter_available()      # Return 0 if CLI is installed
adapter_version()        # Print CLI version
adapter_supports_hooks() # Return 0 if adapter supports hooks
adapter_invoke()         # Run a command through the CLI
adapter_setup()          # Prepare workspace for this adapter
adapter_teardown()       # Clean up adapter-specific resources
```

## Adding a Scenario

Create a new `.sh` file in `scenarios/` with a numeric prefix for ordering:

```bash
scenario_name()           # Return scenario name
scenario_requires_hooks() # Return 0 if hooks are needed
scenario_requires_server()# Return 0 if server is needed
scenario_run()            # Execute the test (return 0=pass, 1=fail)
```

Use assertion helpers from `lib/harness.sh`:
- `assert_success "label" command args...`
- `assert_failure "label" command args...`
- `echo "$data" | assert_contains "label" "substring"`
- `echo "$data" | assert_matches "label" "regex"`
- `echo "$json" | assert_json "label" ".field" "expected"`
- `assert_gt "label" "$actual" "$threshold"`

## Workspace Isolation

Each scenario runs in an isolated workspace under `.runs/<run-id>/<adapter>/<scenario>/`. On success, workspaces are cleaned up. On failure, they are preserved with full logs for debugging.

## CI Integration

The harness runs nightly via `.github/workflows/e2e-nightly.yml`:
- Schedule: 6:00 AM UTC daily
- Can be triggered manually via `workflow_dispatch`
- Artifacts uploaded on failure
- Advisory only (not a required check)

## Cost

Each full run makes real `claude -p` API calls. Estimated cost: $0.50-2.00 per run depending on scenario count and response length.
