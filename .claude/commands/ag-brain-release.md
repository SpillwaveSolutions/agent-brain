---
context: fork
agent: release_agent
---

# ag-brain-release

Release automation for Agent Brain packages.

## Arguments

- `<bump>` (required): Version bump type
  - `major` - Breaking changes (1.2.0 → 2.0.0)
  - `minor` - New features (1.2.0 → 1.3.0)
  - `patch` - Bug fixes (1.2.0 → 1.2.1)

- `--dry-run` (optional): Preview changes without executing

## Examples

```bash
/ag-brain-release patch
/ag-brain-release minor
/ag-brain-release major
/ag-brain-release minor --dry-run
```

## Task

Execute a versioned release with these steps:

### Pre-Release Checks (MUST PASS)

1. Working directory is clean (`git status --porcelain` empty)
2. On `main` branch
3. Synced with remote origin/main
4. CLI dependency points to PyPI (not path) - flip if needed
5. CHANGELOG entry exists for the new version. Calculate the new version from current + bump type, then verify `docs/CHANGELOG.md` contains a `## [X.Y.Z]` heading matching it. If missing, abort with: "Add a `## [X.Y.Z] - YYYY-MM-DD` section to docs/CHANGELOG.md and commit it before re-running. See the existing [10.0.0] entry for the expected Keep-a-Changelog format."

> **Note**: `task before-push` is wrapped by an automatic lock-drift guard (`scripts/before_push_lock_guard.sh`, see issue #174). The guard snapshots clean `agent-brain-{server,cli}/poetry.lock` files at task entry and reverts any in-task churn on exit. The release flow inherits this protection — no separate manual `git checkout HEAD -- poetry.lock` step is required after `task before-push`.

### Release Steps

1. Calculate new version from current + bump type (also used by pre-release check #5)
2. Flip CLI dependency to PyPI if path-based
3. Update version in 9 files:
   - `agent-brain-server/pyproject.toml`
   - `agent-brain-server/agent_brain_server/__init__.py`
   - `agent-brain-cli/pyproject.toml`
   - `agent-brain-cli/agent_brain_cli/__init__.py`
   - `agent-brain-uds/pyproject.toml`
   - `agent-brain-uds/agent_brain_uds/__init__.py`
   - `agent-brain-mcp/pyproject.toml`
   - `agent-brain-mcp/agent_brain_mcp/__init__.py`
   - `agent-brain-plugin/.claude-plugin/plugin.json` (top-level `"version"` field — must match CLI/server)
4. Commit: `chore(release): bump version to X.Y.Z`
5. Tag: `vX.Y.Z`
6. Push branch and tag
7. Create GitHub release (triggers PyPI publish)

### Dry-Run Mode

If `--dry-run`, report what WOULD happen without executing.

## Expected Result

Report:
- Pre-check status (clean/branch/sync/dep)
- Version calculation (current → new)
- Files updated
- Git operations performed
- GitHub release URL
- PyPI package URLs (available in ~5 minutes)
