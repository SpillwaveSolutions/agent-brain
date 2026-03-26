---
phase: 45-performance-benchmarking
plan: "01"
subsystem: cli-config-validation
tags: [config-schema, postgres, validation, docs]
dependency_graph:
  requires: []
  provides: [nested-postgres-key-validation, pool-timeout-docs]
  affects: [agent-brain-cli/config_schema.py, agent-brain-cli/tests/test_config_validate.py]
tech_stack:
  added: []
  patterns: [allowlist-validation, nested-section-validation, type-checking]
key_files:
  created: []
  modified:
    - agent-brain-cli/agent_brain_cli/config_schema.py
    - agent-brain-cli/tests/test_config_validate.py
    - docs/POSTGRESQL_SETUP.md
    - docs/CONFIGURATION.md
decisions:
  - "Added POSTGRES_KNOWN_FIELDS allowlist with 12 keys matching PostgresConfig Pydantic model"
  - "Added POSTGRES_TYPE_FIELDS for type-checked sub-keys (port, pool_size, pool_max_overflow, pool_timeout, hnsw_m, hnsw_ef_construction, debug)"
  - "Inserted nested validation as step 2d in validate_config_dict — after per-section loop, before deprecated keys check"
  - "Added 6 tests covering: valid full config, unknown key rejection, pool_timeout accepted, pool_timeout type error, all 12 known keys accepted, typo detection"
  - "Documented pool_timeout in POSTGRESQL_SETUP.md pool settings table and CONFIGURATION.md PostgreSQL key reference table"
metrics:
  duration: "~10 minutes"
  completed: "2026-03-26T21:57:26Z"
  tasks_completed: 2
  files_changed: 4
requirements: [PERF-02]
---

# Phase 45 Plan 01: Nested storage.postgres.* Config Validation + pool_timeout Docs Summary

**One-liner:** Nested `storage.postgres.*` key validation with 12-field allowlist and type-checking, plus `pool_timeout` documented in PostgreSQL setup and configuration reference docs.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add nested storage.postgres.* key validation to config_schema.py | 0a4aea8 | agent-brain-cli/agent_brain_cli/config_schema.py |
| 2 | Add nested postgres validation tests + update pool_timeout docs | bcf2f79 | agent-brain-cli/tests/test_config_validate.py, docs/POSTGRESQL_SETUP.md, docs/CONFIGURATION.md |

## What Was Built

### Task 1: Nested postgres key validation (config_schema.py)

Added two new module-level constants:

- `POSTGRES_KNOWN_FIELDS`: set of 12 keys matching the server-side `PostgresConfig` Pydantic model (`host`, `port`, `database`, `user`, `password`, `pool_size`, `pool_max_overflow`, `pool_timeout`, `language`, `hnsw_m`, `hnsw_ef_construction`, `debug`)
- `POSTGRES_TYPE_FIELDS`: dict mapping 7 sub-keys to their expected Python types and error messages

Added step 2d in `validate_config_dict` (between per-section loop and deprecated keys check):
- Iterates over `storage.postgres.*` keys, rejects unknowns with `storage.postgres.<key>` field paths and sorted known-fields suggestion
- Type-validates all numeric/bool postgres sub-keys

### Task 2: Tests and docs

Added `TestNestedPostgresValidation` class with 6 test methods:
1. `test_valid_postgres_config_no_errors` — all 12 known keys produce no errors
2. `test_unknown_postgres_key_returns_error` — bad_key produces error with correct field path
3. `test_pool_timeout_accepted` — integer pool_timeout: 45 produces no errors
4. `test_pool_timeout_wrong_type_returns_error` — string "thirty" produces type error
5. `test_all_known_postgres_keys_accepted` — all 12 keys asserted against POSTGRES_KNOWN_FIELDS
6. `test_typo_in_postgres_key_is_caught` — pool_timeot typo produces error with exact field path

Updated `docs/POSTGRESQL_SETUP.md`: added pool settings table with pool_size, pool_max_overflow, pool_timeout, and pool_timeout to the config YAML example.

Updated `docs/CONFIGURATION.md`: added complete 12-row key reference table for `storage.postgres.*` keys including pool_timeout.

## Verification

All checks passed:
- `poetry run pytest tests/test_config_validate.py -v` — 24 passed (18 pre-existing + 6 new)
- `poetry run ruff check agent_brain_cli/config_schema.py` — no issues
- `poetry run mypy agent_brain_cli/config_schema.py` — no issues
- `grep POSTGRES_KNOWN_FIELDS agent_brain_cli/config_schema.py` — found
- `grep pool_timeout docs/POSTGRESQL_SETUP.md` — found
- `grep pool_timeout docs/CONFIGURATION.md` — found

## Decisions Made

1. **Allowlist approach for nested validation:** Added `POSTGRES_KNOWN_FIELDS` as a `set` to mirror `STORAGE_KNOWN_FIELDS` / `EMBEDDING_KNOWN_FIELDS` pattern already used in the file — no architectural changes required.
2. **Step 2d placement:** Nested validation placed after per-section loop (step 2) and before deprecated keys check (step 3) — keeps storage-related checks grouped together.
3. **Separate POSTGRES_TYPE_FIELDS dict:** Kept type-checking data separate from the known-fields set to allow independent expansion without touching the allowlist.
4. **6 tests vs minimum 5:** Added `test_typo_in_postgres_key_is_caught` as a 6th test to explicitly verify the pool_timeot typo scenario from the plan's success criteria.
5. **pool_timeout table in docs:** Added a complete pool settings table to POSTGRESQL_SETUP.md (not just inline text) to match the CONFIGURATION.md table format and make it scannable.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

- [x] `agent-brain-cli/agent_brain_cli/config_schema.py` — verified POSTGRES_KNOWN_FIELDS present
- [x] `agent-brain-cli/tests/test_config_validate.py` — verified TestNestedPostgresValidation class present
- [x] `docs/POSTGRESQL_SETUP.md` — verified pool_timeout present
- [x] `docs/CONFIGURATION.md` — verified pool_timeout present
- [x] Commit 0a4aea8 exists (Task 1)
- [x] Commit bcf2f79 exists (Task 2)

## Self-Check: PASSED
