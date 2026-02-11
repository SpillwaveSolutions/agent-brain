# Phase 6: PostgreSQL Backend Implementation - Context

**Gathered:** 2026-02-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement PostgreSQL as an alternative storage backend behind the StorageBackendProtocol (Phase 5). Includes pgvector for vector search, tsvector for full-text search, async connection pooling, Docker Compose template, and auto-schema creation. The plugin wizard (Phase 8) handles user-facing setup flows; this phase builds the backend and infrastructure it will use.

</domain>

<decisions>
## Implementation Decisions

### Docker & local setup
- Docker Compose only (no native PostgreSQL install documentation in this phase)
- PostgreSQL 16 + pgvector 0.7+ as the target versions
- Minimal compose: just PostgreSQL + pgvector container (pgAdmin is optional, offered by Phase 8 wizard)
- Port allocation: scan for available ports (reuse existing auto-port pattern), configure in `.env.agent-brain` (fallback to `.env`)
- Data persistence via named Docker volume (survives `docker compose down`, only lost with `-v`)
- Docker Compose template lives in both server package (reference copy) and plugin package (deployable template)
- Per-project deployment: Phase 8 wizard generates docker-compose.yml into `.claude/agent-brain/` state directory
- Server does NOT manage Docker lifecycle — just connects to configured host:port. Docker management is Phase 8 plugin territory.

### Connection & pooling
- Connection config: YAML fields as primary (storage.postgres.host, port, database, user, password), DATABASE_URL env var as override
- Startup behavior: retry with exponential backoff (3-5 attempts) before failing — handles Docker containers still initializing
- Pool sizing: sensible defaults (10 connections, max 20), configurable via YAML (storage.postgres.pool_size, storage.postgres.pool_max)
- Health endpoint: dedicated `/health/postgres` endpoint with pool metrics (active, idle, size) — separate from main `/health/status`

### Schema & migrations
- Embedded SQL in Python code — schema as SQL strings in PostgresBackend class, auto-creates tables on first connection
- Vector column dimension: dynamic from embedding provider config at startup. Validated on subsequent startups (mismatch = fail fast)
- Full-text search: single combined tsvector column with setweight() for relevance boosting across content fields
- No Alembic — if schema changes, user drops and recreates (acceptable for v1)

### Claude's Discretion
- Schema version tracking strategy (simple meta table vs. no tracking)
- Exact retry backoff timing and attempt count
- HNSW index parameter defaults (m, ef_construction)
- Table naming conventions
- Connection string parsing implementation
- Exact Docker Compose health check configuration

</decisions>

<specifics>
## Specific Ideas

- Reuse the existing auto-port allocation pattern from multi-instance architecture (Feature 109) for PostgreSQL port scanning
- `.env.agent-brain` is the preferred config file, `.env` as fallback — consistent with existing conventions
- The plugin (Phase 8) acts as a setup wizard that walks users through Docker Compose and PostgreSQL configuration
- Plugin and server both ship the docker-compose.yml template — plugin for deployment, server for reference/testing

</specifics>

<deferred>
## Deferred Ideas

- pgAdmin as optional Docker Compose add-on — Phase 8 setup wizard can offer this
- Native PostgreSQL installation documentation — out of scope, Docker-only for Phase 6
- GraphRAG on PostgreSQL — stays ChromaDB-only for now, future milestone
- Alembic schema migrations — if needed later, separate phase
- Auto-detect Docker availability from server — Phase 8 plugin wizard territory

</deferred>

---

*Phase: 06-postgresql-backend*
*Context gathered: 2026-02-11*
