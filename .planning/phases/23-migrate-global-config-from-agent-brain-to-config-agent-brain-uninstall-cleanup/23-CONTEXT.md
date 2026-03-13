# Phase 23: Migrate global config from ~/.agent-brain to ~/.config/agent-brain + uninstall cleanup - Context

**Gathered:** 2026-03-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Migrate the global Agent Brain directory from `~/.agent-brain` to XDG-compliant paths (`~/.config/agent-brain/`, `~/.local/state/agent-brain/`). Add an `agent-brain uninstall` CLI command for clean removal of global artifacts. Project-level state at `{project_root}/.claude/agent-brain/` is NOT affected.

</domain>

<decisions>
## Implementation Decisions

### Migration Strategy
- Auto-migrate with a one-time notice on `agent-brain start` or `agent-brain init` (not every command)
- When `~/.agent-brain` exists but XDG paths don't: copy files to new locations, then delete old directory
- Print notice to stderr: "Migrated config to ~/.config/agent-brain/"
- If migration fails (permission error, disk full): warn and continue using old path — non-blocking

### XDG Directory Layout
- Config files (config.yaml) → `$XDG_CONFIG_HOME/agent-brain/` (defaults to `~/.config/agent-brain/`)
- Runtime state (registry.json) → `$XDG_STATE_HOME/agent-brain/` (defaults to `~/.local/state/agent-brain/`)
- Shared project data path is user-configurable (not forced to any XDG location) — avoids permission issues
- Respect `XDG_CONFIG_HOME` and `XDG_STATE_HOME` env vars if set

### Config Search Order (updated)
- Flip priority: XDG path checked BEFORE legacy `~/.agent-brain/` path
- Updated order: (1) AGENT_BRAIN_CONFIG env var, (2) cwd config files, (3) project .claude/agent-brain/config.yaml, (4) `$XDG_CONFIG_HOME/agent-brain/config.yaml`, (5) `~/.agent-brain/config.yaml` (legacy fallback)
- Update both `agent_brain_cli/config.py` AND `agent_brain_server/config/provider_config.py`

### Backward Compatibility
- Keep `~/.agent-brain/` as a fallback in config search (priority #5)
- Show deprecation warning every time old path is used (via stderr/logging, not stdout)
- No hard removal deadline — graceful deprecation

### Uninstall Command
- New CLI command: `agent-brain uninstall`
- Scope: global-only cleanup — removes `~/.config/agent-brain/`, `~/.local/state/agent-brain/`, and legacy `~/.agent-brain/` if any exist
- Does NOT touch project-level `.claude/agent-brain/` directories
- Auto-stops all running Agent Brain servers (via registry) before cleanup
- Confirmation prompt by default: "Remove all Agent Brain global data? [y/N]"
- `--yes` flag to skip confirmation (for scripts/automation)

### Claude's Discretion
- Exact deprecation warning message wording
- Logging level for migration notices (info vs warning)
- Whether to create XDG directories eagerly on first run or lazily on first write
- Internal helper function structure for XDG path resolution

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `agent_brain_cli/config.py:_find_config_file()` — already searches both `~/.agent-brain/` and `~/.config/agent-brain/`, just needs priority swap
- `agent_brain_cli/config.py:load_config()` — env var override logic can stay as-is
- `agent_brain_cli/commands/stop.py` — already reads registry.json, can be reused for auto-stop during uninstall
- `agent_brain_cli/commands/reset.py` — existing cleanup pattern with confirmation prompts

### Established Patterns
- `--yes` flag for skipping confirmation: used in `agent-brain reset --yes` (same pattern for uninstall)
- `Path.home() / ".agent-brain"` hardcoded in 5+ files across CLI (stop, list, start, config commands) — all need updating
- `resolve_shared_project_dir()` in `storage_paths.py` — uses `~/.agent-brain/projects/`, needs configurable path

### Integration Points
- CLI commands affected: `start.py` (registry_dir), `stop.py` (registry_path), `list_cmd.py` (registry_path), `config.py` (home_config)
- Server config affected: `provider_config.py` (home_config search), `storage_paths.py` (shared project dir)
- Tests affected: `test_config.py`, `test_multi_instance_commands.py`, `test_storage_paths.py`

</code_context>

<specifics>
## Specific Ideas

- XDG compliance matters for Linux users who mount ~/.config separately or use dotfile managers
- Shared project data path should be configurable because some users may have permission constraints on ~/.local/share/
- Migration happens only on start/init to avoid surprise side effects during read-only commands like `status` or `query`

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 23-migrate-global-config-from-agent-brain-to-config-agent-brain-uninstall-cleanup*
*Context gathered: 2026-03-12*
