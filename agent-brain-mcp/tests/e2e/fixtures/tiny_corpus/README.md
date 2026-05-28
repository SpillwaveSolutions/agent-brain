# Tiny Corpus — E2E Fixture

This is a deliberately small corpus consumed by Phase 4 E2E tests in
`agent-brain-mcp/tests/e2e/`. ~5 markdown + ~3 python files so indexing
completes in a few seconds.

## Contents

- `README.md` (this file)
- `docs/auth.md` — describes a fictional auth flow
- `docs/storage.md` — describes a fictional storage layer
- `src/query_service.py` — fictional retrieval service
- `src/auth.py` — fictional auth helper

## Purpose

E2E tests query against this corpus to verify end-to-end behavior:

- `search_documents` for `"auth"` should return chunks from `docs/auth.md`
- `find-callers` for `QueryService` should return the call in `src/auth.py`
- `onboard-to-codebase` should list this README and the docs/ folder
