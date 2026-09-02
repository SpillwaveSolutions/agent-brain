#!/usr/bin/env bash
# Fail if a published package's *runtime* dependencies include a path pin.
# Dev-group path deps are allowed (monorepo test wiring). See #238.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python3 - <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path

PACKAGES = (
    "agent-brain-server",
    "agent-brain-cli",
    "agent-brain-mcp",
    "agent-brain-uds",
)

failed = False
for pkg in PACKAGES:
    path = Path(pkg) / "pyproject.toml"
    if not path.is_file():
        continue
    text = path.read_text()
    match = re.search(
        r"\[tool\.poetry\.dependencies\](.*?)(?:\n\[|\Z)",
        text,
        re.S,
    )
    if match is None:
        continue
    block = match.group(1)
    if re.search(r"path\s*=", block):
        print(
            f"ERROR: runtime path dependency in {path} — "
            "publishing this would ship an unresolvable wheel (#238).",
            file=sys.stderr,
        )
        failed = True

if failed:
    sys.exit(1)
print("OK: no runtime path dependencies in published packages.")
PY
