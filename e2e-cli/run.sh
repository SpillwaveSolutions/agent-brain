#!/usr/bin/env bash
# =============================================================================
# E2E CLI Test Harness — Main Entrypoint
# =============================================================================
# Discovers adapters and scenarios, manages server lifecycle, runs tests,
# and generates reports.
#
# Usage:
#   ./e2e-cli/run.sh                    # Run all scenarios with default adapter
#   ./e2e-cli/run.sh --adapter claude    # Specify adapter
#   ./e2e-cli/run.sh --scenario init     # Run single scenario
#   ./e2e-cli/run.sh --list              # List available scenarios
#   ./e2e-cli/run.sh --dry-run           # Show what would run
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Resolve paths
# ---------------------------------------------------------------------------
E2E_ROOT="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$E2E_ROOT/.." && pwd)"
export E2E_ROOT REPO_ROOT

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
ADAPTER_NAME="claude"
FILTER_SCENARIO=""
DRY_RUN=false
LIST_ONLY=false
KEEP_WORKSPACES=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --adapter|-a)    ADAPTER_NAME="$2"; shift 2 ;;
        --scenario|-s)   FILTER_SCENARIO="$2"; shift 2 ;;
        --dry-run)       DRY_RUN=true; shift ;;
        --list|-l)       LIST_ONLY=true; shift ;;
        --keep)          KEEP_WORKSPACES=true; shift ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --adapter, -a NAME    CLI adapter to use (default: claude)"
            echo "  --scenario, -s NAME   Run a single scenario by name"
            echo "  --dry-run             Show what would run without executing"
            echo "  --list, -l            List available scenarios"
            echo "  --keep                Keep all workspaces (even on success)"
            echo "  --help, -h            Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

export ADAPTER_NAME

# ---------------------------------------------------------------------------
# Source libraries
# ---------------------------------------------------------------------------
source "$E2E_ROOT/lib/harness.sh"
source "$E2E_ROOT/lib/report.sh"

# ---------------------------------------------------------------------------
# Load adapter
# ---------------------------------------------------------------------------
ADAPTER_FILE="$E2E_ROOT/adapters/${ADAPTER_NAME}.sh"
if [[ ! -f "$ADAPTER_FILE" ]]; then
    log_fail "Adapter not found: $ADAPTER_FILE"
    echo "Available adapters:"
    for f in "$E2E_ROOT/adapters/"*.sh; do
        echo "  - $(basename "$f" .sh)"
    done
    exit 1
fi
source "$ADAPTER_FILE"

# Check adapter availability
if ! adapter_available; then
    log_fail "Adapter '${ADAPTER_NAME}' is not available (CLI not installed)"
    exit 1
fi

log_info "Adapter: $(adapter_name) — $(adapter_version)"
log_info "Hooks support: $(adapter_supports_hooks && echo yes || echo no)"

# ---------------------------------------------------------------------------
# Discover scenarios
# ---------------------------------------------------------------------------
declare -a SCENARIO_FILES=()

for f in "$E2E_ROOT/scenarios/"*.sh; do
    [[ -f "$f" ]] || continue
    SCENARIO_FILES+=("$f")
done

if [[ ${#SCENARIO_FILES[@]} -eq 0 ]]; then
    log_fail "No scenarios found in $E2E_ROOT/scenarios/"
    exit 1
fi

# Sort scenarios by filename (numeric prefix ensures order)
IFS=$'\n' SCENARIO_FILES=($(sort <<<"${SCENARIO_FILES[*]}")); unset IFS

# ---------------------------------------------------------------------------
# List mode
# ---------------------------------------------------------------------------
if $LIST_ONLY; then
    echo ""
    echo "Available scenarios (adapter: ${ADAPTER_NAME}):"
    echo ""
    printf "  %-30s %-8s %-8s %s\n" "NAME" "SERVER" "HOOKS" "FILE"
    echo "  ────────────────────────────────────────────────────────"
    for f in "${SCENARIO_FILES[@]}"; do
        source "$f"
        local_name=$(scenario_name)
        local_server=$(scenario_requires_server && echo "yes" || echo "no")
        local_hooks=$(scenario_requires_hooks && echo "yes" || echo "no")
        printf "  %-30s %-8s %-8s %s\n" "$local_name" "$local_server" "$local_hooks" "$(basename "$f")"
    done
    echo ""
    exit 0
fi

# ---------------------------------------------------------------------------
# Initialize run
# ---------------------------------------------------------------------------
RUN_ID="$(date +%Y%m%d-%H%M%S)-$$"
RUNS_DIR="${E2E_ROOT}/.runs/${RUN_ID}"
mkdir -p "$RUNS_DIR"
export RUN_ID RUNS_DIR

log_info "Run ID: $RUN_ID"
log_info "Results: $RUNS_DIR"
report_init

# ---------------------------------------------------------------------------
# Dry-run mode
# ---------------------------------------------------------------------------
if $DRY_RUN; then
    echo ""
    log_info "DRY RUN — would execute:"
    for f in "${SCENARIO_FILES[@]}"; do
        source "$f"
        local_name=$(scenario_name)
        if [[ -n "$FILTER_SCENARIO" && "$local_name" != "$FILTER_SCENARIO" ]]; then
            continue
        fi
        # Check hooks requirement
        if scenario_requires_hooks && ! adapter_supports_hooks; then
            echo "  [SKIP] $local_name (requires hooks)"
        else
            echo "  [RUN]  $local_name"
        fi
    done
    echo ""
    exit 0
fi

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
log_info "Checking prerequisites ..."

# Verify required env vars
if [[ -z "${OPENAI_API_KEY:-}" ]]; then
    log_warn "OPENAI_API_KEY not set — search scenarios may fail"
fi

# ---------------------------------------------------------------------------
# Server lifecycle — start once for all scenarios that need it
# ---------------------------------------------------------------------------
NEEDS_SERVER=false
for f in "${SCENARIO_FILES[@]}"; do
    source "$f"
    local_name=$(scenario_name)
    if [[ -n "$FILTER_SCENARIO" && "$local_name" != "$FILTER_SCENARIO" ]]; then
        continue
    fi
    if scenario_requires_server; then
        NEEDS_SERVER=true
        break
    fi
done

if $NEEDS_SERVER; then
    server_start || {
        log_fail "Cannot start server — aborting"
        exit 1
    }
fi

# Ensure server is stopped on exit
trap 'server_stop; log_info "Run complete: $RUNS_DIR"' EXIT

# ---------------------------------------------------------------------------
# Run scenarios
# ---------------------------------------------------------------------------
TOTAL_SCENARIOS=0
OVERALL_EXIT=0

for scenario_file in "${SCENARIO_FILES[@]}"; do
    # Source the scenario to get its functions
    source "$scenario_file"
    local_name=$(scenario_name)

    # Filter if requested
    if [[ -n "$FILTER_SCENARIO" && "$local_name" != "$FILTER_SCENARIO" ]]; then
        continue
    fi

    # Skip if requires hooks and adapter doesn't support them
    if scenario_requires_hooks && ! adapter_supports_hooks; then
        log_warn "Skipping $local_name (requires hooks, adapter $(adapter_name) has none)"
        report_add_result "$local_name" "skip" "0" "0" "0" "requires hooks"
        continue
    fi

    # Skip if requires server and server isn't running
    if scenario_requires_server && ! server_is_running; then
        log_warn "Skipping $local_name (requires server)"
        report_add_result "$local_name" "skip" "0" "0" "0" "server not running"
        continue
    fi

    (( TOTAL_SCENARIOS++ ))
    echo ""
    log_info "━━━ Scenario: $local_name ━━━"

    # Create workspace
    workspace_create "$local_name"
    adapter_setup "$SCENARIO_WORKSPACE"

    # Run scenario with timing
    local_start=$(date +%s)
    local_status="pass"
    local_message=""

    if scenario_run "$SCENARIO_WORKSPACE"; then
        local_status="pass"
    else
        local_status="fail"
        local_message="scenario returned non-zero"
        OVERALL_EXIT=1
    fi

    local_end=$(date +%s)
    local_duration=$(( local_end - local_start ))

    # Record result
    report_add_result "$local_name" "$local_status" "$local_duration" \
        "$_ASSERT_PASSED" "$_ASSERT_TOTAL" "$local_message"

    # Workspace cleanup
    adapter_teardown "$SCENARIO_WORKSPACE"
    if [[ "$local_status" == "pass" ]] && ! $KEEP_WORKSPACES; then
        workspace_clean "$SCENARIO_WORKSPACE"
    else
        workspace_preserve "$SCENARIO_WORKSPACE"
    fi

    if [[ "$local_status" == "pass" ]]; then
        log_ok "Scenario $local_name: PASSED (${local_duration}s)"
    else
        log_fail "Scenario $local_name: FAILED (${local_duration}s)"
    fi
done

# ---------------------------------------------------------------------------
# Generate reports
# ---------------------------------------------------------------------------
echo ""
log_info "Generating reports ..."
report_all
exit $OVERALL_EXIT
