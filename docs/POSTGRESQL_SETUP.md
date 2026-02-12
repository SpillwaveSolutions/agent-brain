# PostgreSQL + pgvector Setup (Docker Compose)

This guide explains how to run a local PostgreSQL instance with pgvector for the Agent Brain PostgreSQL backend.

## Requirements

- Docker Desktop with Docker Compose v2
- The provided pgvector Compose template
- Agent Brain configured with `storage.backend: "postgres"`

## Template Location

The repository includes a ready-to-run template:

```
agent-brain-plugin/templates/docker-compose.postgres.yml
```

Copy it into your project root (recommended so `docker compose` finds it):

```bash
cp agent-brain-plugin/templates/docker-compose.postgres.yml ./docker-compose.postgres.yml
```

## Environment Variables

The template supports these optional overrides:

- `POSTGRES_PASSWORD` (default: `agent_brain_dev`)
- `POSTGRES_PORT` (default: `5432`)

Example:

```bash
export POSTGRES_PASSWORD="supersecret"
export POSTGRES_PORT="5432"
```

## Start PostgreSQL

```bash
docker compose -f docker-compose.postgres.yml up -d
```

## Readiness Checks

Confirm the container is healthy:

```bash
docker compose -f docker-compose.postgres.yml ps
```

Check readiness inside the container:

```bash
docker compose -f docker-compose.postgres.yml exec postgres \
  pg_isready -U agent_brain -d agent_brain
```

## pgvector Requirement

Agent Brain requires the pgvector extension. The template uses the
`pgvector/pgvector:pg16` image so the extension is available.

If you use a different PostgreSQL image, ensure `pgvector` is installed,
or schema creation will fail with `extension "vector" does not exist`.

## Configure Agent Brain

After PostgreSQL is running, configure the storage backend and connection
settings in `config.yaml`. See `docs/CONFIGURATION.md` for the full schema
and `DATABASE_URL` override behavior.

## Important: No Auto-Migration

Agent Brain does not auto-migrate data between backends. If you switch
from ChromaDB to PostgreSQL (or vice versa), you must re-index your
documents after the change.

## Next Steps

- Update `storage.backend` and `storage.postgres` in `config.yaml`
- Restart the Agent Brain server
- Run `agent-brain reset --yes` and re-index your documents
