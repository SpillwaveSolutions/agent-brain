# Data Model: Multi-Instance Architecture

**Feature**: 109-multi-instance-architecture
**Date**: 2026-01-27

## Entities

### RuntimeState

Represents a running doc-serve instance. Written to `runtime.json` after server startup.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| schema_version | integer | Yes | Schema version (currently 1) |
| mode | string enum | Yes | `"project"` or `"shared"` |
| project_root | string (path) | Yes | Canonical absolute path to project root |
| instance_id | string | Project mode | Unique instance identifier (e.g., `ds_3f0f1c`) |
| project_id | string | Shared mode | Deterministic project identifier (e.g., `p_7f1c2c9e`) |
| base_url | string (URL) | Yes | Full URL including port (e.g., `http://127.0.0.1:49321`) |
| bind_host | string | Project mode | Host the server is bound to |
| port | integer | Project mode | Actual bound port |
| pid | integer | Project mode | OS process identifier |
| started_at | string (ISO 8601) | Project mode | Server start timestamp |

**Identity**: One RuntimeState per state directory. In project mode, the state directory is `<project_root>/.claude/doc-serve/`. In shared mode, each project gets a pointer file in its own state directory.

**Lifecycle**: Created after server binds port successfully. Deleted on graceful shutdown. Detected as stale if PID is dead or health check fails.

---

### ProjectConfig

Per-project configuration. Stored in `config.json` within the state directory.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| mode | string enum | No | `"project"` | Deployment mode preference |
| bind_host | string | No | `"127.0.0.1"` | Host to bind |
| port | integer | No | `0` | Port (0 = auto-assign) |
| data_dir | string | No | `"data"` | Relative path for index data |
| log_dir | string | No | `"logs"` | Relative path for log files |
| shared_server_url | string (URL) | No | `null` | URL of shared daemon (shared mode only) |

**Identity**: One per project state directory. Optional — system works with defaults if absent.

**Lifecycle**: Created by `doc-serve init`. Can be committed to VCS. Never auto-modified by the server.

---

### SharedConfig

Global configuration for the shared daemon. Stored in `~/.doc-serve/shared_config.json`.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| bind_host | string | No | `"127.0.0.1"` | Host to bind |
| port | integer | No | `45123` | Fixed port for shared daemon |
| embedding_model | string | No | `"text-embedding-3-large"` | OpenAI embedding model |
| chunk_size | integer | No | `512` | Document chunk size |
| chunk_overlap | integer | No | `50` | Chunk overlap |
| max_concurrent_indexing | integer | No | `2` | Max parallel indexing jobs |

**Identity**: One global instance at `~/.doc-serve/shared_config.json`.

**Lifecycle**: Created by `doc-serve init --mode shared`. Manually edited by user.

---

### LockState

Represents the lock file protocol state. Two files work together.

**doc-serve.lock**: OS-level exclusive lock (fcntl.flock). Held for process lifetime.

**doc-serve.pid**: Contains the PID of the owning process.

| Field | Type | Description |
|-------|------|-------------|
| pid | integer | Process ID of lock owner (plain text file) |

**Identity**: One per state directory.

**Lifecycle**: Lock acquired on startup, PID written immediately after. Both released/deleted on shutdown. Stale detection on next startup checks PID alive + health endpoint.

---

## Relationships

```
ProjectConfig (0..1) ──── defines mode for ────> RuntimeState (0..1)
                                                       │
RuntimeState ──── references ────> LockState (1)       │
                                                       │
SharedConfig (0..1) ──── configures ────> SharedDaemon  │
                                              │        │
                                    serves ───┘        │
                                              │        │
                                    ProjectStorage (0..N)
```

- A project has at most one RuntimeState (either a full project-mode state or a shared-mode pointer).
- A project has at most one ProjectConfig (optional).
- A project-mode RuntimeState has exactly one LockState.
- A shared daemon has one SharedConfig and one LockState.
- A shared daemon manages 0..N ProjectStorage instances (one per registered project).

## State Transitions

### Server Instance Lifecycle

```
[Not Running] ──start──> [Starting] ──bind port──> [Running] ──stop──> [Shutting Down] ──cleanup──> [Not Running]
                              │                         │
                              │                    [Crashed]
                              │                         │
                              └─────── stale detect ────┘──cleanup──> [Not Running]
```

### Lock Acquisition Flow

```
[No Lock] ──check pid──> [Stale?] ──yes──> [Cleanup] ──> [Acquire Lock] ──> [Locked]
                              │
                              no──> [Already Running] (return existing base_url)
```
