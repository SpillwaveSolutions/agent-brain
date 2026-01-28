# Doc-Serve Multi-Instance Architecture Specification

**Version:** 2.0.0  
**Date:** 2026-01-27  
**Status:** Implementation Ready

## Executive Summary

Refactor doc-serve from a single-instance architecture (tied to install directory) to support concurrent multi-project operation with two deployment modes:

1. **Mode A: Per-Project (Dedicated)** - One server process per repository
2. **Mode B: Shared Daemon** - Single process serving multiple repositories

The key insight: **agents always read the same discovery file** (`<repo>/.claude/doc-serve/runtime.json`) regardless of mode. The file just contains different content.

---

## Problem Statement

### Current Limitations

1. **Single Instance** - Only one doc-serve can run at a time
2. **Home Directory Coupling** - State stored globally in `~/.doc-serve` or install location
3. **Port Conflicts** - No automatic port management
4. **No Project Isolation** - Indexes mix across projects
5. **No Stale Detection** - runtime.json can be orphaned

### Requirements

1. Run multiple doc-serve instances concurrently (one per project)
2. State travels with project (can be git-ignored)
3. Collision-free port allocation
4. Clean agent discovery contract
5. Optional shared daemon for resource efficiency

---

## Architecture

### Deployment Modes

#### Mode A: Per-Project (Dedicated Instances)

```
┌─────────────────────────────────────────────────────────────┐
│  Project A                      Project B                    │
│  ┌─────────────────┐           ┌─────────────────┐          │
│  │ doc-serve:49321 │           │ doc-serve:49322 │          │
│  └────────┬────────┘           └────────┬────────┘          │
│           │                             │                    │
│  .claude/doc-serve/            .claude/doc-serve/           │
│  ├── runtime.json              ├── runtime.json             │
│  ├── config.json               ├── config.json              │
│  ├── data/                     ├── data/                    │
│  └── logs/                     └── logs/                    │
└─────────────────────────────────────────────────────────────┘
```

- One process per repository
- State: `<repo>/.claude/doc-serve/`
- OS-assigned port (bind to `:0`)
- Full isolation between projects

#### Mode B: Shared Daemon (Single Instance)

```
┌─────────────────────────────────────────────────────────────┐
│                    Shared Daemon :45123                      │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              doc-serve (shared mode)                │    │
│  │  project_id routing → per-project indexes          │    │
│  └─────────────────────────────────────────────────────┘    │
│                          │                                   │
│  ~/.doc-serve/                                              │
│  ├── runtime.json        (daemon runtime)                   │
│  ├── shared_config.json  (global settings)                  │
│  └── projects/                                              │
│      ├── p_7f1c2c9e/     (project A)                       │
│      │   ├── config.json                                    │
│      │   └── data/                                          │
│      └── p_3a8b2d1f/     (project B)                       │
│          ├── config.json                                    │
│          └── data/                                          │
│                                                             │
│  Project A/.claude/doc-serve/runtime.json → points to daemon│
│  Project B/.claude/doc-serve/runtime.json → points to daemon│
└─────────────────────────────────────────────────────────────┘
```

- One long-running process serving multiple repos
- State: `~/.doc-serve/`
- Projects identified by `project_id` (hash of canonical repo root)
- Lower resource overhead

---

## Directory Structure

### Per-Project State (`<repo>/.claude/doc-serve/`)

```
<repo>/.claude/doc-serve/
├── config.json          # Optional, can be committed to VCS
├── runtime.json         # Generated at startup, NEVER commit (add to .gitignore)
├── doc-serve.lock       # Prevents double-start
├── doc-serve.pid        # Process ID for stale detection
├── data/                # LlamaIndex indexes, Chroma DB
│   ├── llamaindex/
│   ├── chroma_db/
│   └── bm25_index/
└── logs/
    └── doc-serve.log
```

### Shared Daemon State (`~/.doc-serve/`)

```
~/.doc-serve/
├── runtime.json            # Shared daemon runtime
├── shared_config.json      # Global settings
├── doc-serve.lock
├── doc-serve.pid
├── logs/
│   └── doc-serve.log
└── projects/
    └── <project_id>/
        ├── config.json     # Per-project overrides
        └── data/
            ├── llamaindex/
            ├── chroma_db/
            └── bm25_index/
```

---

## File Schemas

### runtime.json (Mode A: Per-Project)

```json
{
  "schema_version": 1,
  "mode": "project",
  "project_root": "/abs/path/to/repo",
  "instance_id": "ds_3f0f1c",
  "base_url": "http://127.0.0.1:49321",
  "bind_host": "127.0.0.1",
  "port": 49321,
  "pid": 71244,
  "started_at": "2026-01-27T19:13:02Z"
}
```

### runtime.json (Mode B: Shared - Per-Repo Pointer)

```json
{
  "schema_version": 1,
  "mode": "shared",
  "project_root": "/abs/path/to/repo",
  "project_id": "p_7f1c2c9e",
  "base_url": "http://127.0.0.1:45123"
}
```

### config.json (Per-Project)

```json
{
  "mode": "project",
  "bind_host": "127.0.0.1",
  "port": 0,
  "data_dir": "data",
  "log_dir": "logs",
  "shared_server_url": null
}
```

### shared_config.json (Shared Daemon)

```json
{
  "bind_host": "127.0.0.1",
  "port": 45123,
  "embedding_model": "text-embedding-3-large",
  "chunk_size": 512,
  "chunk_overlap": 50,
  "max_concurrent_indexing": 2
}
```

---

## Critical Fixes (From Current Implementation)

### Fix 1: Port Race Condition (TOCTOU)

**Problem:** `pick_free_port()` has a race condition - port can be taken between pick and bind.

**Solution:** Server binds to port 0 directly, then reports actual bound port.

```python
# WRONG (current)
port = pick_free_port()  # Race window here!
uvicorn.run(app, port=port)

# CORRECT (new)
config = uvicorn.Config(app, host="127.0.0.1", port=0)
server = uvicorn.Server(config)
# After startup, get actual port from server.servers[0].sockets[0].getsockname()[1]
```

**Implementation:**
1. FastAPI/uvicorn binds to port 0
2. Server writes `runtime.json` AFTER startup with actual port
3. Startup script waits for `runtime.json` to appear

### Fix 2: Canonical Project Root

**Problem:** Different shells/cwd/symlinks generate different project_ids and state dirs.

**Solution:** Deterministic resolution with symlink resolution.

```python
def get_project_root(start_path: Path = None) -> Path:
    """Resolution order:
    1. git rev-parse --show-toplevel (if in git repo)
    2. Walk up to find .claude/ directory
    3. Walk up to find pyproject.toml
    4. Current directory (fallback)
    
    Always returns Path.resolve() (absolute, symlink-resolved)
    """
    start = Path(start_path or Path.cwd()).resolve()
    
    # Try git first
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, cwd=str(start), timeout=5
        )
        if result.returncode == 0:
            return Path(result.stdout.strip()).resolve()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    # Walk up for markers
    current = start
    while current != current.parent:
        if (current / ".claude").is_dir():
            return current
        if (current / "pyproject.toml").is_file():
            return current
        current = current.parent
    
    return start
```

### Fix 3: Runtime Discovery Resilience

**Problem:** `runtime.json` can be stale (pid dead, port reused, server crashed).

**Solution:** Treat `runtime.json` as cache, always validate with health check.

```python
def discover_instance(project_root: Path) -> Optional[RuntimeState]:
    """Read runtime.json and validate it's actually alive."""
    state_dir = project_root / ".claude" / "doc-serve"
    runtime = read_runtime_state(state_dir)
    
    if runtime is None:
        return None
    
    # Validate PID is alive (for project mode)
    if runtime.mode == "project" and not is_pid_alive(runtime.pid):
        cleanup_stale_runtime(state_dir)
        return None
    
    # Validate health endpoint responds
    if not check_health_sync(runtime.base_url):
        cleanup_stale_runtime(state_dir)
        return None
    
    return runtime
```

---

## API Changes

### Shared Mode Endpoints

All requests include `project_id` when in shared mode:

```
POST /index
Body: {"project_id": "p_7f1c2c9e", "folder_path": "/path/to/docs", ...}

POST /query
Body: {"project_id": "p_7f1c2c9e", "query": "how do I...", ...}

GET /health
Response: {"status": "healthy", "mode": "shared", "active_projects": 3}

GET /projects/{project_id}/status
Response: {"total_chunks": 1200, "last_indexed_at": "..."}
```

### Project Mode Endpoints (Unchanged)

Same as current, no `project_id` needed since one server = one project.

---

## CLI Commands

### New CLI Structure

```bash
# Start server for current project (auto-detects mode from config)
doc-serve start [--state-dir PATH] [--port PORT] [--mode project|shared]

# Check status
doc-serve status [--project PATH]

# Stop server
doc-serve stop [--project PATH]

# List all running instances
doc-serve list

# Initialize config for a project
doc-serve init [--mode project|shared]
```

### Examples

```bash
# Start per-project server (default)
cd /path/to/my-repo
doc-serve start
# → Server started at http://127.0.0.1:49321
# → State: /path/to/my-repo/.claude/doc-serve/

# Start shared daemon
doc-serve start --mode shared
# → Shared daemon started at http://127.0.0.1:45123
# → State: ~/.doc-serve/

# Check status from any subdirectory
cd /path/to/my-repo/src/deep/nested
doc-serve status
# → Doc-serve running at http://127.0.0.1:49321 (project mode)
# → Indexed: 1,234 chunks from 56 files
```

---

## Configuration Precedence

1. CLI flags (`--port`, `--state-dir`, `--mode`)
2. Environment variables (`DOC_SERVE_MODE`, `DOC_SERVE_STATE_DIR`, `DOC_SERVE_PORT`)
3. Project config file (`<repo>/.claude/doc-serve/config.json`)
4. Shared config file (`~/.doc-serve/shared_config.json`)
5. Built-in defaults

**Default mode:** `project` (per-repo instance)

---

## Lock File Protocol

### Startup Logic

```
1. Resolve project_root (canonical path)
2. Determine state_dir based on mode
3. Check if doc-serve.lock exists:
   a. Read doc-serve.pid
   b. Check if PID is alive
   c. If alive, check health endpoint
   d. If healthy → return existing base_url (already running)
   e. If stale → delete lock, pid, runtime.json and continue
4. Acquire exclusive lock on doc-serve.lock
5. Write doc-serve.pid with current PID
6. Start server (bind to port 0)
7. After server binds, write runtime.json with actual port
8. Hold lock for lifetime of process
```

### Cleanup Logic

```
1. On normal shutdown:
   - Remove runtime.json
   - Remove doc-serve.pid
   - Release doc-serve.lock
   
2. On crash (handled by next startup):
   - Stale detection finds dead PID
   - Cleanup removes orphaned files
```

---

## LlamaIndex Integration

### Storage Path Resolution

```python
def get_storage_paths(state_dir: Path, project_id: Optional[str] = None) -> dict:
    """Get all storage paths for a project."""
    if project_id:
        # Shared mode - project-specific subdirectory
        base = Path.home() / ".doc-serve" / "projects" / project_id / "data"
    else:
        # Project mode - state_dir/data
        base = state_dir / "data"
    
    return {
        "persist_dir": base / "llamaindex",
        "chroma_dir": base / "chroma_db",
        "bm25_dir": base / "bm25_index",
    }
```

### Settings Migration

Every LlamaIndex component that currently uses hardcoded paths must be updated:

| Component | Current | New |
|-----------|---------|-----|
| `CHROMA_PERSIST_DIR` | `./chroma_db` | `<state_dir>/data/chroma_db` |
| `BM25_INDEX_PATH` | `./bm25_index` | `<state_dir>/data/bm25_index` |
| LlamaIndex storage | `./storage` | `<state_dir>/data/llamaindex` |

---

## Implementation Plan

### Phase 1: State Directory Decoupling

1. Add `--state-dir` CLI flag
2. Add `DOC_SERVE_STATE_DIR` environment variable
3. Update all storage paths to use `state_dir`
4. Update `settings.py` to accept runtime overrides

### Phase 2: Per-Project Mode (Mode A)

1. Implement `runtime.py` (read/write/validate runtime.json)
2. Implement `locking.py` (lock acquisition with stale detection)
3. Implement port 0 binding with post-startup runtime.json write
4. Update CLI with `start`, `stop`, `status` commands

### Phase 3: Shared Mode (Mode B)

1. Implement `project_id` generation and routing
2. Add `project_id` parameter to all endpoints
3. Implement per-project storage under `~/.doc-serve/projects/`
4. Add shared daemon management

### Phase 4: Agent Integration

1. Create discovery function for skills/agents
2. Add auto-start capability
3. Document the contract for skill authors

---

## Module Structure

```
doc_serve_server/
├── __init__.py
├── runtime.py          # NEW: Runtime state management
├── locking.py          # NEW: Lock file handling
├── storage.py          # NEW: Storage path resolution
├── config/
│   ├── __init__.py
│   └── settings.py     # MODIFIED: Add state_dir support
├── api/
│   ├── __init__.py
│   ├── main.py         # MODIFIED: Port 0 binding, runtime.json write
│   └── routers/
│       ├── health.py   # MODIFIED: Include mode info
│       ├── index.py    # MODIFIED: project_id routing (shared mode)
│       └── query.py    # MODIFIED: project_id routing (shared mode)
├── models/             # Unchanged
├── indexing/           # Unchanged (paths come from storage.py)
├── services/           # Unchanged
└── cli/                # NEW: CLI commands
    ├── __init__.py
    ├── main.py
    ├── start.py
    ├── stop.py
    └── status.py
```

---

## Testing Strategy

### Unit Tests

- `test_runtime.py` - runtime.json read/write/validation
- `test_locking.py` - lock acquisition, stale detection
- `test_storage.py` - path resolution for both modes

### Integration Tests

- Start/stop cycle in project mode
- Start/stop cycle in shared mode
- Multiple concurrent project-mode instances
- Stale lock cleanup
- Port collision handling

### End-to-End Tests

- Agent discovers running instance
- Agent starts instance if not running
- Agent handles instance crash and recovery

---

## Migration Guide

### For Existing Users

1. Existing `~/.doc-serve` or `./chroma_db` data will NOT be migrated automatically
2. First run will create new state directory
3. Re-index documents to populate new location

### For Skill Authors

```python
# Old way (don't do this)
BASE_URL = "http://127.0.0.1:8000"  # Hardcoded!

# New way
from doc_serve_client import discover_or_start

runtime = discover_or_start(project_root=Path.cwd())
BASE_URL = runtime.base_url  # Dynamic!
```

---

## Appendix: Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DOC_SERVE_MODE` | `project` | Deployment mode (`project` or `shared`) |
| `DOC_SERVE_STATE_DIR` | (auto) | Override state directory |
| `DOC_SERVE_PORT` | `0` | Port to bind (0 = auto) |
| `DOC_SERVE_HOST` | `127.0.0.1` | Host to bind |
| `DOC_SERVE_LOG_LEVEL` | `INFO` | Logging level |

---

## Appendix: Gitignore Additions

Add to project `.gitignore`:

```gitignore
# Doc-serve runtime state (never commit)
.claude/doc-serve/runtime.json
.claude/doc-serve/doc-serve.lock
.claude/doc-serve/doc-serve.pid
.claude/doc-serve/data/
.claude/doc-serve/logs/
```

Optionally commit:
```
# This CAN be committed for team-shared config
.claude/doc-serve/config.json
```