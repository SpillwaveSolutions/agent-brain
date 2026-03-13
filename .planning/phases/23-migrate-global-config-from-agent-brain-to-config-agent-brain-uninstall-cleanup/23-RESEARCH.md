# Phase 23: Migrate Global Config from ~/.agent-brain to ~/.config/agent-brain + Uninstall Cleanup - Research

**Researched:** 2026-03-12
**Domain:** XDG Base Directory compliance, Python Path manipulation, Click CLI, shutil file operations
**Confidence:** HIGH

## Summary

Phase 23 migrates the global Agent Brain directory from `~/.agent-brain` to XDG-compliant paths (`~/.config/agent-brain/` for config, `~/.local/state/agent-brain/` for state/registry), adds one-time auto-migration on `agent-brain start` and `agent-brain init`, adds deprecation warnings when the legacy path is still used, and introduces a new `agent-brain uninstall` command for global cleanup.

The scope is deliberately narrow: only global state is affected. Project-level `.claude/agent-brain/` directories are completely untouched. The code changes are concentrated in four CLI source files (`start.py`, `stop.py`, `list_cmd.py`, `config.py`) plus the new `uninstall.py` command. The server's `storage_paths.py` also needs updating for its `resolve_shared_project_dir()` helper.

The existing codebase already has all patterns needed for implementation. The `_find_config_file()` functions in both the CLI and server `provider_config.py` already include XDG paths — they just need priority reordering and a deprecation notice on the legacy fallback. The `reset.py` command provides a direct template for the `--yes` confirmation pattern used by `uninstall`. All global registry operations in `start.py`, `stop.py`, and `list_cmd.py` currently hardcode `Path.home() / ".agent-brain"` — these need to call a shared helper instead.

**Primary recommendation:** Extract XDG path resolution into a single shared helper module (`agent_brain_cli/xdg_paths.py`), update all callers to use it, add migration logic in `start.py` and `init.py`, then add `uninstall.py` as a new command.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Migration Strategy
- Auto-migrate with a one-time notice on `agent-brain start` or `agent-brain init` (not every command)
- When `~/.agent-brain` exists but XDG paths don't: copy files to new locations, then delete old directory
- Print notice to stderr: "Migrated config to ~/.config/agent-brain/"
- If migration fails (permission error, disk full): warn and continue using old path — non-blocking

#### XDG Directory Layout
- Config files (config.yaml) → `$XDG_CONFIG_HOME/agent-brain/` (defaults to `~/.config/agent-brain/`)
- Runtime state (registry.json) → `$XDG_STATE_HOME/agent-brain/` (defaults to `~/.local/state/agent-brain/`)
- Shared project data path is user-configurable (not forced to any XDG location) — avoids permission issues
- Respect `XDG_CONFIG_HOME` and `XDG_STATE_HOME` env vars if set

#### Config Search Order (updated)
- Flip priority: XDG path checked BEFORE legacy `~/.agent-brain/` path
- Updated order: (1) AGENT_BRAIN_CONFIG env var, (2) cwd config files, (3) project .claude/agent-brain/config.yaml, (4) `$XDG_CONFIG_HOME/agent-brain/config.yaml`, (5) `~/.agent-brain/config.yaml` (legacy fallback)
- Update both `agent_brain_cli/config.py` AND `agent_brain_server/config/provider_config.py`

#### Backward Compatibility
- Keep `~/.agent-brain/` as a fallback in config search (priority #5)
- Show deprecation warning every time old path is used (via stderr/logging, not stdout)
- No hard removal deadline — graceful deprecation

#### Uninstall Command
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

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| XDG-01 | Config files → `$XDG_CONFIG_HOME/agent-brain/` (default `~/.config/agent-brain/`) | `_get_xdg_config_dir()` helper reads env var with fallback |
| XDG-02 | State/registry → `$XDG_STATE_HOME/agent-brain/` (default `~/.local/state/agent-brain/`) | `_get_xdg_state_dir()` helper reads env var with fallback |
| XDG-03 | Respect `XDG_CONFIG_HOME` and `XDG_STATE_HOME` env vars | Standard XDG spec, `os.environ.get()` |
| MIG-01 | Auto-migrate `~/.agent-brain` → XDG paths on `start` or `init` | `shutil.copytree()` / per-file copy, then rmtree |
| MIG-02 | Migration notice to stderr (non-blocking on failure) | `sys.stderr.write()` or `click.echo(err=True)` |
| MIG-03 | Deprecation warning when legacy path is still used as fallback | Warning in `_find_config_file()` fallback branch |
| CFG-01 | Flip config search priority: XDG before legacy in CLI `config.py` | Swap steps 4 and 5 in `_find_config_file()` |
| CFG-02 | Flip config search priority: XDG before legacy in server `provider_config.py` | Swap steps 5 and 6 in server `_find_config_file()` |
| REG-01 | Registry operations in `start.py` use XDG state dir | Replace `Path.home() / ".agent-brain"` with helper |
| REG-02 | Registry operations in `stop.py` use XDG state dir | Replace hardcoded path with helper |
| REG-03 | Registry operations in `list_cmd.py` use XDG state dir | Replace hardcoded path with helper |
| REG-04 | `storage_paths.resolve_shared_project_dir()` uses configurable base, not `~/.agent-brain` | Add `base_dir` parameter or read env var |
| UNI-01 | `agent-brain uninstall` command — removes global dirs, stops servers first | New `uninstall.py` patterned after `reset.py` |
| UNI-02 | Uninstall confirmation prompt "Remove all Agent Brain global data? [y/N]" | `click.confirm()` with default=False |
| UNI-03 | `--yes` flag to skip confirmation | Same pattern as `agent-brain reset --yes` |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pathlib.Path | stdlib | Path manipulation for XDG dirs | Already used throughout codebase |
| os.environ | stdlib | Read XDG env vars | Standard approach for XDG spec compliance |
| shutil | stdlib | Copy directory tree during migration | `shutil.copytree()` handles recursive copy |
| click | ^8.0 | New `uninstall` command + confirmation | Already the CLI framework |
| rich.prompt.Confirm | existing | User confirmation UI | Already used in reset.py pattern |

### No New Dependencies Required
All required functionality is available in the Python standard library and existing project dependencies. This phase introduces no new packages.

**Installation:**
```bash
# No new packages needed
```

## Architecture Patterns

### Recommended Project Structure (changes only)

```
agent-brain-cli/
├── agent_brain_cli/
│   ├── xdg_paths.py         # NEW: shared XDG path helpers + migration logic
│   ├── config.py            # MODIFY: flip search order steps 4/5, add deprecation warn
│   └── commands/
│       ├── start.py         # MODIFY: call migrate_legacy_paths(), use xdg_state_dir()
│       ├── stop.py          # MODIFY: use xdg_state_dir() for registry
│       ├── list_cmd.py      # MODIFY: use xdg_state_dir() for registry
│       ├── config.py        # MODIFY: flip search order steps 5/6, add deprecation warn
│       └── uninstall.py     # NEW: global cleanup command
agent-brain-server/
└── agent_brain_server/
    ├── config/
    │   └── provider_config.py  # MODIFY: flip search order steps 5/6, add deprecation warn
    └── storage_paths.py        # MODIFY: resolve_shared_project_dir() reads AGENT_BRAIN_SHARED_DIR env or uses xdg_data_dir
```

### Pattern 1: XDG Path Helper Module (`xdg_paths.py`)

**What:** Single source of truth for all XDG directory resolution and migration logic.
**When to use:** Any code that needs to find the global registry or config directory.

```python
# agent_brain_cli/xdg_paths.py
import logging
import os
import shutil
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

LEGACY_DIR = Path.home() / ".agent-brain"


def get_xdg_config_dir() -> Path:
    """Return $XDG_CONFIG_HOME/agent-brain (default ~/.config/agent-brain)."""
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config_home:
        return Path(xdg_config_home) / "agent-brain"
    return Path.home() / ".config" / "agent-brain"


def get_xdg_state_dir() -> Path:
    """Return $XDG_STATE_HOME/agent-brain (default ~/.local/state/agent-brain)."""
    xdg_state_home = os.environ.get("XDG_STATE_HOME")
    if xdg_state_home:
        return Path(xdg_state_home) / "agent-brain"
    return Path.home() / ".local" / "state" / "agent-brain"


def get_registry_path() -> Path:
    """Return the active registry.json path (XDG state dir)."""
    return get_xdg_state_dir() / "registry.json"


def migrate_legacy_paths(*, silent: bool = False) -> bool:
    """Migrate ~/.agent-brain to XDG directories if needed.

    Called once on 'agent-brain start' and 'agent-brain init'.
    Non-blocking: warns on failure and returns False.

    Returns:
        True if migration was performed, False otherwise.
    """
    if not LEGACY_DIR.exists():
        return False

    config_dir = get_xdg_config_dir()
    state_dir = get_xdg_state_dir()

    # Only migrate if XDG dirs don't exist yet
    if config_dir.exists() or state_dir.exists():
        return False

    try:
        config_dir.mkdir(parents=True, exist_ok=True)
        state_dir.mkdir(parents=True, exist_ok=True)

        # Copy config files (config.yaml) to config dir
        for name in ("config.yaml", "agent-brain.yaml"):
            src = LEGACY_DIR / name
            if src.exists():
                shutil.copy2(src, config_dir / name)

        # Copy state files (registry.json) to state dir
        for name in ("registry.json",):
            src = LEGACY_DIR / name
            if src.exists():
                shutil.copy2(src, state_dir / name)

        # Remove legacy directory
        shutil.rmtree(LEGACY_DIR, ignore_errors=True)

        if not silent:
            click.echo(
                f"Migrated config to {config_dir}",
                err=True,
            )
        return True

    except (PermissionError, OSError) as e:
        logger.warning("Migration failed, using legacy path: %s", e)
        if not silent:
            click.echo(
                f"Warning: Could not migrate ~/.agent-brain to XDG paths: {e}",
                err=True,
            )
        return False
```

### Pattern 2: Config Search Priority Flip

**What:** In both `_find_config_file()` implementations (CLI `config.py` and server `provider_config.py`), swap the order so XDG path is checked before the legacy path.
**When to use:** Everywhere `_find_config_file()` is defined.

Current order (wrong):
```
4. ~/.agent-brain/config.yaml       # legacy
5. ~/.config/agent-brain/config.yaml  # XDG
```

Correct order after fix:
```
4. $XDG_CONFIG_HOME/agent-brain/config.yaml  # XDG (preferred)
5. ~/.agent-brain/config.yaml                 # legacy (fallback + deprecation warn)
```

Deprecation warning in step 5 (legacy fallback):
```python
# Step 5 — legacy fallback
home_config = Path.home() / ".agent-brain" / "config.yaml"
if home_config.exists():
    import sys
    print(
        "Warning: Using legacy config path ~/.agent-brain/config.yaml. "
        "Migrate to ~/.config/agent-brain/config.yaml.",
        file=sys.stderr,
    )
    return home_config
```

### Pattern 3: Registry Path Usage in start/stop/list

**What:** Replace the hardcoded `Path.home() / ".agent-brain"` in all registry operations with the shared `get_xdg_state_dir()` helper.
**When to use:** `update_registry()` in start.py, `remove_from_registry()` in stop.py, `get_registry()` / `save_registry()` in list_cmd.py.

```python
# Before (in start.py update_registry, stop.py remove_from_registry, list_cmd.py):
registry_dir = Path.home() / ".agent-brain"

# After:
from agent_brain_cli.xdg_paths import get_xdg_state_dir
registry_dir = get_xdg_state_dir()
```

Note: `get_xdg_state_dir()` also must return the legacy dir as fallback if the legacy dir exists and XDG dir does not (pre-migration). However, since migration runs on `start` and `init`, by the time `stop` or `list` runs, migration will have already occurred. A safe approach: read from whichever dir actually contains `registry.json`, preferring XDG.

```python
def get_registry_path() -> Path:
    """Return registry.json path, preferring XDG over legacy."""
    xdg_path = get_xdg_state_dir() / "registry.json"
    if xdg_path.exists():
        return xdg_path
    legacy_path = Path.home() / ".agent-brain" / "registry.json"
    if legacy_path.exists():
        return legacy_path  # Will be migrated next time start/init runs
    return xdg_path  # Default write target
```

### Pattern 4: Uninstall Command (`uninstall.py`)

**What:** New Click command modeled directly on `reset.py`. Stops all servers via registry, then removes global dirs.
**When to use:** When user wants to completely remove Agent Brain global artifacts.

```python
@click.command("uninstall")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def uninstall_command(yes: bool, json_output: bool) -> None:
    """Remove all Agent Brain global data and configuration.

    Stops all running servers, then removes:
      - ~/.config/agent-brain/  (XDG config)
      - ~/.local/state/agent-brain/  (XDG state + registry)
      - ~/.agent-brain/  (legacy, if present)

    Project-level .claude/agent-brain/ directories are NOT removed.
    """
    # 1. Show what will be removed
    # 2. Confirm (unless --yes)
    # 3. Stop running servers via registry
    # 4. Remove directories
    # 5. Report results
```

Key implementation details:
- Scan registry for running servers before deleting anything
- Stop each running server via SIGTERM (reuse stop_command logic)
- Use `shutil.rmtree()` for directory removal
- Handle missing directories gracefully (idempotent)
- `--yes` skips `click.confirm()` — identical to `reset.py` pattern

### Anti-Patterns to Avoid
- **Importing `xdg_paths` at module level in commands:** Commands share a process, but `Path.home()` is fixed at import time. Use function calls, not module-level constants, so tests can patch.
- **Using `shutil.rmtree` without error handling in uninstall:** If a running server holds a file lock, rmtree will raise. Wrap in try/except and report partial failures.
- **Creating XDG dirs eagerly in the helper:** Create dirs lazily (only when writing) to avoid creating empty dirs that confuse migration detection.
- **Forgetting the `lru_cache` on `load_provider_settings()` in server:** The server's `_find_config_file()` result is cached via `@lru_cache` on `load_provider_settings()`. The path flip only matters at first load — this is correct behavior, no change needed.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Directory copy during migration | Custom recursive walker | `shutil.copytree()` or `shutil.copy2()` per file | Handles symlinks, permissions, edge cases |
| Directory removal during uninstall | Custom recursive delete | `shutil.rmtree(path, ignore_errors=True)` | Handles non-empty dirs, partial failures |
| Confirmation prompt | Custom `input()` loop | `click.confirm()` / `rich.prompt.Confirm.ask()` | Consistent with rest of CLI; handles Ctrl+C |
| XDG spec parsing | Full XDG library | `os.environ.get("XDG_CONFIG_HOME")` inline | Phase only needs two env vars; full XDG lib is overkill |

## Common Pitfalls

### Pitfall 1: Migration Runs Before Registry Write
**What goes wrong:** `migrate_legacy_paths()` is called in `start.py`, but the registry write (`update_registry()`) happens later in the same command. If migration runs first and deletes `~/.agent-brain/registry.json`, then `update_registry()` still looks in the old path, it will recreate the legacy directory.
**Why it happens:** Migration deletes `~/.agent-brain/` but `update_registry()` still uses the hardcoded legacy path.
**How to avoid:** Update `update_registry()` to use `get_xdg_state_dir()` in the same change. Migration must be paired with registry path update.
**Warning signs:** `~/.agent-brain/` directory reappears after migration.

### Pitfall 2: `shutil.rmtree` on Legacy Dir with Active Files
**What goes wrong:** User has a running server whose log files or PID file live inside `~/.agent-brain/`. Migration deletes that dir, crashing the server.
**Why it happens:** Migration check only looks at XDG dirs, not whether legacy dir has active processes.
**How to avoid:** Migration only runs on `start` and `init` — both of which require no server running for the target project. The global `~/.agent-brain/registry.json` doesn't belong to any running server's data. Log files live in `.claude/agent-brain/logs/`, not the global dir.
**Warning signs:** Check that `~/.agent-brain/` only contains `registry.json` and `config.yaml` — not server runtime files.

### Pitfall 3: XDG Path Doubles in config.py's `_find_config_file()`
**What goes wrong:** Both the CLI's `agent_brain_cli/config.py` and the config command's `agent_brain_cli/commands/config.py` have their own `_find_config_file()` implementations that need identical priority fixes.
**Why it happens:** The search logic is duplicated across two files.
**How to avoid:** Update both. Consider consolidating to a single shared `_find_config_file()` in `xdg_paths.py` or the main `config.py` and importing it in `commands/config.py`.
**Warning signs:** `agent-brain config show` shows different search order than actual config loading.

### Pitfall 4: Test Mocking Path.home()
**What goes wrong:** Tests that mock `Path.home()` or use tmp_path need to be updated to account for the XDG env var logic.
**Why it happens:** `get_xdg_config_dir()` checks `XDG_CONFIG_HOME` before falling back to `Path.home()`. Tests that set `XDG_CONFIG_HOME` will hit the XDG path; tests that don't will hit the home-based default.
**How to avoid:** In tests for xdg_paths, use `patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path)})` to control the path. Existing tests for `_find_config_file()` that mock at step 4/5 need their mock indices updated.
**Warning signs:** Tests pass with `XDG_CONFIG_HOME` set but fail in clean environments.

### Pitfall 5: `storage_paths.resolve_shared_project_dir()` in Server
**What goes wrong:** Server-side `resolve_shared_project_dir()` hardcodes `Path.home() / ".agent-brain" / "projects"`. If user has migrated, this silently creates a new `~/.agent-brain/projects/` directory.
**Why it happens:** Server doesn't import from the CLI's `xdg_paths.py` (different package).
**How to avoid:** Server's `resolve_shared_project_dir()` should read `AGENT_BRAIN_SHARED_DIR` env var or check a new XDG data path. The CONTEXT.md specifies shared project data is user-configurable, so an env var override is the right approach.

## Code Examples

Verified patterns from existing codebase:

### Existing `--yes` Confirmation Pattern (from reset.py)
```python
# Source: agent-brain-cli/agent_brain_cli/commands/reset.py
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
def reset_command(url: str | None, yes: bool, json_output: bool) -> None:
    if not yes and not json_output:
        console.print("[yellow]Warning:[/] This will permanently delete all indexed documents.")
        if not Confirm.ask("Are you sure you want to reset the index?"):
            console.print("[dim]Aborted.[/]")
            return
```

Apply same pattern in `uninstall_command`:
```python
if not yes and not json_output:
    console.print("[yellow]Warning:[/] This will remove all Agent Brain global configuration.")
    console.print("[dim]Project .claude/agent-brain/ directories will NOT be touched.[/]")
    if not Confirm.ask("Remove all Agent Brain global data?", default=False):
        console.print("[dim]Aborted.[/]")
        return
```

### Existing Registry Read Pattern (from list_cmd.py)
```python
# Source: agent-brain-cli/agent_brain_cli/commands/list_cmd.py lines 51-60
def get_registry() -> dict[str, Any]:
    """Load the global registry of Agent Brain projects."""
    registry_path = Path.home() / ".agent-brain" / "registry.json"
    # BECOMES:
    # registry_path = get_registry_path()
```

### Existing Registry Write Pattern (from start.py)
```python
# Source: agent-brain-cli/agent_brain_cli/commands/start.py lines 146-164
def update_registry(project_root: Path, state_dir: Path) -> None:
    """Add project to global registry."""
    registry_dir = Path.home() / ".agent-brain"   # <-- replace
    # BECOMES:
    registry_dir = get_xdg_state_dir()
    registry_dir.mkdir(parents=True, exist_ok=True)
    registry_path = registry_dir / "registry.json"
```

### Click `err=True` for stderr output
```python
# Print migration notice to stderr, not stdout (doesn't pollute JSON output)
click.echo("Migrated config to ~/.config/agent-brain/", err=True)
```

### Server `storage_paths.py` pattern (shared project dir)
```python
# Source: agent-brain-server/agent_brain_server/storage_paths.py line 76
def resolve_shared_project_dir(project_id: str) -> Path:
    # BECOMES:
    import os
    base = os.environ.get("AGENT_BRAIN_SHARED_DIR")
    if base:
        shared_dir = Path(base) / "projects" / project_id / "data"
    else:
        # XDG data dir: ~/.local/share/agent-brain/projects/
        xdg_data_home = os.environ.get("XDG_DATA_HOME")
        if xdg_data_home:
            shared_dir = Path(xdg_data_home) / "agent-brain" / "projects" / project_id / "data"
        else:
            shared_dir = Path.home() / ".local" / "share" / "agent-brain" / "projects" / project_id / "data"
    shared_dir.mkdir(parents=True, exist_ok=True)
    return shared_dir
```

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing) |
| Config file | `agent-brain-cli/pyproject.toml` (pytest section) |
| Quick run command | `cd agent-brain-cli && poetry run pytest tests/test_xdg_paths.py tests/test_config.py -x` |
| Full suite command | `cd agent-brain-cli && poetry run pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| XDG-01 | `get_xdg_config_dir()` returns `~/.config/agent-brain` by default | unit | `pytest tests/test_xdg_paths.py::TestXdgPaths::test_config_dir_default -x` | ❌ Wave 0 |
| XDG-02 | `get_xdg_state_dir()` returns `~/.local/state/agent-brain` by default | unit | `pytest tests/test_xdg_paths.py::TestXdgPaths::test_state_dir_default -x` | ❌ Wave 0 |
| XDG-03 | `get_xdg_config_dir()` respects `XDG_CONFIG_HOME` env var | unit | `pytest tests/test_xdg_paths.py::TestXdgPaths::test_config_dir_env_var -x` | ❌ Wave 0 |
| XDG-03 | `get_xdg_state_dir()` respects `XDG_STATE_HOME` env var | unit | `pytest tests/test_xdg_paths.py::TestXdgPaths::test_state_dir_env_var -x` | ❌ Wave 0 |
| MIG-01 | Migration copies files and removes legacy dir | unit | `pytest tests/test_xdg_paths.py::TestMigration::test_migration_copies_and_removes -x` | ❌ Wave 0 |
| MIG-01 | Migration skips if XDG dirs already exist | unit | `pytest tests/test_xdg_paths.py::TestMigration::test_migration_skips_if_xdg_exists -x` | ❌ Wave 0 |
| MIG-01 | Migration skips if no legacy dir | unit | `pytest tests/test_xdg_paths.py::TestMigration::test_migration_noop_no_legacy -x` | ❌ Wave 0 |
| MIG-02 | Migration prints notice to stderr | unit | `pytest tests/test_xdg_paths.py::TestMigration::test_migration_notice_to_stderr -x` | ❌ Wave 0 |
| MIG-02 | Migration failure is non-blocking (warn + continue) | unit | `pytest tests/test_xdg_paths.py::TestMigration::test_migration_failure_nonfatal -x` | ❌ Wave 0 |
| MIG-03 | Deprecation warning printed when legacy config fallback used | unit | `pytest tests/test_config.py::TestFindConfigFile::test_legacy_fallback_prints_deprecation -x` | ❌ Wave 0 (add to existing file) |
| CFG-01 | XDG config path checked before legacy in CLI config | unit | `pytest tests/test_config.py::TestFindConfigFile::test_xdg_before_legacy -x` | ❌ Wave 0 (add to existing file) |
| REG-01 | `update_registry` writes to XDG state dir | unit | `pytest tests/test_multi_instance_commands.py::TestStartCommand::test_registry_uses_xdg -x` | ❌ Wave 0 (add to existing file) |
| REG-02 | `remove_from_registry` reads from XDG state dir | unit | `pytest tests/test_multi_instance_commands.py::TestStopCommand::test_remove_registry_uses_xdg -x` | ❌ Wave 0 (add to existing file) |
| UNI-01 | `agent-brain uninstall` removes XDG and legacy dirs | unit | `pytest tests/test_uninstall_command.py::TestUninstallCommand::test_removes_global_dirs -x` | ❌ Wave 0 |
| UNI-01 | Uninstall stops running servers before removal | unit | `pytest tests/test_uninstall_command.py::TestUninstallCommand::test_stops_servers_first -x` | ❌ Wave 0 |
| UNI-02 | Uninstall prompts for confirmation by default | unit | `pytest tests/test_uninstall_command.py::TestUninstallCommand::test_confirmation_prompt -x` | ❌ Wave 0 |
| UNI-03 | `--yes` flag skips confirmation | unit | `pytest tests/test_uninstall_command.py::TestUninstallCommand::test_yes_flag_skips_prompt -x` | ❌ Wave 0 |
| UNI-01 | Uninstall does NOT remove `.claude/agent-brain/` project dirs | unit | `pytest tests/test_uninstall_command.py::TestUninstallCommand::test_does_not_touch_project_dirs -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `cd agent-brain-cli && poetry run pytest tests/test_xdg_paths.py tests/test_config.py tests/test_uninstall_command.py tests/test_multi_instance_commands.py -x`
- **Per wave merge:** `cd agent-brain-cli && poetry run pytest`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_xdg_paths.py` — covers XDG-01 through MIG-03 (new module tests)
- [ ] `tests/test_uninstall_command.py` — covers UNI-01 through UNI-03
- [ ] `agent_brain_cli/xdg_paths.py` — the shared helper module itself must be created

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `Path.home() / ".agent-brain"` for all global state | XDG-compliant `~/.config/agent-brain/` + `~/.local/state/agent-brain/` | This phase | Linux users with separate ~/.config mounts get proper separation |
| XDG checked after legacy | XDG checked before legacy | This phase | New installs use XDG; old installs auto-migrate |
| No uninstall mechanism | `agent-brain uninstall` command | This phase | Clean removal for CI, dev machines, package managers |

## Open Questions

1. **Should `commands/config.py` import `_find_config_file` from `config.py` or have its own copy?**
   - What we know: Currently duplicated — `config.py` has one, `commands/config.py` has another. The two implementations are slightly different (server vs CLI context).
   - What's unclear: Whether they should be unified or kept separate (they serve slightly different contexts).
   - Recommendation: Keep separate but apply the same priority fix to both. Consolidation is a separate refactor concern.

2. **How should `resolve_shared_project_dir()` in the server handle the XDG migration?**
   - What we know: It currently hardcodes `~/.agent-brain/projects/`. The CONTEXT.md says shared project data path is user-configurable.
   - What's unclear: Whether existing data under `~/.agent-brain/projects/` needs to be migrated too, or just the path resolution updated.
   - Recommendation: Add `AGENT_BRAIN_SHARED_DIR` env var support and use `~/.local/share/agent-brain/projects/` as new default. Existing data under `~/.agent-brain/projects/` is separate from config/registry, so it's not part of the auto-migration. A separate migration for project data would be out of scope for this phase.

## Sources

### Primary (HIGH confidence)
- Direct code inspection — `agent-brain-cli/agent_brain_cli/config.py` (full read)
- Direct code inspection — `agent-brain-cli/agent_brain_cli/commands/start.py` (full read)
- Direct code inspection — `agent-brain-cli/agent_brain_cli/commands/stop.py` (full read)
- Direct code inspection — `agent-brain-cli/agent_brain_cli/commands/list_cmd.py` (full read)
- Direct code inspection — `agent-brain-cli/agent_brain_cli/commands/reset.py` (full read — template for uninstall)
- Direct code inspection — `agent-brain-cli/agent_brain_cli/commands/init.py` (full read)
- Direct code inspection — `agent-brain-server/agent_brain_server/config/provider_config.py` (full read)
- Direct code inspection — `agent-brain-server/agent_brain_server/storage_paths.py` (full read)
- Direct code inspection — `agent-brain-cli/tests/test_config.py` (full read — test patterns)
- Direct code inspection — `agent-brain-cli/tests/test_multi_instance_commands.py` (partial read)
- XDG Base Directory Specification v0.8 — standard env var names `XDG_CONFIG_HOME`, `XDG_STATE_HOME`, `XDG_DATA_HOME` with documented fallbacks

### Secondary (MEDIUM confidence)
- Python stdlib `shutil.copytree()`, `shutil.rmtree()` docs — standard behavior for directory operations
- `click.echo(err=True)` — documented Click API for stderr output

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies; all tools verified in codebase
- Architecture: HIGH — xdg_paths.py helper pattern confirmed by code structure; all call sites identified
- Pitfalls: HIGH — identified from direct code reading of 5 affected files

**Research date:** 2026-03-12
**Valid until:** 2026-06-12 (stable stdlib + click patterns; XDG spec is stable)
