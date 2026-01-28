# Tasks: Multi-Instance Architecture

**Input**: Design documents from `.speckit/features/109-multi-instance-architecture/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/api-changes.yaml, quickstart.md

**Tests**: Per Constitution III (Test-Alongside), unit and integration test tasks are included in each user story phase. Tests MUST be written during implementation in the same PR/commit.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Branch initialization and project structure preparation

- [ ] T001 Verify branch `109-multi-instance-architecture` is checked out and up to date with main
- [ ] T002 Add `.claude/doc-serve/` to `.gitignore` in the repository root (runtime.json, lock, pid files should not be tracked)
- [ ] T003 [P] Create empty module files for new server modules: `doc-serve-server/doc_serve_server/runtime.py`, `doc-serve-server/doc_serve_server/locking.py`, `doc-serve-server/doc_serve_server/storage_paths.py`, `doc-serve-server/doc_serve_server/project_root.py`
- [ ] T004 [P] Create CLI commands directory structure: `doc-svr-ctl/doc_svr_ctl/commands/__init__.py`

---

## Phase 2: Foundational — State Directory Decoupling (Blocking Prerequisites)

**Purpose**: Make all storage paths configurable so the server can run with any state directory. This is Plan Phase 1 and MUST complete before any user story work.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete. Without configurable paths, per-project isolation is impossible.

- [ ] T005 Add `state_dir` parameter and `DOC_SERVE_STATE_DIR` environment variable to `doc-serve-server/doc_serve_server/config/settings.py` — default to `None` (current behavior) for backward compatibility; when set, all storage paths resolve relative to it
- [ ] T006 Modify `VectorStoreManager.__init__` in `doc-serve-server/doc_serve_server/storage/vector_store.py` to accept an absolute `persist_dir` parameter instead of reading from global settings
- [ ] T007 Modify `BM25IndexManager.__init__` in `doc-serve-server/doc_serve_server/indexing/bm25_index.py` to accept an absolute `persist_dir` parameter instead of reading from global settings
- [ ] T008 Modify `IndexingService.__init__` in `doc-serve-server/doc_serve_server/services/indexing_service.py` to accept injected `VectorStoreManager` and `BM25IndexManager` dependencies instead of importing global singletons
- [ ] T009 Remove global singleton factory functions (`get_vector_store`, `get_bm25_manager`, `get_indexing_service`) from their respective modules and replace with FastAPI `app.state`-based initialization in `doc-serve-server/doc_serve_server/api/main.py` lifespan handler
- [ ] T010 Update all router files that depend on singletons (`doc-serve-server/doc_serve_server/api/routers/health.py`, `index.py`, `query.py`) to retrieve services from `request.app.state` instead of importing singletons
- [ ] T011 Verify existing tests pass with refactored dependency injection — run `cd doc-serve-server && poetry run pytest`
- [ ] T053 [P] Implement configuration loading in `doc-serve-server/doc_serve_server/config/settings.py` — add `load_project_config(state_dir: Path) -> ProjectConfig` that reads `config.json` from the state directory and merges with environment variables and built-in defaults per FR-009 precedence chain (CLI flags > env vars > project config > global config > defaults). CLI flag overrides are applied at call site.
- [ ] T054 Update FastAPI-generated OpenAPI spec to reflect new/modified endpoints — verify `/docs` endpoint exposes health_response_v2 (mode, instance_id, project_id, active_projects fields), index_request_v2 and query_request_v2 (optional project_id), and new `/projects/{project_id}/status` endpoint. Ensure OpenAPI schema is auto-generated from Pydantic models per Constitution II (OpenAPI-First).

**Checkpoint**: Foundation ready — server runs with configurable `state_dir`, config precedence chain, no global singletons, and updated OpenAPI spec. All existing tests pass. User story implementation can now begin.

---

## Phase 3: User Story 1 — Per-Project Server Lifecycle (Priority: P1) 🎯 MVP

**Goal**: Full per-project lifecycle with discovery, locking, crash recovery, and CLI commands. A developer can start, discover, and stop a dedicated doc-serve instance for any project.

**Independent Test**: Start doc-serve from a project root, verify it binds to a unique port, confirm `runtime.json` is written to `<repo>/.claude/doc-serve/`, query the server from a nested subdirectory, stop the server, verify all runtime artifacts are cleaned up.

### Tests for User Story 1 (Constitution III: Test-Alongside)

- [ ] T055 [P] [US1] Write unit tests for `project_root.py` in `doc-serve-server/tests/unit/test_project_root.py` — test git root resolution, cwd fallback, symlink resolution
- [ ] T056 [P] [US1] Write unit tests for `runtime.py` in `doc-serve-server/tests/unit/test_runtime.py` — test RuntimeState model validation, write/read/delete cycle, stale PID detection
- [ ] T057 [P] [US1] Write unit tests for `locking.py` in `doc-serve-server/tests/unit/test_locking.py` — test lock acquisition, release, stale detection, cleanup
- [ ] T058 [P] [US1] Write unit tests for `storage_paths.py` in `doc-serve-server/tests/unit/test_storage.py` — test state dir resolution, directory creation, path determinism
- [ ] T059 [US1] Write integration test for per-project lifecycle in `doc-serve-server/tests/integration/test_lifecycle.py` — test start/stop cycle, runtime.json creation/deletion, lock acquisition/release, port binding

### Core Modules

- [ ] T012 [P] [US1] Implement `project_root.py` in `doc-serve-server/doc_serve_server/project_root.py` — basic project root resolution using `git rev-parse --show-toplevel` (5s timeout) with fallback to `Path.cwd().resolve()`. Always resolve symlinks. Export `resolve_project_root(start_path: Path) -> Path`. Note: US2 (T026-T027) adds full fallback chain (.claude/ marker, pyproject.toml walk-up, edge cases).
- [ ] T013 [P] [US1] Implement `storage.py` in `doc-serve-server/doc_serve_server/storage_paths.py` — path resolution for per-project state directory. Given a project root, return `<root>/.claude/doc-serve/` and subdirectories (`data/`, `logs/`, `data/llamaindex/`, `data/chroma_db/`, `data/bm25_index/`). Create directories if they don't exist. Export `resolve_state_dir(project_root: Path) -> Path` and `resolve_storage_paths(state_dir: Path) -> dict`.
- [ ] T014 [P] [US1] Implement `runtime.py` in `doc-serve-server/doc_serve_server/runtime.py` — Pydantic `RuntimeState` model matching `runtime_json_project` schema from `contracts/api-changes.yaml` (fields: `schema_version`, `mode`, `project_root`, `instance_id`, `base_url`, `bind_host`, `port`, `pid`, `started_at`). Include `write_runtime(state_dir: Path, state: RuntimeState)`, `read_runtime(state_dir: Path) -> Optional[RuntimeState]`, `delete_runtime(state_dir: Path)`, and `validate_runtime(state: RuntimeState) -> bool` (checks PID alive + health endpoint).
- [ ] T015 [P] [US1] Implement `locking.py` in `doc-serve-server/doc_serve_server/locking.py` — `fcntl.flock()`-based exclusive lock on `doc-serve.lock` with separate `doc-serve.pid` file. Export `acquire_lock(state_dir: Path) -> bool` (non-blocking, returns False if held), `release_lock(state_dir: Path)`, `read_pid(state_dir: Path) -> Optional[int]`, `is_stale(state_dir: Path) -> bool` (check PID alive via `os.kill(pid, 0)`), `cleanup_stale(state_dir: Path)`.

### Server Modifications

- [ ] T016 [US1] Modify `doc-serve-server/doc_serve_server/api/main.py` to support port 0 binding — change uvicorn config to accept `port=0`, after server starts read actual port from bound socket, write `runtime.json` via `runtime.py`, register shutdown hook to call `delete_runtime()` and `release_lock()`
- [ ] T017 [US1] Modify health endpoint in `doc-serve-server/doc_serve_server/api/routers/health.py` to include `mode` field (`"project"` or `"shared"`), `instance_id`, and `project_id` in response per `health_response_v2` schema from `contracts/api-changes.yaml`

### CLI Commands

- [ ] T018 [P] [US1] Implement `start` command in `doc-svr-ctl/doc_svr_ctl/commands/start.py` — resolve project root, check for existing lock/runtime, detect and clean stale state, spawn server subprocess (daemonized), wait for health endpoint readiness, print base URL
- [ ] T019 [P] [US1] Implement `stop` command in `doc-svr-ctl/doc_svr_ctl/commands/stop.py` — read `runtime.json`, send SIGTERM to PID, wait for process exit, verify cleanup of runtime artifacts
- [ ] T020 [P] [US1] Implement `status` command in `doc-svr-ctl/doc_svr_ctl/commands/status.py` — resolve project root from cwd, read `runtime.json`, validate health endpoint, report address and indexing status (or "not running")
- [ ] T021 [P] [US1] Implement `list` command in `doc-svr-ctl/doc_svr_ctl/commands/list_cmd.py` — maintain a registry file at `~/.doc-serve/registry.json` (list of known project state directories, updated by `start`/`stop`/`init`). Scan registry entries for `runtime.json` files, validate each via health check, report table of running instances with project name, URL, mode, and PID. Fall back to scanning `~/.doc-serve/projects/` for shared mode instances.
- [ ] T022 [P] [US1] Implement `init` command in `doc-svr-ctl/doc_svr_ctl/commands/init.py` — resolve project root, create `.claude/doc-serve/` directory, write `config.json` with defaults per `config_json` schema from `contracts/api-changes.yaml`
- [ ] T023 [US1] Register all new commands in `doc-svr-ctl/doc_svr_ctl/cli.py` — add `start`, `stop`, `status` (update existing), `list`, and `init` as Click commands/groups

### Integration

- [ ] T024 [US1] Add startup integration in `doc-serve-server/doc_serve_server/api/main.py` lifespan — on startup: resolve project root → resolve state dir → acquire lock (fail if held and not stale) → bind port 0 → resolve storage paths → initialize services with resolved paths → write runtime.json. On shutdown: delete runtime.json → release lock → delete PID file.
- [ ] T025 [US1] Verify per-project lifecycle end-to-end: start server via CLI, confirm `runtime.json` written with actual port, run status from subdirectory, stop server, confirm all artifacts cleaned up

**Checkpoint**: Per-project mode is fully functional. A developer can `init → start → status → stop` for any project. Two projects can run concurrently on different ports. Crashed instances recover on next start. This is the MVP.

---

## Phase 4: User Story 2 — Project Root Discovery and State Isolation (Priority: P2)

**Goal**: Reliable canonical project root resolution ensures the same project always maps to the same state directory regardless of access path, symlinks, or current subdirectory.

**Independent Test**: Navigate to various subdirectories and symlinked paths within a project, call `resolve_project_root()`, verify it always returns the same canonical path.

> **Note**: The core `project_root.py` module was created in T012 as part of US1 (it's a shared prerequisite). This phase adds edge case handling, fallback strategies, and ensures isolation guarantees.

### Tests for User Story 2 (Constitution III: Test-Alongside)

- [ ] T060 [P] [US2] Write unit tests for enhanced project root resolution in `doc-serve-server/tests/unit/test_project_root.py` — test symlink resolution, git submodule handling, monorepo subdirectories, missing git binary fallback, .claude/ marker walk-up, pyproject.toml walk-up, cwd fallback
- [ ] T061 [US2] Write integration test for state isolation in `doc-serve-server/tests/integration/test_concurrent.py` — test that two different project roots produce completely separate ChromaDB and BM25 storage directories with no cross-contamination

### Implementation for User Story 2

- [ ] T026 [P] [US2] Enhance `resolve_project_root()` in `doc-serve-server/doc_serve_server/project_root.py` to handle edge cases: symlink resolution (`Path.resolve()`), git submodules (use outermost repo root), monorepo subdirectories (still use git root), missing git binary (fall through gracefully), and 5-second timeout on `git rev-parse`
- [ ] T027 [P] [US2] Add `.claude/` marker walk-up detection to `project_root.py` — if git resolution fails, walk parent directories looking for `.claude/` directory, then `pyproject.toml`, then fall back to `cwd.resolve()`
- [ ] T028 [US2] Validate state isolation in `storage_paths.py` — given the same canonical project root, always return the same state directory; given different roots, always return different state directories. Add assertion that `state_dir` is an absolute path.
- [ ] T029 [US2] Update `start` and `status` CLI commands (`doc-svr-ctl/doc_svr_ctl/commands/start.py`, `status.py`) to pass resolved project root through the full chain (CLI → server startup), ensuring consistent resolution

**Checkpoint**: Project root resolution is robust across symlinks, subdirectories, non-git projects, and missing tools. The same project always maps to the same state regardless of access path.

---

## Phase 5: User Story 3 — Shared Daemon Mode (Priority: P3)

**Goal**: A single long-running process serves multiple projects with per-project index isolation. Power users can reduce resource overhead while maintaining full isolation.

**Independent Test**: Start a shared daemon, register two projects, verify isolated indexes per project, query each independently, confirm discovery pointers are written into each project's state directory.

### Tests for User Story 3 (Constitution III: Test-Alongside)

- [ ] T062 [P] [US3] Write unit tests for SharedConfig and shared RuntimeState models in `doc-serve-server/tests/unit/test_runtime.py` — test shared config read/write, discovery pointer schema, project_id generation
- [ ] T063 [US3] Write integration test for shared daemon isolation in `doc-serve-server/tests/integration/test_concurrent.py` — test two projects registered with shared daemon have isolated indexes, query one does not return results from the other

### Data Model Extensions

- [ ] T030 [P] [US3] Add `SharedConfig` Pydantic model to `doc-serve-server/doc_serve_server/runtime.py` per `shared_config.json` schema from data-model.md — fields: `bind_host`, `port` (default 45123), `embedding_model`, `chunk_size`, `chunk_overlap`, `max_concurrent_indexing`. Read/write from `~/.doc-serve/shared_config.json`.
- [ ] T031 [P] [US3] Add shared-mode `RuntimeState` variant to `doc-serve-server/doc_serve_server/runtime.py` per `runtime_json_shared` schema — fields: `schema_version`, `mode="shared"`, `project_root`, `project_id`, `base_url`. This is the discovery pointer written into each project's state directory.

### Project Identification

- [ ] T032 [US3] Implement project ID generation in `doc-serve-server/doc_serve_server/project_root.py` — `generate_project_id(project_root: Path) -> str` returns `p_` + first 8 chars of SHA-256 hash of canonical path string. Deterministic and filesystem-safe.

### Server Routing

- [ ] T033 [US3] Modify `doc-serve-server/doc_serve_server/api/routers/index.py` to accept optional `project_id` field in request body per `index_request_v2` schema — required in shared mode, ignored in project mode. Route indexing to project-specific storage.
- [ ] T034 [US3] Modify `doc-serve-server/doc_serve_server/api/routers/query.py` to accept optional `project_id` field in request body per `query_request_v2` schema — required in shared mode, ignored in project mode. Route queries to project-specific indexes.
- [ ] T035 [US3] Add new endpoint `GET /projects/{project_id}/status` in `doc-serve-server/doc_serve_server/api/routers/health.py` per `project_status` schema from `contracts/api-changes.yaml` — returns project-specific indexing status.

### Shared Storage

- [ ] T036 [US3] Implement per-project storage under shared daemon in `doc-serve-server/doc_serve_server/storage_paths.py` — `resolve_shared_project_dir(project_id: str) -> Path` returns `~/.doc-serve/projects/<project_id>/data/`. Create directories on first use.
- [ ] T037 [US3] Modify `app.state` initialization in `doc-serve-server/doc_serve_server/api/main.py` to support per-project service instances in shared mode — use `Dict[str, ServiceBundle]` keyed by `project_id` instead of single instances

### CLI Extensions

- [ ] T038 [US3] Add `--mode shared` flag to `start` command in `doc-svr-ctl/doc_svr_ctl/commands/start.py` — starts shared daemon binding to configured port (default 45123), writes `runtime.json` to `~/.doc-serve/`
- [ ] T039 [US3] Add `--mode shared` flag to `init` command in `doc-svr-ctl/doc_svr_ctl/commands/init.py` — creates `~/.doc-serve/shared_config.json` with defaults
- [ ] T040 [US3] Update `status` and `list` commands to detect and display shared mode instances — show `(shared)` label and `active_projects` count

### Discovery Pointers

- [ ] T041 [US3] Implement discovery pointer writing — when a project registers with a shared daemon, write a shared-mode `runtime.json` pointer into `<project_root>/.claude/doc-serve/runtime.json` containing the daemon's `base_url` and the project's `project_id`
- [ ] T042 [US3] Update health endpoint in `doc-serve-server/doc_serve_server/api/routers/health.py` for shared mode — include `active_projects` count in response per `health_response_v2` schema

**Checkpoint**: Shared daemon mode is functional. Multiple projects share one process with isolated indexes. Discovery pointers let agents find the daemon from any project directory.

---

## Phase 6: User Story 4 — Agent and Skill Integration (Priority: P4)

**Goal**: Skills and agents can programmatically discover a running doc-serve instance for the current project, or auto-start one if none is running.

**Independent Test**: From a Python context, call `discover_or_start()`, verify it finds a running instance or starts one, confirm the returned base URL is valid and responds to health checks.

### Tests for User Story 4 (Constitution III: Test-Alongside)

- [ ] T064 [P] [US4] Write unit tests for discovery client in `doc-serve-server/tests/unit/test_discovery.py` — test discover() with valid/stale/missing runtime.json, test discover_or_start() with mock subprocess, test stale cleanup path

### Implementation for User Story 4

- [ ] T043 [P] [US4] Create discovery client module at `doc-serve-server/doc_serve_server/discovery.py` — export `discover(project_root: Path) -> Optional[RuntimeState]` that reads `runtime.json`, validates health endpoint, returns state or None
- [ ] T044 [P] [US4] Add `discover_or_start(project_root: Path) -> RuntimeState` to `doc-serve-server/doc_serve_server/discovery.py` — calls `discover()` first; if None, spawns server subprocess via the same logic as CLI `start`, waits for health readiness, returns RuntimeState
- [ ] T045 [US4] Handle stale discovery in `discovery.py` — if `runtime.json` exists but health check fails, call `cleanup_stale()` from `locking.py`, then either return None (discover-only) or auto-start (discover_or_start)
- [ ] T046 [US4] Update `doc-serve-skill/doc-serve/SKILL.md` to document the discovery contract — explain how skills should use `discover_or_start()` to connect, include Python code examples from `quickstart.md` "For Skill Authors" section

**Checkpoint**: Skills can reliably discover or auto-start doc-serve for any project. The discovery contract is documented for skill authors.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T047 [P] Update `CLAUDE.md` and `.claude/CLAUDE.md` with new CLI commands and multi-instance architecture overview
- [ ] T048 [P] Add structured logging to all new modules using Python `logging` with JSON format and correlation IDs per Constitution IV (Observability) — log to per-project `<state_dir>/logs/` directory. Include request correlation IDs for tracing. Add metrics hooks for startup time, discovery latency, and per-instance resource usage.
- [ ] T049 [P] Update `doc-serve-server/pyproject.toml` and `doc-svr-ctl/pyproject.toml` if any new dependencies are needed (verify: `fcntl` is stdlib, no new external deps expected)
- [ ] T050 Run `task before-push` from repository root to verify formatting, linting, type checking, and all tests pass
- [ ] T051 Run quickstart.md verification checklist — confirm all 7 items from quickstart.md pass
- [ ] T052 Update `.speckit/features/109-multi-instance-architecture/spec.md` status from "Draft" to "Implemented"

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Foundational — delivers MVP
- **US2 (Phase 4)**: Depends on Foundational; enhances T012 from US1
- **US3 (Phase 5)**: Depends on Foundational; extends runtime.py and storage from US1
- **US4 (Phase 6)**: Depends on Foundational; uses runtime.py from US1
- **Polish (Phase 7)**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 2 — no dependencies on other stories. **This is the MVP.**
- **US2 (P2)**: Can start after Phase 2 — enhances `project_root.py` created in US1 but is independently testable. Can run in parallel with US1 if T012 is completed first.
- **US3 (P3)**: Can start after Phase 2 — extends runtime.py and storage from US1 but adds its own models and routing. Recommend completing US1 first.
- **US4 (P4)**: Can start after Phase 2 — creates discovery client using runtime.py from US1. Recommend completing US1 first.

### Within Each User Story

- Models/modules before services
- Services before endpoints/CLI
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

**Phase 1**: T003 and T004 can run in parallel
**Phase 2**: T006, T007, T008 can run in parallel (different files); T009 depends on T006-T008; T010 depends on T009
**Phase 3 (US1)**: T012, T013, T014, T015 can all run in parallel (4 independent new modules); T018-T022 can run in parallel (5 independent CLI commands); T016-T017 depend on T012-T015
**Phase 4 (US2)**: T026, T027 can run in parallel
**Phase 5 (US3)**: T030, T031 can run in parallel; T033, T034 can run in parallel
**Phase 6 (US4)**: T043, T044 can run in parallel

---

## Parallel Example: User Story 1

```bash
# Launch all 4 core modules in parallel (no dependencies between them):
Task: "T012 [P] [US1] Implement project_root.py"
Task: "T013 [P] [US1] Implement storage_paths.py"
Task: "T014 [P] [US1] Implement runtime.py"
Task: "T015 [P] [US1] Implement locking.py"

# After core modules complete, launch 5 CLI commands in parallel:
Task: "T018 [P] [US1] Implement start command"
Task: "T019 [P] [US1] Implement stop command"
Task: "T020 [P] [US1] Implement status command"
Task: "T021 [P] [US1] Implement list command"
Task: "T022 [P] [US1] Implement init command"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T004)
2. Complete Phase 2: Foundational — State Decoupling (T005-T011)
3. Complete Phase 3: User Story 1 — Per-Project Lifecycle (T012-T025)
4. **STOP and VALIDATE**: Test per-project lifecycle end-to-end
5. Run `task before-push` to verify quality gate

### Incremental Delivery

1. Setup + Foundational → Server runs with configurable state_dir
2. Add US1 → Per-project mode works (`init → start → status → stop`) — **MVP!**
3. Add US2 → Robust project root resolution (symlinks, non-git projects)
4. Add US3 → Shared daemon mode for power users
5. Add US4 → Agent/skill discovery integration
6. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers after Foundational phase:

- Developer A: US1 (Per-Project Lifecycle) — MVP path
- Developer B: US2 (Project Root Discovery) — can start after T012 lands
- Developer C: US3 (Shared Daemon) — recommend waiting for US1 completion
- Developer D: US4 (Agent Integration) — recommend waiting for US1 completion

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks in same phase
- [USn] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Test tasks included per Constitution III (Test-Alongside): T055-T064
- `storage.py` in plan.md renamed to `storage_paths.py` to avoid collision with existing `storage/` directory
- T053 adds config precedence chain per FR-009; T054 ensures OpenAPI compliance per Constitution II
- T021 uses `~/.doc-serve/registry.json` for instance discovery (resolves U1)
