---
phase: 51-uri-schemes-templates
plan: 03
subsystem: mcp
tags: [mcp, uri-schemes, file-uri, sandbox, filesystem-read, phase-50-consumer, share-dont-fork]

# Dependency graph
requires:
  - phase: 50-server-endpoint-prep-v2-design-doc
    provides: "agent_brain_server.security.file_sandbox module (canonicalize_path, is_path_allowed, list_sandbox_roots, DEFAULT_MAX_READ_BYTES) — 4 deny reasons, 10 MiB cap, symlink-escape detection"
  - phase: 51-uri-schemes-templates
    provides: "Plan 01 parameterized URI dispatcher infrastructure (ParsedURI dataclass, PARAMETERIZED_HANDLERS registry, scheme-prefix routing in read_resource, McpError data refinement pattern)"
provides:
  - "file://<abs-path> MCP resource → raw filesystem bytes/text via the parameterized dispatcher (URI-04)"
  - "agent_brain_mcp.security re-export shim — single source of truth for path policy SHARED with the server (no fork)"
  - "Dual-return handler signature: parameterized handlers can return str (wrapped as application/json) OR ReadResourceContents (used verbatim, per-file mime_type + bytes for binary blobs)"
  - "FileSandboxScenario fixture + make_file_sandbox_httpx_client helper — composable filesystem-sandbox test infrastructure for future plans"
affects:
  - "52-resource-subscriptions (SUB-04 file:// change watcher could reuse the same sandbox helper)"
  - "53-streamable-http-transport (file:// reads must continue to work over HTTP transport; same handler covers both)"
  - "55-validation-contract-tests-qa-gate (contract tests can pin the four Phase 50 deny reasons via wire-shape assertions)"

# Tech tracking
tech-stack:
  added: []  # no new dependencies — used stdlib mimetypes, base64, pathlib + Phase 50's helper
  patterns:
    - "Re-export shim discipline: agent_brain_mcp/security/__init__.py contains zero logic, docstring explicitly forbids it — keeps server module the single source of truth for path policy"
    - "Dispatcher dual-return convention: str → SDK-wrap as application/json; ReadResourceContents → use verbatim — minimal-surface change so JSON schemes don't need to construct wire types"
    - "Sandbox refresh on every read: NO cache on list_folders(); a regression test asserts two consecutive resources/read calls trigger TWO GET /index/folders/ requests"

key-files:
  created:
    - "agent-brain-mcp/agent_brain_mcp/security/__init__.py — 55-line re-export shim of Phase 50 file_sandbox helpers"
    - "agent-brain-mcp/tests/test_resources_read_file.py — 352 lines, 17 tests covering parse_uri + e2e file:// + every Phase 50 deny rule"
  modified:
    - "agent-brain-mcp/agent_brain_mcp/server.py — read_resource dispatcher now accepts ReadResourceContents from handlers (12 lines added)"
    - "agent-brain-mcp/agent_brain_mcp/resources/parameterized.py — _handle_file_uri function (~150 LOC); file:// parser tightened to reject two-slash form; PARAMETERIZED_HANDLERS[file] swapped off NotImplementedError placeholder; ParameterizedHandler type widened to str | ReadResourceContents"
    - "agent-brain-mcp/tests/conftest.py — FileSandboxScenario dataclass + tmp_path_with_indexed_root fixture + make_file_sandbox_httpx_client helper (~200 LOC)"
    - "agent-brain-mcp/tests/test_resources_read_parameterized.py — TestPlaceholderHandlers reduced to a documentation-only comment block (all 4 schemes now wired)"
    - "agent-brain-mcp/tests/test_smoke.py — [Rule 1 - Bug] Black 25.x line-wrap autofix (out-of-scope but blocks before-push)"

key-decisions:
  - "Re-export NOT fork: agent_brain_mcp.security is a pure pass-through of Phase 50's file_sandbox. Docstring forbids logic. Forking would create silent policy drift between server-side and MCP-side file:// reads (load-bearing security invariant from CONTEXT specifics #2)."
  - "Three-slash form is the only accepted file:// URI shape. file://host/path is rejected because urlsplit treats `host` as the authority, which could be exploited to smuggle relative paths past the sandbox. Forces an absolute path at the parse layer; the sandbox helper then canonicalizes."
  - "Dispatcher dual-return signature: handlers can return str (wrapped as application/json — the JSON-backed schemes) OR ReadResourceContents (used verbatim — file://, which needs per-file mime_type + optional bytes payload). Single isinstance check in server.py; no scheme-specific dispatcher rewiring."
  - "No cache on list_folders(): the load-bearing CONTEXT decision E. Stale roots would silently widen the sandbox after operator folder mutations. A roots-refresh regression test pins this — two consecutive reads MUST result in two HTTP calls."
  - "Pre-flight stat().st_size check as defense-in-depth: is_path_allowed already checks the size cap, but we re-check in the handler against DEFAULT_MAX_READ_BYTES so a future caller that bypasses the sandbox helper still gets a sane upper bound."
  - "MIME-typed text/binary dispatch via mimetypes.guess_type: text/* MIMEs decode UTF-8 → str content; anything else (or a UTF-8 decode failure on a mis-typed text file) returns bytes content, auto-base64-encoded as BlobResourceContents by the MCP SDK at the wire boundary. No aiofiles dependency added — kept the package footprint lean by sticking to asyncio.to_thread(Path.read_bytes)."

patterns-established:
  - "Re-export shim discipline: when a downstream package needs a helper from an upstream package, expose it through a thin `__init__.py` whose docstring explicitly forbids logic. Future readers reading the shim see immediately that the upstream module is the source of truth."
  - "Dual-return handler signature for parameterized dispatchers: most handlers return a stringly-typed payload (JSON, plain text) that the dispatcher wraps; one or two specialized handlers return the wire-level type directly so they can pick their own MIME / payload shape. Single isinstance check at the dispatch boundary."

requirements-completed: [URI-04]

# Metrics
duration: 30min
completed: 2026-06-03
---

# Phase 51 Plan 03: file:// with sandbox enforcement Summary

**`file://<abs-path>` is now an addressable MCP resource. Reads bytes off disk via the parameterized dispatcher after path canonicalization and a per-read sandbox check against Phase 50's `is_path_allowed` helper — SHARE-don't-fork: the policy module is re-exported, not duplicated, so server-side and MCP-side `file://` reads enforce one set of rules.**

## Performance

- **Duration:** 30 min
- **Started:** 2026-06-03T05:30:00Z
- **Completed:** 2026-06-03T06:00:00Z
- **Tasks:** 4 (security shim, file:// handler + dispatcher widening, conftest fixtures, e2e + parse_uri tests)
- **Files modified:** 5 (server.py, parameterized.py, conftest.py, test_resources_read_parameterized.py, test_smoke.py)
- **Files created:** 2 (security/__init__.py shim, test_resources_read_file.py)
- **Tests added:** 17 (6 parse_uri unit + 11 e2e resources/read)
- **Total test count after plan:** 124 (up from 108 at Plan 51-02 close, +17 from this plan; -1 placeholder test removed)

## Accomplishments

- **`file://<abs-path>` end-to-end:** MCP client → parse_uri (three-slash only) → handler refreshes roots from GET /index/folders/ → canonicalize_path → is_path_allowed → text/binary dispatch → ReadResourceContents wire response. Every Phase 50 deny reason is exercised by an e2e test.
- **Phase 50 deny-reason wire passthrough:** the four literals (`outside_indexed_roots`, `hidden_file`, `symlink_escape`, `size_limit`) flow into `McpError.data["reason"]` verbatim. MCP clients route on the literal without re-parsing cause strings.
- **SHARE-don't-fork enforced:** `agent_brain_mcp/security/__init__.py` is 55 lines of pure re-export with a docstring that explicitly forbids logic. The Phase 50 module remains the single source of truth for path policy. No code duplication, no drift surface.
- **Three-slash URI form enforced:** `file://relative/path` (which urlsplit reads as `authority=relative, path=/path`) is rejected at the parser layer. The only accepted shape is `file:///<abs-path>` (canonical form per RFC 3986 with empty authority). Forces an absolute path before the sandbox check.
- **Dispatcher dual-return contract documented:** server.py's parameterized dispatcher now accepts EITHER `str` (wrapped as `application/json` for the three JSON-backed schemes) OR `ReadResourceContents` (used verbatim for `file://`). Single `isinstance` check; the three JSON schemes don't need to construct wire types.
- **Sandbox refresh on every read regression-pinned:** the `test_read_file_uri_roots_refresh_on_each_read` test asserts that two consecutive `resources/read` calls result in TWO `GET /index/folders/` requests. Stale roots would silently widen the sandbox after operator folder mutations — CONTEXT decision E load-bearing.
- **Hidden-file inside-root allowance:** Phase 50's rule that dot-files INSIDE an indexed root are allowed (root policy wins) is exercised by `test_read_file_uri_hidden_file_inside_root_allowed`. The `hidden_file` deny only fires for dot-prefixed paths OUTSIDE every root.
- **Test infrastructure for future plans:** `FileSandboxScenario` dataclass + `tmp_path_with_indexed_root` fixture + `make_file_sandbox_httpx_client` helper are reusable for Phase 52 (file change watcher) and Phase 55 (contract tests).

## Task Commits

Each task was committed atomically:

1. **Security shim** — `8ea1460` (feat: re-export Phase 50 helpers under agent_brain_mcp.security)
2. **file:// handler + dispatcher widening** — `f284568` (feat: implement file:// handler with Phase 50 sandbox enforcement)
3. **Tests + smoke autofix** — `9093ed4` (test: cover file:// URI handler across all sandbox rules)
4. **Plan metadata** — _next commit_ (docs: complete plan 03; updates STATE.md, ROADMAP.md, REQUIREMENTS.md)

_Note: Task 3 (conftest fixtures) was included in commit `f284568` because the staging snapshot at commit time included the conftest changes — semantically the fixture infrastructure is tightly coupled to the handler implementation it supports._

## Files Created/Modified

### Created

- `agent-brain-mcp/agent_brain_mcp/security/__init__.py` — Re-export shim for Phase 50's `canonicalize_path`, `is_path_allowed`, `list_sandbox_roots`, `DEFAULT_MAX_READ_BYTES`. Docstring forbids logic.
- `agent-brain-mcp/tests/test_resources_read_file.py` — 17 tests: 6 `parse_uri` unit tests + 11 e2e `resources/read` tests covering text success, binary success, all four Phase 50 deny reasons, `..` traversal, hidden-inside-root allowance, AnyUrl normalization quirks, two-slash-form rejection at wire level, and the roots-refresh-on-each-read regression.
- `.planning/phases/51-uri-schemes-templates/plans/03-file-uri-with-sandbox-SUMMARY.md` — this file.

### Modified

- `agent-brain-mcp/agent_brain_mcp/server.py` — Dispatcher `isinstance(content, ReadResourceContents)` check. 12 LOC added.
- `agent-brain-mcp/agent_brain_mcp/resources/parameterized.py` — `_handle_file_uri` function (~150 LOC); `parse_uri` file:// branch tightened to reject any non-empty authority; `PARAMETERIZED_HANDLERS["file"]` swapped off `_handle_not_implemented`; `ParameterizedHandler` type alias widened to `str | ReadResourceContents`; module docstring updated.
- `agent-brain-mcp/tests/conftest.py` — `FileSandboxScenario` dataclass, `tmp_path_with_indexed_root` fixture, `make_file_sandbox_httpx_client` helper. ~200 LOC added.
- `agent-brain-mcp/tests/test_resources_read_parameterized.py` — `TestPlaceholderHandlers` class reduced to a documentation-only comment (all four schemes now have real handlers).
- `agent-brain-mcp/tests/test_smoke.py` — [Rule 1 - Bug] Black 25.x line-wrap autofix.

## Decisions Made

See `key-decisions` in frontmatter above. All six are load-bearing for the file:// security model and should be carried forward into Phase 52 (file change watcher) planning.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] tests/test_smoke.py Black 25.x line-wrap drift**
- **Found during:** Quality-gate run after Task 4 (writing tests)
- **Issue:** `tests/test_smoke.py` was committed in Plan 51-01's chore by a different Black version. Newer Black flagged a line-wrap style preference that would block `task before-push` exit 0.
- **Fix:** `poetry run black tests/test_smoke.py` — pure formatting change.
- **Files modified:** `agent-brain-mcp/tests/test_smoke.py`
- **Verification:** `poetry run black --check agent_brain_mcp tests` returns clean across all 50 files.
- **Committed in:** `9093ed4` (Task 4 commit, with rationale in commit body)

**2. [Rule 3 - Blocking] Dispatcher widening to accept ReadResourceContents**
- **Found during:** Task 2 (designing the `_handle_file_uri` return shape)
- **Issue:** The existing dispatcher in `server.py` hard-coded `application/json` for ALL parameterized handlers. The `file://` handler needs a per-file MIME (text/plain, application/octet-stream, etc.) and the ability to return bytes for binary blobs (so the MCP SDK can auto-base64-encode as `BlobResourceContents`).
- **Fix:** Added a single `isinstance(content, ReadResourceContents)` check in `server.py` so handlers can return EITHER `str` (wrapped) or `ReadResourceContents` (used verbatim). Non-breaking for Plans 01/02 — `str` returns still wrap as JSON.
- **Files modified:** `agent-brain-mcp/agent_brain_mcp/server.py`, `agent-brain-mcp/agent_brain_mcp/resources/parameterized.py` (widened `ParameterizedHandler` type alias).
- **Verification:** All 124 tests pass; Plan 01/02 JSON-scheme tests untouched.
- **Committed in:** `f284568`

**3. [Rule 1 - Bug] parse_uri file:// branch tightened to reject two-slash form**
- **Found during:** Task 2 (testing the parser smoke-test loop)
- **Issue:** The previous (Plan 51-01) parser accepted `file://relative/path` and returned `path=/path` because urlsplit puts `relative` in `netloc` and `/path` in `path`. The sandbox would later reject it as `outside_indexed_roots`, but at the parser layer this is silent acceptance of a non-canonical URI shape. The plan called this out explicitly as a security risk (a relative-path-smuggling vector).
- **Fix:** Reject any URI with a non-empty authority (`netloc`) AND require the path to start with `/`. Only the canonical three-slash form `file:///abs/path` is accepted.
- **Files modified:** `agent-brain-mcp/agent_brain_mcp/resources/parameterized.py` (one branch in `parse_uri`).
- **Verification:** Six new `TestParseUriFile` unit tests + two `TestReadResourceFileUri` end-to-end tests cover both the accepted three-slash form and the rejected two-slash form.
- **Committed in:** `f284568`

---

**Total deviations:** 3 auto-fixed (1 bug, 1 blocking, 1 bug).
**Impact on plan:** All three deviations are essential for correctness/security. No scope creep. The dispatcher widening (deviation #2) is the only structural change beyond the plan's expected scope; it landed as the minimal-surface change required to let `file://` carry its own MIME type — a single `isinstance` check, fully backward-compatible.

## Issues Encountered

**Parallel-execution git race during Task 4:** Plan 02 was running in parallel and committing simultaneously. One commit attempt grabbed Plan 02's staged planning files (STATE/ROADMAP/REQUIREMENTS/SUMMARY) and dropped my actually-staged test files. Recovered via `git reset --soft HEAD~1` + clean re-stage. No code lost, no Plan 02 work disturbed.

## User Setup Required

None — `file://` reads use the existing `/index/folders/` endpoint and Phase 50's file_sandbox module. No new env vars, no operator configuration beyond what Phase 50 already documented (`MCP_SANDBOX_MAX_READ_BYTES` setting, defaults to 10 MiB).

## Next Phase Readiness

- Plan 51-04 (resources/templates/list + MIN_BACKEND_VERSION bump) is the only remaining plan for Phase 51. It does NOT depend on `file://` internals — it only needs the URI string template `file://{+path}` advertised in the templates list. All four schemes are now addressable; the templates-list plan is the discoverability bow on top.
- Phase 52 (subscriptions) can begin planning. Plan 52-01's `SubscriptionManager.start_polling()` primitive for `job://` reads benefits from the dispatcher being scheme-agnostic; the `file://` handler is a reference for "what does a non-HTTP-backed scheme look like" if Phase 52 adds a file change watcher.

## Self-Check: PASSED

- `agent-brain-mcp/agent_brain_mcp/security/__init__.py` — FOUND on disk
- `agent-brain-mcp/tests/test_resources_read_file.py` — FOUND on disk
- `.planning/phases/51-uri-schemes-templates/plans/03-file-uri-with-sandbox-SUMMARY.md` — FOUND on disk
- Commit `8ea1460` (security shim) — FOUND in git log
- Commit `f284568` (file:// handler + dispatcher) — FOUND in git log
- Commit `9093ed4` (tests + smoke autofix) — FOUND in git log
- 124 of 124 MCP tests passing (124 passed, 4 deselected from e2e)
- 416 of 416 monorepo tests passing (task before-push exit 0)
- 3 of 3 import-linter contracts kept
- Black 50 files unchanged · Ruff All checks passed · mypy no issues in 24 source files

---
*Phase: 51-uri-schemes-templates*
*Completed: 2026-06-03*
