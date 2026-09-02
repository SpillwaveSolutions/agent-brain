#!/usr/bin/env bash
# Install a consumer package (cli or mcp) from its committed lock, then overlay
# locally-built server/uds wheels so CI tests *this commit* without a
# `poetry lock` re-resolve of torch/CUDA (see #238, #240).
#
# Usage:
#   scripts/ci_install_from_local_wheels.sh <agent-brain-cli|agent-brain-mcp>
#
# Prerequisites:
#   - poetry configured with in-project venvs
#   - agent-brain-server/dist/*.whl already built (`poetry build`)
#   - agent-brain-uds/dist/*.whl optional (overlaid when present)
#
# --no-deps on the overlay is load-bearing: the committed lock already
# resolved the heavy tree; we only want this-commit's package files.

set -euo pipefail

CONSUMER="${1:?usage: $0 <agent-brain-cli|agent-brain-mcp>}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [ ! -d "$ROOT/$CONSUMER" ]; then
    echo "ERROR: $CONSUMER is not a package directory" >&2
    exit 1
fi

shopt -s nullglob
SERVER_WHEELS=("$ROOT/agent-brain-server/dist"/*.whl)
if [ ${#SERVER_WHEELS[@]} -eq 0 ]; then
    echo "ERROR: no wheel in agent-brain-server/dist — poetry build first" >&2
    exit 1
fi
UDS_WHEELS=("$ROOT/agent-brain-uds/dist"/*.whl)

cd "$ROOT/$CONSUMER"
poetry install

OVERLAY=("${SERVER_WHEELS[@]}")
if [ ${#UDS_WHEELS[@]} -gt 0 ]; then
    OVERLAY+=("${UDS_WHEELS[@]}")
fi

echo "Overlaying local wheels (no-deps): ${OVERLAY[*]}"
poetry run pip install --force-reinstall --no-deps "${OVERLAY[@]}"
