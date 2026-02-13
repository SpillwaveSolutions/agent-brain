# Phase 08: Plugin & Documentation - Research

**Researched:** 2026-02-12
**Domain:** Claude Code plugin updates for storage backend configuration and documentation (ChromaDB vs PostgreSQL)
**Confidence:** MEDIUM

## User Constraints

No CONTEXT.md found. No locked decisions or out-of-scope items provided.

## Summary

Phase 08 is a plugin and docs update that adds PostgreSQL backend selection, configuration, and troubleshooting to the Claude Code plugin flow. The storage backend selection already exists in the server as config-driven behavior: environment variable override, then YAML config, then default to ChromaDB. The plugin must surface that choice in `/agent-brain-config`, write the `storage.backend` and `storage.postgres` configuration block, and expose Docker Compose for a local pgvector-backed PostgreSQL setup. The setup assistant should recognize PostgreSQL-specific errors like connection failures, pgvector extension missing, and pool exhaustion.

The codebase already includes a `PostgresConfig` with explicit defaults (host, port, pool sizing, HNSW params) and a `PostgresSchemaManager` that attempts to `CREATE EXTENSION vector`, so plugin docs should clearly call out the pgvector dependency. The repository also ships a `docker-compose.postgres.yml` template using `pgvector/pgvector:pg16`, which should be used as the recommended local dev path. Documentation needs to cover backend selection and a focused tradeoff comparison: ChromaDB for zero-ops local persistence and PostgreSQL for larger datasets, stronger operational tooling, and pgvector index tuning.

**Primary recommendation:** Update plugin flows and docs to align with the existing storage backend resolution order (env override, YAML config, default ChromaDB) and standardize the PostgreSQL setup around the provided Docker Compose template.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| ChromaDB | ^0.5.0 | Default vector store | Current server dependency and default backend | 
| PostgreSQL + pgvector | Postgres 16, pgvector extension | Optional persistent vector store | Backend implementation uses pgvector HNSW indexes | 
| SQLAlchemy (asyncio) | ^2.0.0 | Async DB engine and pooling | Postgres backend is built on async SQLAlchemy | 
| asyncpg | ^0.29.0 | Postgres driver | SQLAlchemy async driver for PostgreSQL | 

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Docker Compose | v2 | Local Postgres + pgvector | Recommended local dev setup | 

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pgvector in Postgres | ChromaDB only | ChromaDB is simpler locally, but lacks SQL tooling and Postgres ops ecosystem | 

**Installation:**
```bash
# Local dev Postgres with pgvector
docker compose -f docker-compose.postgres.yml up -d
```

## Architecture Patterns

### Recommended Project Structure
```
agent-brain-plugin/
├── commands/              # Claude Code commands (e.g., /agent-brain-config)
├── agents/                # Assistants (setup/search/research)
├── skills/                # Skills and reference docs
└── templates/             # Docker Compose templates
```

### Pattern 1: Config-Driven Backend Selection
**What:** Server resolves storage backend from env var, then YAML config, then default.
**When to use:** Always; plugin should mirror the same logic in docs and prompts.
**Example:**
```python
# Source: agent-brain-server/agent_brain_server/storage/factory.py
env_backend = settings.AGENT_BRAIN_STORAGE_BACKEND
if env_backend:
    return env_backend.lower()
provider_settings = load_provider_settings()
return provider_settings.storage.backend
```

### Pattern 2: PostgreSQL Connection Configuration via YAML + DATABASE_URL Override
**What:** PostgreSQL parameters are loaded from `storage.postgres` in config.yaml, with `DATABASE_URL` overriding only the connection string.
**When to use:** When backend is `postgres`, prefer YAML for pool sizing and tuning, optionally override host/user/password via `DATABASE_URL`.
**Example:**
```python
# Source: agent-brain-server/agent_brain_server/storage/factory.py
postgres_dict = dict(provider_settings.storage.postgres)
database_url = os.getenv("DATABASE_URL")
if database_url:
    config = PostgresConfig.from_database_url(database_url)
else:
    config = PostgresConfig(**postgres_dict)
```

### Pattern 3: Schema Creation Requires pgvector Extension
**What:** PostgreSQL schema creation runs `CREATE EXTENSION IF NOT EXISTS vector`.
**When to use:** Always for Postgres backend; doc must stress pgvector install.
**Example:**
```python
# Source: agent-brain-server/agent_brain_server/storage/postgres/schema.py
await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
```

### Anti-Patterns to Avoid
- **Storing storage backend config only in CLI env:** Server prioritizes YAML config, so plugin docs should guide users to `config.yaml` with the `storage` section.
- **Custom Postgres init scripts:** Use the provided Docker Compose template instead of hand-rolled scripts.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Postgres startup for local dev | Custom shell scripts | `docker-compose.postgres.yml` | Already in repo, includes pgvector image and healthcheck |
| Connection pooling | Custom pooling layer | SQLAlchemy async engine + pool settings | Existing backend relies on SQLAlchemy pool | 
| Vector indexing | Custom index management | pgvector HNSW indexes | Built into schema creation and tuned via config | 

**Key insight:** The server already owns backend selection and schema creation. Plugin and docs should only surface configuration and setup, not reimplement storage behavior.

## Common Pitfalls

### Pitfall 1: Postgres backend selected without config
**What goes wrong:** Storage backend set to `postgres`, but `storage.postgres` is missing and `DATABASE_URL` not set.
**Why it happens:** Plugin config flow does not collect storage parameters yet.
**How to avoid:** Ensure `/agent-brain-config` writes `storage.backend` and `storage.postgres` with required fields.
**Warning signs:** Validation warnings: missing `storage.postgres` or missing `host` field.

### Pitfall 2: pgvector extension missing
**What goes wrong:** Schema creation fails because `CREATE EXTENSION vector` cannot run.
**Why it happens:** PostgreSQL image without pgvector or extension not installed.
**How to avoid:** Use `pgvector/pgvector` Docker image or install pgvector on the server.
**Warning signs:** Errors like `extension "vector" does not exist` or `could not open extension control file`.

### Pitfall 3: Connection refused during setup
**What goes wrong:** Connection retries fail when Postgres is not running or port is wrong.
**Why it happens:** Docker compose not started or wrong host/port in config.
**How to avoid:** Detect Docker and offer to start Compose; validate host/port with `pg_isready`.
**Warning signs:** `connection refused`, `could not connect to server`, or repeated retry warnings.

### Pitfall 4: Pool exhaustion under load
**What goes wrong:** Requests fail with pool timeout/overflow errors.
**Why it happens:** Pool size too small for indexing workloads.
**How to avoid:** Increase `pool_size` and `pool_max_overflow` in `storage.postgres`.
**Warning signs:** Errors referencing `QueuePool` limit or "too many connections" in Postgres.

### Pitfall 5: Embedding dimension mismatch
**What goes wrong:** Postgres backend refuses to start if stored dimensions do not match current embedding model.
**Why it happens:** Switching embedding models without resetting storage.
**How to avoid:** Document the need to run `agent-brain reset --yes` after changing embedding dimensions.
**Warning signs:** StorageError mentioning "Embedding dimension mismatch".

## Code Examples

Verified patterns from repository sources:

### YAML storage backend configuration
```yaml
# Source: agent-brain-server/agent_brain_server/config/provider_config.py
storage:
  backend: "postgres"  # or "chroma"
  postgres:
    host: "localhost"
    port: 5432
    database: "agent_brain"
    user: "agent_brain"
    password: "agent_brain_dev"
    pool_size: 10
    pool_max_overflow: 10
    language: "english"
    hnsw_m: 16
    hnsw_ef_construction: 64
    debug: false
```

### Docker Compose for local Postgres with pgvector
```yaml
# Source: agent-brain-plugin/templates/docker-compose.postgres.yml
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: agent_brain
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-agent_brain_dev}
      POSTGRES_DB: agent_brain
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| ChromaDB-only default | Configurable backend (ChromaDB or PostgreSQL) | Implemented in storage factory | Enables pgvector-backed storage for larger deployments |

**Deprecated/outdated:**
- Single-backend assumptions in plugin docs. Storage backend is now configurable and must be documented as such.

## Open Questions

1. **Exact PostgreSQL error strings to match in setup assistant**
   - What we know: Common failures include connection refused, missing pgvector extension, and pool exhaustion.
   - What is unclear: Which exact error messages surface in this repo's logs for those cases.
   - Recommendation: Collect a few real error logs from tests or manual runs and codify matches.

## Sources

### Primary (HIGH confidence)
- `agent-brain-server/agent_brain_server/storage/factory.py` - backend selection and DATABASE_URL override
- `agent-brain-server/agent_brain_server/storage/postgres/config.py` - PostgresConfig fields and defaults
- `agent-brain-server/agent_brain_server/storage/postgres/schema.py` - pgvector extension creation
- `agent-brain-plugin/templates/docker-compose.postgres.yml` - Docker Compose template for pgvector
- `agent-brain-plugin/commands/agent-brain-config.md` - config flow and config file priority

### Secondary (MEDIUM confidence)
- https://github.com/pgvector/pgvector - pgvector extension behavior and HNSW index tradeoffs
- https://docs.trychroma.com/llms.txt - Chroma documentation index

### Tertiary (LOW confidence)
- Error pattern suggestions for pool exhaustion and pgvector missing; needs validation with actual logs.

## Metadata

**Confidence breakdown:**
- Standard stack: MEDIUM - versions verified in `agent-brain-server/pyproject.toml`, pgvector details from official repo
- Architecture: HIGH - derived from server storage factory and config models
- Pitfalls: MEDIUM - code-backed for config errors, error strings need validation

**Research date:** 2026-02-12
**Valid until:** 2026-03-14
