#!/bin/sh
# bootstrap_venv.sh — create a per-framework isolated venv with exact pins.
#
# Usage: bash framework-matrix/bootstrap_venv.sh <framework>
#   e.g. bash framework-matrix/bootstrap_venv.sh openai-agents
#
# The script can be invoked from any working directory; it always resolves
# paths relative to the repository root.
#
# Exit codes:
#   0 — success
#   1 — missing argument
#   2 — requirements.txt not found
#   3 — pin drift detected (second install was NOT a no-op)

set -euo pipefail

# ---------------------------------------------------------------------------
# Step 1: cd to the repository root so that all relative paths resolve
# regardless of where the script was invoked from.
# ---------------------------------------------------------------------------
if git rev-parse --show-toplevel >/dev/null 2>&1; then
    cd "$(git rev-parse --show-toplevel)"
else
    # Fallback when not inside a git work tree (e.g. bare clone or CI overlay).
    cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
fi

# ---------------------------------------------------------------------------
# Step 2: validate argument.
# ---------------------------------------------------------------------------
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <framework>" >&2
    echo "  e.g. $0 openai-agents" >&2
    exit 1
fi

FRAMEWORK="$1"
DIR="framework-matrix/$FRAMEWORK"

if [ ! -f "$DIR/requirements.txt" ]; then
    echo "ERROR: $DIR/requirements.txt not found." >&2
    echo "  Create a pinned requirements.txt for '$FRAMEWORK' first." >&2
    exit 2
fi

# ---------------------------------------------------------------------------
# Step 3: create the venv (idempotent — skips if .venv already exists).
# ---------------------------------------------------------------------------
if [ ! -d "$DIR/.venv" ]; then
    echo "Creating venv at $DIR/.venv ..."
    python3 -m venv "$DIR/.venv"
fi

# ---------------------------------------------------------------------------
# Step 4: upgrade pip (silent — we only care about the framework packages).
# ---------------------------------------------------------------------------
"$DIR/.venv/bin/pip" install --upgrade pip >/dev/null

# ---------------------------------------------------------------------------
# Step 5: install the framework requirements + local Agent Brain packages.
#
# Local packages are installed as path edits so agent-brain-serve,
# agent-brain-mcp, and agent-brain resolve on the venv PATH.
# The cd to repo root above ensures these relative paths always resolve.
# ---------------------------------------------------------------------------
echo "Installing $FRAMEWORK requirements ..."
"$DIR/.venv/bin/pip" install -r "$DIR/requirements.txt"

echo "Installing local Agent Brain packages ..."
"$DIR/.venv/bin/pip" install \
    ./agent-brain-server \
    ./agent-brain-uds \
    ./agent-brain-mcp \
    ./agent-brain-cli

# ---------------------------------------------------------------------------
# Step 6: PIN-FRESHNESS CHECK — re-run requirements install and verify it
# is a complete no-op (all pins are exact; no upgrade messages).
#
# A second install that emits "Collecting" or "Successfully installed"
# means a pinned package drifted (transitive dep pulled a newer version).
# We detect this and exit 3 so the operator knows to tighten the pins.
# ---------------------------------------------------------------------------
echo "Verifying pin freshness (second install must be a no-op) ..."
LOG="/tmp/ab_fwm_${FRAMEWORK}.log"
"$DIR/.venv/bin/pip" install -r "$DIR/requirements.txt" 2>&1 | tee "$LOG"

# Check for drift indicators.
if grep -q "^Collecting " "$LOG"; then
    # Extract the drifted package name from the first Collecting line.
    DRIFTED=$(grep "^Collecting " "$LOG" | head -1 | awk '{print $2}')
    echo "" >&2
    echo "ERROR: Pin drift detected for '$FRAMEWORK'!" >&2
    echo "  First drifted package: $DRIFTED" >&2
    echo "  A second install should be a no-op when all pins are exact." >&2
    echo "  Update $DIR/requirements.txt to pin every transitive dependency." >&2
    echo "  Full log: $LOG" >&2
    exit 3
fi

if grep -q "^Successfully installed" "$LOG"; then
    INSTALLED=$(grep "^Successfully installed" "$LOG" | head -1)
    echo "" >&2
    echo "ERROR: Pin drift detected for '$FRAMEWORK'!" >&2
    echo "  Second install unexpectedly installed packages: $INSTALLED" >&2
    echo "  A second install should produce only 'Requirement already satisfied'" >&2
    echo "  lines when all pins are exact." >&2
    echo "  Update $DIR/requirements.txt to pin every transitive dependency." >&2
    echo "  Full log: $LOG" >&2
    exit 3
fi

# Confirm that the second install was indeed a no-op.
if ! grep -q "Requirement already satisfied" "$LOG"; then
    echo "WARNING: Second install produced no output — treating as no-op." >&2
fi

echo ""
echo "bootstrapped $FRAMEWORK venv at $DIR/.venv"
