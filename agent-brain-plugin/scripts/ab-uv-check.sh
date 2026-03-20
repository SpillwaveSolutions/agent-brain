#!/usr/bin/env bash
# ab-uv-check.sh - Report uv availability and install hint when missing.

set -euo pipefail

if uv --version >/dev/null 2>&1; then
  echo "available"
  exit 0
fi

echo "missing"
echo "Install hint: curl -LsSf https://astral.sh/uv/install.sh | sh"
