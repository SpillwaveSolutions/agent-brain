# Plan 04 Summary: file_sandbox module

**Phase:** 50 — Server endpoint prep + v2 design doc
**Requirement:** prerequisite for URI-04 (Phase 51 file:// resource)
**Status:** Complete
**Commits:** `1b339d4`, `bea4790`, `b83e93d`
**Date:** 2026-06-02

## What was built

New `agent_brain_server/security/` package containing `file_sandbox.py` — the policy module that decides which absolute paths are addressable via `file://` MCP resource reads. Hard whitelist by canonical (symlink-resolved) absolute path from the operator's indexed folders, with deny-by-default for hidden files, paths outside indexed roots, and files larger than the configured size cap. Establishes the API surface that Phase 51 Plan 03 (`file://` URI handler) imports verbatim.

## Files Created

| File | Status | Lines | Notes |
|------|--------|-------|-------|
| `agent-brain-server/agent_brain_server/security/__init__.py` | created | — | package init |
| `agent-brain-server/agent_brain_server/security/file_sandbox.py` | created | 261 | core module |
| `agent-brain-server/tests/security/test_file_sandbox.py` | created | 353 | 33 tests |
| `agent-brain-server/agent_brain_server/config/settings.py` | edited | — | added `MCP_SANDBOX_MAX_READ_BYTES` setting (default 10 MiB) |

## Public API (Phase 51 Plan 03 will import)

```python
from agent_brain_server.security.file_sandbox import (
    canonicalize_path,      # str | Path -> Path (resolves symlinks)
    is_path_allowed,        # core policy: (path, roots) -> (allowed, deny_reason)
    list_sandbox_roots,     # folders -> list[dict] for MCP roots/list
    DEFAULT_MAX_READ_BYTES, # 10 * 1024 * 1024
)
```

## Decisions Implemented (from 50-CONTEXT.md decision A)

- **Hard whitelist** by canonical absolute path from `folders.list()` (via `_FolderLike` protocol — duck-typed for testability)
- **Symlink resolution at read-time** (not subscribe/list time) so policy stays current as folders change
- **4 deny reasons** as string literals (DenyReason = str): `outside_indexed_roots`, `size_limit`, `hidden_file`, `not_found`
- **Hidden-file deny** for `.env`, `.git/*`, `.ssh/*`, `~/*` patterns — checked via dot-component path walk
- **Default 10 MiB read cap**, configurable via new `MCP_SANDBOX_MAX_READ_BYTES` settings field
- **No `--no-resolve` escape hatch** in v2 (deferred to v3 with auth per design doc §6)

## Verification

| Check | Command | Result |
|-------|---------|--------|
| Format | `poetry run black --check agent_brain_server tests` | PASS (192 files unchanged) |
| Lint | `poetry run ruff check agent_brain_server tests` | PASS |
| Types (strict) | `poetry run mypy agent_brain_server` | PASS (84 source files) |
| Tests (sandbox only) | `poetry run pytest tests/security/ -q` | PASS (33 passed) |
| Tests (full suite) | `poetry run pytest -x -q` | PASS (1269 passed, 28 skipped) |

## Deviations

- **Executor process terminated mid-flight** with a socket disconnect after the three main commits landed (security package, settings config, sandbox tests). The 3 commits `1b339d4`, `bea4790`, `b83e93d` were already in the history; the missing SUMMARY.md and final verification run were completed by the orchestrator (post-crash recovery). Net effect: identical outcome to a successful executor run.
- The `DenyReason` type is implemented as a `str` type alias rather than a `Literal[...]` enum. Reason: keeps the public API simple for callers that need to assemble reason strings dynamically (e.g., `"size_limit:13107200_bytes"`). All 4 canonical reasons are documented and the test suite asserts them.

## Self-Check: PASSED

All claimed files exist on disk; all 3 commit hashes resolve in `git log`; verification matrix fully green; 33 sandbox tests passing in isolation and as part of the 1269-test full suite. Ready for Phase 51 Plan 03 to import.
