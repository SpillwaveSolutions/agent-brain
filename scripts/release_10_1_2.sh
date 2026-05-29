#!/usr/bin/env bash
# Pre-staged v10.1.2 release script.
#
# Usage:
#   scripts/release_10_1_2.sh [<uds_pypi_name>]
#
#   <uds_pypi_name> defaults to "agent-brain-uds"; pass
#   "agent-brain-ag-uds" if PyPI rejected the canonical name as
#   "too similar" (the MCP package hit this and is being renamed to
#   "agent-brain-ag-mcp" because "agentbrain-mcp" 0.2.0 already exists).
#
# Run AFTER pending publishers are registered on PyPI for both packages
# (one-time, web UI only): https://pypi.org/manage/account/publishing/
#
# Steps:
#   1. Apply PyPI-name renames in pyproject.toml + workflow + docs
#   2. Bump 9 version files 10.1.1 → 10.1.2
#   3. Add CHANGELOG [10.1.2] entry
#   4. task before-push
#   5. Commit, tag, push
#   6. Create GitHub release (triggers publish-to-pypi workflow)
#   7. Watch the workflow
#   8. Verify all 4 packages at 10.1.2 on PyPI under their (possibly
#      renamed) project names

set -euo pipefail

cd "$(dirname "$0")/.."

UDS_PYPI_NAME="${1:-agent-brain-uds}"
MCP_PYPI_NAME="agent-brain-ag-mcp"  # locked in — PyPI rejected agent-brain-mcp

echo "=== v10.1.2 release ==="
echo "UDS PyPI name: $UDS_PYPI_NAME"
echo "MCP PyPI name: $MCP_PYPI_NAME"
echo ""

# 1a. MCP: rename the package itself.
perl -pi -e 's|^name = "agent-brain-mcp"$|name = "agent-brain-ag-mcp"|' \
    agent-brain-mcp/pyproject.toml

# 1b. CLI: rename agent-brain-uds dep IF the UDS name changed.
if [ "$UDS_PYPI_NAME" != "agent-brain-uds" ]; then
    perl -pi -e "s|agent-brain-uds = \"\\^[0-9]+\\.[0-9]+\\.[0-9]+\"|$UDS_PYPI_NAME = \"^10.1.0\"|" \
        agent-brain-cli/pyproject.toml \
        agent-brain-mcp/pyproject.toml
fi

# 1c. publish-to-pypi.yml: update both wait loops to reference the
# actual PyPI project names.
perl -pi -e "s|for pkg in agent-brain-rag agent-brain-uds; do|for pkg in agent-brain-rag $UDS_PYPI_NAME; do|g" \
    .github/workflows/publish-to-pypi.yml
# The publish-mcp job's build still works (it builds whatever
# pyproject.toml says, which is now agent-brain-ag-mcp).

# 2. Bump versions across all 9 files
perl -pi -e 's/^version = "10\.1\.1"$/version = "10.1.2"/' \
    agent-brain-server/pyproject.toml \
    agent-brain-cli/pyproject.toml \
    agent-brain-uds/pyproject.toml \
    agent-brain-mcp/pyproject.toml
perl -pi -e 's/__version__ = "10\.1\.1"/__version__ = "10.1.2"/' \
    agent-brain-server/agent_brain_server/__init__.py \
    agent-brain-cli/agent_brain_cli/__init__.py \
    agent-brain-uds/agent_brain_uds/__init__.py \
    agent-brain-mcp/agent_brain_mcp/__init__.py
perl -pi -e 's/"version": "10\.1\.1"/"version": "10.1.2"/' \
    agent-brain-plugin/.claude-plugin/plugin.json

# Also: agent-brain-uds package itself ships with its old name
# (`name = "agent-brain-uds"`); if the user picked a different PyPI
# name, rename the distribution.
if [ "$UDS_PYPI_NAME" != "agent-brain-uds" ]; then
    perl -pi -e "s|^name = \"agent-brain-uds\"\$|name = \"$UDS_PYPI_NAME\"|" \
        agent-brain-uds/pyproject.toml
fi

# 3. Add CHANGELOG [10.1.2] entry directly after [Unreleased]
perl -i -pe 'BEGIN{undef $/;} s|## \[Unreleased\]\n\n---\n\n## \[10\.1\.1\]|## [Unreleased]\n\n---\n\n## [10.1.2] - 2026-05-29\n\n### Fixed\n\n- **PyPI publish completes for all four packages after pending publishers were registered.** v10.1.0 and v10.1.1 each failed at the new-package publish step because the projects had not been pre-registered for Trusted Publisher OIDC on PyPI. `agent-brain-mcp` additionally hit PyPI'"'"'s typosquatting filter (similar to existing `agentbrain-mcp` 0.2.0) and was renamed to **`agent-brain-ag-mcp`** as its PyPI distribution name. The MCP `agent-brain-mcp` CLI command and Python import path stay unchanged — only the `pip install` string differs (`pip install agent-brain-ag-mcp` now). No functional changes vs the 10.1.1 design.\n\n---\n\n## [10.1.1]|s' docs/CHANGELOG.md

# 4. Pre-push gate
echo "=== Running task before-push ==="
task before-push

# 5. Commit + tag + push
git add -A
git commit -m "chore(release): bump version to 10.1.2 + rename agent-brain-mcp PyPI distribution

PyPI rejected the canonical \`agent-brain-mcp\` distribution name as
'too similar' to the existing \`agentbrain-mcp\` 0.2.0. The MCP
distribution is renamed to \`agent-brain-ag-mcp\` on PyPI; the CLI
command (\`agent-brain-mcp\`), Python import (\`agent_brain_mcp\`),
and code layout are all unchanged. End-users install via
\`pip install agent-brain-ag-mcp\`.

UDS distribution name: $UDS_PYPI_NAME.

No functional changes vs the 10.1.1 design. See docs/CHANGELOG.md
[10.1.2] for the user-visible install-command update."
git tag -a v10.1.2 -m "Release v10.1.2 — complete 4-package PyPI publish (with MCP rename)"
git push origin main
git push origin v10.1.2

# 6. Create GitHub release (triggers publish-to-pypi workflow)
gh release create v10.1.2 \
    --title "v10.1.2 — complete 4-package PyPI publish" \
    --notes "Re-publish of the 10.1.1 surface with **one breaking PyPI-name change**:

- \`agent-brain-mcp\` → **\`agent-brain-ag-mcp\`** (PyPI typosquat filter rejected the canonical name)
- All other distribution names, Python imports, CLI commands, and code remain unchanged.

10.1.0 and 10.1.1 each failed to publish the new packages because (a) pending publishers were not registered for the new projects, and (b) PyPI rejected \`agent-brain-mcp\` as too similar to existing \`agentbrain-mcp\`. Both issues are resolved in 10.1.2.

End-users: \`pip install agent-brain-ag-mcp\` (the CLI command \`agent-brain-mcp\` still works for stdio invocation).

See [v10.1.0](https://github.com/SpillwaveSolutions/agent-brain/releases/tag/v10.1.0) and [v10.1.1](https://github.com/SpillwaveSolutions/agent-brain/releases/tag/v10.1.1) for the full design notes."

# 7. Watch the workflow
RUN_ID=$(gh run list --workflow=publish-to-pypi.yml --limit 1 --json databaseId --jq '.[0].databaseId')
echo "Watching publish run $RUN_ID..."
gh run watch "$RUN_ID" --exit-status

# 8. Verify
echo ""
echo "=== PyPI verification ==="
for pkg in agent-brain-rag agent-brain-cli "$UDS_PYPI_NAME" "$MCP_PYPI_NAME"; do
    v=$(curl -sf "https://pypi.org/pypi/$pkg/10.1.2/json" 2>/dev/null \
        | python3 -c "import sys,json; print(json.load(sys.stdin)['info']['version'])" 2>/dev/null || echo "")
    if [ "$v" = "10.1.2" ]; then
        echo "✓ $pkg 10.1.2 LIVE on PyPI"
    else
        echo "✗ $pkg 10.1.2 NOT on PyPI"
        exit 1
    fi
done
echo ""
echo "✅ Goal achieved: all 4 packages at 10.1.2 on PyPI"
