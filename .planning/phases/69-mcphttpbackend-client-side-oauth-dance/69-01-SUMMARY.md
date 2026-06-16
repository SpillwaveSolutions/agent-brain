---
phase: 69-mcphttpbackend-client-side-oauth-dance
plan: "01"
subsystem: agent-brain-mcp / oauth
tags: [oauth, token-storage, security, file-permissions, tdd]
dependency_graph:
  requires: []
  provides: [FileTokenStorage, agent_brain_mcp.oauth.token_storage]
  affects: [agent-brain-mcp/agent_brain_mcp/oauth]
tech_stack:
  added: []
  patterns: [TokenStorage Protocol (SDK), model_dump/model_validate (Pydantic), os.chmod 0o600 idiom]
key_files:
  created:
    - agent-brain-mcp/agent_brain_mcp/oauth/token_storage.py
    - agent-brain-mcp/tests/test_oauth_file_token_storage.py
  modified:
    - agent-brain-mcp/agent_brain_mcp/oauth/__init__.py
decisions:
  - "FileTokenStorage wraps sync file I/O in async def methods (no asyncio) — matches Pattern A subprocess lifetime; file is tiny"
  - "_read_raw() / _write_raw() private helpers mirror write_mcp_runtime idiom from agent_brain_cli/mcp_runtime.py"
  - "os.chmod(path, 0o600) called on every write unconditionally — mandatory security gate (design-doc Probe 6)"
  - "Corrupt/absent file degrades gracefully to empty dict; model_validate failures also warn + return None"
  - "Single JSON file holds both 'tokens' and 'client_info' keys; each setter preserves the other key"
metrics:
  duration: "22m"
  completed_date: "2026-06-16"
  tasks_completed: 2
  files_created: 2
  files_modified: 1
requirements: [OAUTH-07]
---

# Phase 69 Plan 01: FileTokenStorage — 0o600 Client-Side OAuth Persistence Summary

**One-liner:** FileTokenStorage implementing the SDK TokenStorage 4-method Protocol persisting OAuthToken + OAuthClientInformationFull in a single 0o600 JSON file at state_dir/mcp-oauth-tokens.json.

## What Was Built

`agent_brain_mcp/oauth/token_storage.py` — a client-side persistence layer for the Pattern A OAuth dance. The class implements the SDK `mcp.client.auth.oauth2.TokenStorage` Protocol exactly (four async methods: `get_tokens`, `set_tokens`, `get_client_info`, `set_client_info`). Both the access/refresh token pair and the Dynamic Client Registration result are persisted in one file, preventing re-registration on every Pattern A (fresh subprocess per CLI call) invocation.

Security gate: `os.chmod(path, 0o600)` is called unconditionally after every write. The test suite asserts `(st_mode & 0o077) == 0` after both `set_tokens` and `set_client_info`.

Corruption/absence are handled gracefully: `_read_raw()` returns `{}` on any `OSError`, `json.JSONDecodeError`, `ValueError`, or missing file — logging a WARNING at module logger level. This ensures a corrupt token file never crashes Pattern A; it just re-triggers the browser dance.

## Tasks Completed

| # | Task | Commit | Key Files |
|---|------|--------|-----------|
| 1a | TDD RED: Write failing tests | c1a2130 | agent-brain-mcp/tests/test_oauth_file_token_storage.py |
| 1b | TDD GREEN: Implement FileTokenStorage | 34224d3 | agent-brain-mcp/agent_brain_mcp/oauth/token_storage.py, oauth/__init__.py |
| 1c | Fix: Black + Ruff formatting | 500df1a | agent-brain-mcp/tests/test_oauth_file_token_storage.py |
| 2 | Quality gate: task before-push exits 0 | (verified) | repo-wide |

## Decisions Made

1. **Sync I/O wrapped in async def** — The TokenStorage Protocol requires `async def` but the file is tiny and Pattern A is subprocess-scoped. No `asyncio` overhead needed; plain sync file I/O inside `async def` bodies.
2. **Single-file JSON with two top-level keys** — `{"tokens": {...}, "client_info": {...}}`. Each setter reads-before-writing to preserve the other key. This is the design-doc specified shape.
3. **Private helper split** — `_read_raw()` for corruption-tolerant reads, `_write_raw()` for mkdir+write+chmod. Mirrors the `write_mcp_runtime` idiom from `agent_brain_cli/mcp_runtime.py`.
4. **chmod on every write** — called after `write_text` (not before) to ensure the permission is set regardless of whether the file was newly created or overwritten.
5. **`model_validate` for deserialization** — catches Pydantic `ValidationError` (subclass of `ValueError`) in the same try/except block as the JSON parse errors.

## Test Coverage

11 tests in `test_oauth_file_token_storage.py`:
- `test_set_get_tokens_round_trip` — all 5 OAuthToken fields preserved exactly
- `test_set_get_client_info_round_trip` — client_id and redirect_uris preserved
- `test_tokens_and_client_info_coexist` — set_tokens doesn't erase client_info and vice versa; both readable after interleaved writes
- `test_token_file_not_group_world_readable_after_set_tokens` — `(st_mode & 0o077) == 0`
- `test_token_file_not_group_world_readable_after_set_client_info` — same assertion for client_info path
- `test_get_tokens_returns_none_when_file_absent` — cold start returns None (no crash)
- `test_get_client_info_returns_none_when_file_absent` — same for client_info
- `test_get_tokens_on_corrupt_file_returns_none_and_logs_warning` — corrupt JSON → None + WARNING
- `test_get_client_info_on_corrupt_file_returns_none_and_logs_warning` — same for client_info
- `test_get_tokens_returns_none_when_only_client_info_in_file` — absent key → None
- `test_get_client_info_returns_none_when_only_tokens_in_file` — absent key → None

## Quality Gate

`task before-push` run from repo root: **EXIT_CODE=0**
- Black: 0 files reformatted (after formatting fix)
- Ruff: all checks passed (after --fix for I001 import order)
- mypy (MCP): 0 issues
- pytest (MCP): 939 passed, 111 deselected, 7 warnings (includes all new 11 tests)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing validation] Black and Ruff formatting failures on test file**
- **Found during:** Task 2 (quality gate)
- **Issue:** Black reformatted one test file; Ruff found 5 I001 import-order issues in function-local imports and 1 E501 line-too-long (89 chars) in module docstring
- **Fix:** Applied `black` auto-format, `ruff check --fix` for I001, manually shortened the 89-char docstring line to 88
- **Files modified:** agent-brain-mcp/tests/test_oauth_file_token_storage.py
- **Commit:** 500df1a

## Self-Check: PASSED

Files exist:
- agent-brain-mcp/agent_brain_mcp/oauth/token_storage.py: FOUND
- agent-brain-mcp/tests/test_oauth_file_token_storage.py: FOUND

Commits exist:
- c1a2130 (TDD RED): FOUND
- 34224d3 (TDD GREEN): FOUND
- 500df1a (formatting fix): FOUND

Quality gate: task before-push exits 0 — VERIFIED
