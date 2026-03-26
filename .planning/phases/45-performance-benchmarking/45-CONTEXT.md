# Phase 45: Performance Benchmarking - Context

**Gathered:** 2026-03-26
**Status:** Ready for planning
**Source:** PRD Express Path (docs/plans/phase-45-performance-benchmarking-2026-03-26.md)

<domain>
## Phase Boundary

Deliver a reproducible query benchmark workflow plus PostgreSQL pool timeout exposure, without changing retrieval algorithms or query optimization behavior. Includes nested `storage.postgres.*` config schema validation.

</domain>

<decisions>
## Implementation Decisions

### Benchmark runner
- Standalone Python script at `scripts/query_benchmark.py` (developer tool, not a CLI command)
- Benchmark through HTTP API (`/query` POST), not by calling `QueryService` directly — results reflect user-visible latency
- Measure two timings per query: client-observed end-to-end latency for p50/p95/p99/mean/QPS, and server-reported `query_time_ms` as secondary signal
- Use a fixed query set committed to the repo, sized to 20 measured iterations per mode
- 3 warm-up queries per mode before measurement
- Output Rich table to stdout + `--json` for CI
- Keep statistics and formatting logic in small testable helpers

### Reproducibility and preflight
- Add benchmark preflight checks before first timed query: server reachable, index ready, chunk count > 0, backend type detected, GraphRAG enabled/disabled, indexed folders include repo `docs/` when running baseline
- Do NOT reset user data by default
- Add explicit `--prepare-docs-corpus` flag that: resets index, indexes repo `docs/` folder, waits for job completion, optionally rebuilds graph if needed for `graph` mode
- If setup mode is not used and active corpus doesn't match `docs/`, run with a clear warning in stdout/JSON rather than silently claiming a baseline

### Backend compatibility handling
- Always attempt requested benchmark modes, but report unsupported modes explicitly instead of failing entire run
- Expected behavior:
  - Chroma + GraphRAG enabled: benchmark all 5 modes (vector, bm25, hybrid, graph, multi)
  - Chroma + GraphRAG disabled: `graph` marked unsupported; `multi` still measured
  - PostgreSQL: `graph` marked unsupported; `multi` measured with note that graph contribution is skipped
- `docs/BENCHMARKS.md` baseline tables must state backend and graph-enabled status

### Pool timeout exposure
- Add `pool_timeout: int = 30` to `PostgresConfig`
- Pass `pool_timeout` into `create_async_engine(...)`
- Extend `storage.factory` so `DATABASE_URL` override preserves YAML-provided `pool_timeout` (same pattern as `pool_size` and `pool_max_overflow`)
- Update example config and docs that already mention PostgreSQL pool settings

### Config schema validation — nested storage.postgres keys
- Extend `config_schema.py` with nested validation for `storage.postgres.*`
- Introduce allowlist of known PostgreSQL keys: host, port, database, user, password, pool_size, pool_max_overflow, pool_timeout, language, hnsw_m, hnsw_ef_construction, debug
- Add validation errors for unknown nested Postgres keys with `storage.postgres.<key>` paths
- This is NOT just appending pool_timeout — it's introducing proper nested key validation

### Documentation scope
- Write `docs/BENCHMARKS.md` with baseline numbers and run metadata (date, OS, Python version, backend, graph state, iterations, warmups, corpus identity, chunk count)
- Update `docs/POSTGRESQL_SETUP.md` and any other config docs that mention pool sizing to include `pool_timeout`

### Claude's Discretion
- Exact Rich table layout and column widths
- Benchmark query set content (representative queries for the `docs/` corpus)
- Error handling in benchmark script
- BENCHMARKS.md formatting details

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Query service
- `agent-brain-server/agent_brain_server/services/query_service.py` — All 5 retrieval mode implementations (vector, bm25, hybrid, graph, multi)
- `agent-brain-server/agent_brain_server/api/routers/query.py` — `/query` POST endpoint with `mode` field and `query_time_ms` response

### PostgreSQL storage
- `agent-brain-server/agent_brain_server/storage/postgres/config.py` — PostgresConfig with pool_size=10, pool_max_overflow=10 defaults
- `agent-brain-server/agent_brain_server/storage/postgres/connection.py` — PostgresConnectionManager with create_async_engine + QueuePool
- `agent-brain-server/agent_brain_server/storage/factory.py` — YAML config → PostgresConfig mapping (pool keys read at lines 112-114)

### Existing pool tests
- `agent-brain-server/tests/load/test_postgres_pool.py` — Existing pool metric assertions (pool_size, overflow, total)
- `agent-brain-server/tests/unit/storage/test_postgres_config.py` — Unit tests for PostgresConfig (if exists)
- `agent-brain-server/tests/unit/storage/test_postgres_connection.py` — Connection manager tests (if exists)

### Config validation (Phase 44)
- `agent-brain-cli/agent_brain_cli/config_schema.py` — Schema validation engine; currently validates top-level keys but NOT nested storage.postgres.* keys
- `agent-brain-cli/tests/test_config_validate.py` — Validation tests to extend

### Documentation
- `docs/POSTGRESQL_SETUP.md` — PostgreSQL config docs that mention pool sizing
- `docs/CONFIGURATION.md` — General configuration reference
- `docs/PROVIDER_CONFIGURATION.md` — Provider setup docs

### PRD
- `docs/plans/phase-45-performance-benchmarking-2026-03-26.md` — Full planning document with workstream breakdown, test plan, and acceptance criteria

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `httpx` async client used by CLI — can drive benchmark requests against `/query` endpoint
- Rich library already used throughout CLI for tables and formatting
- `QueryService.execute_query()` with `retrieval_mode` parameter — reference for mode behavior
- Existing `BrainApiClient` in `agent_brain_cli/client/` — has `query()` method that hits `/query`

### Established Patterns
- CLI uses Click + Rich for all commands
- Server exposes `/query` POST with `mode` field, returns `query_time_ms` in response
- Config loaded from `.agent-brain/config.yaml` via `load_provider_settings()`
- PostgresConfig fields mapped in `storage/factory.py` at lines 112-114 for pool_size and pool_max_overflow

### Integration Points
- Benchmark script hits `/query` endpoint via HTTP (same as CLI `query` command)
- Pool config flows through `storage.factory.create_storage_backend()` → `PostgresConfig` → `create_async_engine()`
- Config schema in `config_schema.py` needs nested `storage.postgres.*` key validation added

</code_context>

<specifics>
## Specific Ideas

- Benchmark output must include enough metadata to interpret results: date, OS, Python version, backend, graph-enabled state, iterations, warmups, corpus identity, chunk count
- Unsupported benchmark modes reported explicitly — never invalidate supported mode results
- Fixed committed query set for reproducible p50/p95/p99 comparisons across runs

</specifics>

<deferred>
## Deferred Ideas

None — PRD covers phase scope

</deferred>

---

*Phase: 45-performance-benchmarking*
*Context gathered: 2026-03-26 via PRD Express Path*
