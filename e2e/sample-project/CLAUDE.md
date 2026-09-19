# Inventory service

Sample project for Agent Brain integration tests. Small on purpose.

## Rules for agents

- Search this project with Agent Brain before you read files by hand:
  `agent-brain query "<question>"`. Use `--mode bm25` for exact symbol names.
- The service layer owns all business rules. Do not put rules in `api.py`.
- Run tests with `python -m pytest tests/` from this folder.

## Layout

- `src/inventory/` is the package. Layers: `api.py` calls `service.py` calls
  `repository.py`.
- `docs/architecture.md` explains the layers.
- `docs/runbook.md` explains start, stop, and reset.
- `docs/adr/` holds decisions.
