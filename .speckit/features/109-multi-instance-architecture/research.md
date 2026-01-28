# Research: Multi-Instance Architecture

**Feature**: 109-multi-instance-architecture
**Date**: 2026-01-27

## Decision 1: Port Allocation Strategy

**Decision**: Use OS-assigned port (bind to port 0) with post-startup runtime.json write.

**Rationale**: The current `pick_free_port()` pattern has a TOCTOU race condition where the port can be taken between selection and binding. Binding to port 0 lets the OS atomically assign a free port. The server writes `runtime.json` only after the socket is bound, guaranteeing the reported port is actually in use.

**Alternatives Considered**:
- **Sequential port scanning (8000, 8001, ...)**: Rejected. Still has race conditions and creates predictable port usage that could collide with other services.
- **Port reservation file**: Rejected. Adds complexity without solving the fundamental TOCTOU problem.
- **Unix domain sockets**: Rejected. Would break HTTP-based agent discovery and existing CLI client.

**Implementation**: Uvicorn supports `port=0`. After startup, read actual port from `server.servers[0].sockets[0].getsockname()[1]`.

---

## Decision 2: Project Root Resolution Strategy

**Decision**: Multi-strategy resolution with deterministic ordering: git root > `.claude/` marker > `pyproject.toml` > current directory. Always resolve symlinks.

**Rationale**: Git repository root is the most reliable project boundary for developer workflows. The `.claude/` directory is the Claude Code convention. `pyproject.toml` covers Python projects outside git. The fallback to cwd ensures the system always works, even in unconventional setups.

**Alternatives Considered**:
- **Environment variable only**: Rejected. Requires manual configuration per project, violates SC-008 (3-step onboarding).
- **Config file only**: Rejected. Chicken-and-egg problem — need to find the project to find the config.
- **Git-only**: Rejected. Not all projects use git (e.g., quick experiments, monorepo subdirectories).

**Implementation**: `subprocess.run(["git", "rev-parse", "--show-toplevel"])` with 5s timeout, then walk-up marker search, then `Path.cwd().resolve()`.

---

## Decision 3: Lock File Protocol

**Decision**: Use `fcntl.flock()` (Unix) exclusive lock on `doc-serve.lock` with separate `doc-serve.pid` for stale detection.

**Rationale**: `fcntl.flock()` is automatically released when the process exits (including crashes), preventing permanent lock-out. A separate PID file allows stale detection by checking if the owning process is still alive. This two-file approach separates the lock mechanism (OS-level) from the diagnostic information (PID for human debugging).

**Alternatives Considered**:
- **PID file only (no flock)**: Rejected. PID reuse by the OS could cause false "alive" detection. Not atomic.
- **Advisory lockfile with timeout**: Rejected. Adds complexity and doesn't auto-release on crash.
- **Socket-based locking**: Rejected. Over-engineered for local-only use case.

**Implementation**: Acquire flock on startup, hold for process lifetime, write PID to separate file. On startup, check PID file first for fast stale detection, then attempt flock.

---

## Decision 4: State Directory Location

**Decision**: Per-project state in `<repo>/.claude/doc-serve/`. Shared daemon state in `~/.doc-serve/`.

**Rationale**: The `.claude/` directory is the established Claude Code convention for tool state. Placing doc-serve state under `.claude/doc-serve/` follows this convention and allows state to travel with the project (git-ignorable but co-located). The home directory location for the shared daemon follows Unix conventions for user-level daemon state.

**Alternatives Considered**:
- **XDG directories (`~/.local/share/doc-serve/`)**: Rejected. Doesn't co-locate state with project; harder to discover.
- **Project root directly (`.doc-serve/`)**: Rejected. Pollutes project root; doesn't follow Claude Code conventions.
- **Temp directory (`/tmp/doc-serve/`)**: Rejected. Lost on reboot; no persistence for indexes.

---

## Decision 5: Shared Mode Project Identification

**Decision**: Use first 8 characters of SHA-256 hash of the canonical project root path, prefixed with `p_`.

**Rationale**: Deterministic, collision-resistant, filesystem-safe. The `p_` prefix makes project directories easily identifiable. 8 hex characters provide 4 billion possible values, which is more than sufficient for local development use.

**Alternatives Considered**:
- **Full path as directory name**: Rejected. Path separators are invalid in directory names; extremely long paths.
- **Project name from pyproject.toml**: Rejected. Not all projects have this; could collide across repos.
- **UUID**: Rejected. Not deterministic — same project would get different IDs on different invocations.

---

## Decision 6: Singleton Refactoring for Multi-Instance

**Decision**: Replace global singletons with application-state-scoped instances passed through FastAPI's dependency injection.

**Rationale**: The current global singletons (`_vector_store`, `_bm25_manager`, `_indexing_service`) prevent per-project isolation in shared mode. FastAPI's `app.state` provides a natural place to store per-application instances. In project mode, there's one app per project. In shared mode, instances are keyed by project_id in a dictionary on `app.state`.

**Alternatives Considered**:
- **Thread-local storage**: Rejected. Async code doesn't map to threads; would break with asyncio.
- **Context variables**: Partially viable but adds complexity without clear benefit over app.state.
- **Recreate per-request**: Rejected. Too expensive for ChromaDB and LlamaIndex initialization.

---

## Decision 7: Discovery File Schema Versioning

**Decision**: Include `schema_version: 1` in runtime.json. Readers MUST check version and fail gracefully on unknown versions.

**Rationale**: The discovery file is a cross-component contract read by the server, CLI, and skills. Schema versioning ensures forward compatibility when the format evolves. Version 1 is minimal; future versions can add fields without breaking existing readers.

**Alternatives Considered**:
- **No versioning**: Rejected. Any schema change would break all consumers simultaneously.
- **Semantic versioning string**: Rejected. Over-engineered for a simple JSON schema; integer suffices.
