# Storage Layer

The fictional storage layer lives behind `StorageBackendProtocol`. Both
the Chroma backend and the Postgres backend implement it, and the active
one is selected via `AGENT_BRAIN_STORAGE_BACKEND`.

## Backends

- `ChromaBackend` — embedded vector store, default.
- `PostgresBackend` — pgvector + JSONB metadata, opt-in.

Both are tested via the parameterized contract tests in
`agent-brain-server/tests/contract/`.
