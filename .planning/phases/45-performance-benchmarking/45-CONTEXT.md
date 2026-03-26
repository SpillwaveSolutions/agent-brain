# Phase 45: Performance Benchmarking - Context

**Gathered:** 2026-03-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Measure query latency across all retrieval modes, expose PostgreSQL connection pool tuning via config.yaml, and document baseline performance numbers in docs/BENCHMARKS.md. No query optimization work — just measurement and configuration exposure.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
- Benchmark script design: standalone Python script in `scripts/` (not a CLI command — benchmarks are developer tools, not user-facing)
- Metrics: p50, p95, p99 latency, mean, and queries/sec for each retrieval mode (vector, bm25, hybrid, graph, multi)
- Warm-up: 3 warm-up queries before measurement to prime caches and connections
- Iterations: 20 queries per mode by default, configurable via CLI arg
- Reference dataset: use `docs/` folder as the benchmark corpus — it's always present, version-controlled, and ~30 files gives a realistic small-project baseline
- Output: Rich table to stdout with optional `--json` flag for CI integration
- BENCHMARKS.md: structured markdown with table per mode, system info header (Python version, OS, backend type), and date stamp
- Pool config: add `pool_timeout` (default 30s) to PostgresConfig alongside existing pool_size and pool_max_overflow; update config_schema.py to include the new key in validation
- Pool config section in config.yaml: `storage.postgres.pool_size`, `storage.postgres.pool_max_overflow`, `storage.postgres.pool_timeout` (flat keys under storage.postgres, matching current PostgresConfig field names)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Query service
- `agent-brain-server/agent_brain_server/services/query_service.py` — All 5 retrieval mode implementations (vector, bm25, hybrid, graph, multi)

### PostgreSQL storage
- `agent-brain-server/agent_brain_server/storage/postgres/config.py` — PostgresConfig with pool_size=10, pool_max_overflow=10 defaults
- `agent-brain-server/agent_brain_server/storage/postgres/connection.py` — PostgresConnectionManager with create_async_engine + QueuePool
- `agent-brain-server/agent_brain_server/storage/factory.py` — YAML config → PostgresConfig mapping (pool keys read here)

### Existing pool tests
- `agent-brain-server/tests/load/test_postgres_pool.py` — Existing pool metric assertions (pool_size, overflow, total)

### Config validation (Phase 44)
- `agent-brain-cli/agent_brain_cli/config_schema.py` — Schema validation engine; must add pool_timeout as valid key

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `QueryService.execute_query()` with `retrieval_mode` parameter — can be called directly for benchmarking
- Rich library already used throughout CLI for tables and formatting
- `httpx` async client used by CLI — can drive benchmark requests against running server

### Established Patterns
- CLI uses Click + Rich for all commands
- Server exposes `/query` POST endpoint with `mode` field
- Config loaded from `.agent-brain/config.yaml` via `load_provider_settings()`

### Integration Points
- Benchmark script hits `/query` endpoint via HTTP (same as CLI `query` command)
- Pool config flows through `storage.factory.create_storage_backend()` → `PostgresConfig`
- Config schema in `config_schema.py` needs pool_timeout added to valid keys

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 45-performance-benchmarking*
*Context gathered: 2026-03-26*
