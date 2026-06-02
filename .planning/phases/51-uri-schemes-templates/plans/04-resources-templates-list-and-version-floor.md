# Plan 04: `resources/templates/list` handler + `MIN_BACKEND_VERSION` bump

**Phase:** 51 — URI schemes + templates
**Requirements covered:** URI-05
**Depends on:** Plan 01 (dispatcher), Plan 02 (`chunk://` + `graph-entity://` handlers), Plan 03 (`file://` handler) — all four schemes must be live before this plan's end-to-end SDK test can exercise them.
**Parallel-safe with:** none (finalization plan)
**Status:** Not started

## Goal

Wire the `@server.list_resource_templates()` MCP handler so clients can call `resources/templates/list` and discover the four parameterized URI schemes (`chunk://`, `graph-entity://`, `job://`, `file://`) along with their RFC 6570 `uriTemplate` strings (CONTEXT.md decision B). Bump `MIN_BACKEND_VERSION` to `"10.2.0"` so the MCP process refuses to start against an older `agent-brain-server` that does not expose the new endpoints. Add the end-to-end SDK test that exercises `resources/templates/list` + a `resources/read` per scheme through the official MCP Python SDK client, closing out the URI-05 acceptance contract.

This is the finalization plan: it ties the four scheme handlers together at the discovery surface, raises the backend-version floor, and ships the only end-to-end test that uses the official MCP SDK to drive the full templates-list + per-scheme-read flow.

## Acceptance Criteria

- [ ] `agent_brain_mcp/resources/parameterized.py` exposes a `TEMPLATE_REGISTRY: list[types.ResourceTemplate]` (or equivalent constructor function) with exactly four entries matching CONTEXT.md decision B:
  | Scheme | `uriTemplate` | `mimeType` |
  |--------|-------|------|
  | chunk | `chunk://{chunk_id}` | `application/json` |
  | graph-entity | `graph-entity://{type}/{id}` | `application/json` |
  | job | `job://{job_id}` | `application/json` |
  | file | `file://{+path}` | `null` (per-read sniff) |
- [ ] `agent_brain_mcp/server.py` registers an `@server.list_resource_templates()` handler that returns the four `ResourceTemplate` entries.
- [ ] Each `ResourceTemplate` carries `name`, `description`, and `uriTemplate` per the MCP SDK's `mcp/types.py:794` definition. `mimeType` is included for the three JSON schemes; omitted (or `None`) for `file://` since the MIME is determined per-read.
- [ ] `MIN_BACKEND_VERSION` in `agent_brain_mcp/server.py` (currently `"10.0.7"`) is bumped to `"10.2.0"`.
- [ ] If the MCP package's `pyproject.toml` has a version pin on the server distribution (`agent-brain-rag` or `agent-brain-server`), bump it in lockstep to `^10.2.0` (or whichever pin matches the released server version).
- [ ] Server capability advertisement is unchanged for `resources.subscribe` (stays `False`; Phase 52 flips it). The MCP SDK auto-detects the `list_resource_templates` handler's presence — no explicit capability flag bump needed for `templates` discovery (verify by re-reading the MCP SDK `lowlevel/server.py:319-327`).
- [ ] An MCP client calling `resources/templates/list` receives exactly four templates with the `uriTemplate` strings from CONTEXT.md decision B.
- [ ] The existing `resources/list` continues to return exactly the 5 `corpus://*` static resources (no regression from prior plans).
- [ ] End-to-end test against the official MCP SDK client: `initialize` → `resources/templates/list` → for each of the 4 schemes, run `resources/read` with a fixture URI and assert success or expected `INVALID_PARAMS` (depending on whether the fixture backend has the data).
- [ ] `task mcp:test`, `task mcp:contract`, `task check:layering`, `task before-push`, `task pr-qa-gate` all exit 0.
- [ ] **Checkpoint:** Human review of the four `uriTemplate` strings before merge — once advertised, they are a forward-compatibility commitment per CONTEXT.md specifics #1 and risk #3 in `51-PLAN.md`.

## Files to Touch

| File | Action | Notes |
|------|--------|-------|
| `agent-brain-mcp/agent_brain_mcp/resources/parameterized.py` | modify | Add `TEMPLATE_REGISTRY: list[types.ResourceTemplate]` (or `build_template_registry()` factory if hand-rolling `types.ResourceTemplate` is verbose). ~30 LOC delta. |
| `agent-brain-mcp/agent_brain_mcp/server.py` | modify | (a) Add `@server.list_resource_templates()` handler returning `TEMPLATE_REGISTRY`. (b) Bump `MIN_BACKEND_VERSION = "10.2.0"`. ~25 LOC delta. |
| `agent-brain-mcp/pyproject.toml` | modify (conditional) | If a version pin on the server distribution exists, bump to `^10.2.0`. If no pin, skip. |
| `agent-brain-mcp/tests/test_resources_templates_list.py` | create | Asserts the 4 templates appear with the exact `uriTemplate` strings from decision B. Asserts the existing `resources/list` is unchanged. ~80 LOC. |
| `agent-brain-mcp/tests/test_e2e_stdio.py` | modify | Add end-to-end SDK test that exercises `templates/list` + per-scheme `resources/read`. Mirrors the existing v1 e2e test pattern (initialize → SDK client calls → assertions). ~80 LOC delta. |
| `agent-brain-mcp/tests/test_version_compat.py` | modify | Update the version-floor assertion to expect rejection against a `10.1.x` backend and acceptance against `10.2.0+`. ~15 LOC delta. |
| `docs/plans/2026-06-XX-mcp-v2-subscriptions.md` | modify | Add a short subsection to the per-phase decisions section for Phase 51 documenting (a) the four `uriTemplate` strings as a forward-compatibility commitment and (b) the release-train coupling (MCP package must release after agent-brain-server 10.2.0). ~30 LOC delta. |

**Estimated total: ~180 LOC (including tests and doc updates).**

## Implementation Steps

1. **Read `agent-brain-mcp/.venv/.../mcp/types.py:794`** to confirm the `ResourceTemplate` constructor signature. CONTEXT.md indicates the fields are `uriTemplate, name, description, mimeType`. Verify the exact spelling (`mimeType` vs `mime_type` — MCP uses camelCase on the wire but Python SDKs often expose snake_case in Python with aliasing).

2. **Build `TEMPLATE_REGISTRY` in `parameterized.py`:**
   ```python
   TEMPLATE_REGISTRY: list[types.ResourceTemplate] = [
       types.ResourceTemplate(
           uriTemplate="chunk://{chunk_id}",
           name="chunk",
           description="Retrieve a single indexed chunk by id (content + metadata, no embedding).",
           mimeType="application/json",
       ),
       types.ResourceTemplate(
           uriTemplate="graph-entity://{type}/{id}",
           name="graph-entity",
           description="Retrieve a GraphRAG entity by type and id.",
           mimeType="application/json",
       ),
       types.ResourceTemplate(
           uriTemplate="job://{job_id}",
           name="job",
           description="Retrieve current state of an indexing job by id.",
           mimeType="application/json",
       ),
       types.ResourceTemplate(
           uriTemplate="file://{+path}",
           name="file",
           description=(
               "Read a file by absolute path; restricted to indexed roots. "
               "MIME type is determined per-read by extension sniffing."
           ),
           # mimeType omitted — determined per-read
       ),
   ]
   ```
   The `{+path}` reserved expansion (RFC 6570 operator `+`) preserves the `/` characters that filesystem paths require — without it, the default RFC 6570 expansion percent-encodes `/` as `%2F`.

3. **Wire the handler in `server.py`:**
   Locate the existing `@server.list_resources()` block (around line 135 per CONTEXT.md). Add immediately after it:
   ```python
   @self.server.list_resource_templates()
   async def handle_list_resource_templates() -> list[types.ResourceTemplate]:
       return TEMPLATE_REGISTRY
   ```
   Use whichever `self.server` / module-level pattern the existing v1 handler uses — match v1 style verbatim.

4. **Bump `MIN_BACKEND_VERSION`** in `server.py` from `"10.0.7"` to `"10.2.0"`. This is the single point of version-floor enforcement; once raised, the MCP process refuses to start (server.py:296-299) against an older agent-brain-server that lacks `/query/chunk/{id}` and `/graph/entity/{type}/{id}`.

5. **Audit `agent-brain-mcp/pyproject.toml`** for any `agent-brain-rag` or `agent-brain-server` version pin. If present, bump to `^10.2.0` to match the runtime version-floor. Pinning a major-version-only floor (`^10.2.0` allows `10.2.x` and `<11.0.0`) is the conservative choice — verify against the project's existing pin conventions.

6. **Create `tests/test_resources_templates_list.py`:**
   - `async def test_resources_templates_list_returns_four(mcp_server)` — call the handler, assert `len(result) == 4`.
   - `async def test_templates_list_contains_expected_uri_templates(mcp_server)` — for each of the four schemes, assert one template exists with the exact `uriTemplate` string from decision B.
   - `async def test_templates_list_mimetype_for_json_schemes(mcp_server)` — three templates have `mimeType == "application/json"`.
   - `async def test_templates_list_file_scheme_has_no_static_mimetype(mcp_server)` — the `file` template's `mimeType` is `None` (or absent).
   - `async def test_resources_list_unchanged(mcp_server)` — regression: existing `resources/list` still returns exactly the 5 `corpus://*` resources.

7. **Add end-to-end test to `tests/test_e2e_stdio.py`:**
   ```python
   async def test_e2e_templates_list_and_read_all_schemes(mcp_stdio_session):
       # mcp_stdio_session uses the official MCP Python SDK to drive a real
       # stdio subprocess running agent-brain-mcp against the fake backend.
       templates = await mcp_stdio_session.list_resource_templates()
       assert {t.uriTemplate for t in templates} == {
           "chunk://{chunk_id}",
           "graph-entity://{type}/{id}",
           "job://{job_id}",
           "file://{+path}",
       }
       # Per-scheme reads against the fake backend:
       chunk = await mcp_stdio_session.read_resource("chunk://stub-chunk-id")
       assert chunk.contents[0].uri == "chunk://stub-chunk-id"
       # ... similar for job, graph-entity, file
   ```
   Reuse the existing `mcp_stdio_session` fixture pattern from v1's `test_e2e_stdio.py`. If the SDK doesn't have a `list_resource_templates()` method, fall back to sending the raw JSON-RPC `resources/templates/list` request through the session's `request()` method — verify by re-reading the MCP SDK Python client API.

8. **Update `tests/test_version_compat.py`:**
   - Existing test pins floor at `10.0.7`. Bump fixture versions to test:
     - Backend reports version `10.1.5` → MCP refuses to start with a clear error.
     - Backend reports version `10.2.0` → MCP starts successfully.
     - Backend reports version `10.3.0` → MCP starts successfully (compatible — higher than floor).

9. **Update the v2 design doc (`docs/plans/2026-06-XX-mcp-v2-subscriptions.md`):**
   Add a Phase 51 subsection covering:
   - The four `uriTemplate` strings (verbatim from decision B) — flag as forward-compatibility commitment.
   - The `{+path}` operator choice for `file://` and why (RFC 6570 reserved expansion preserves `/`).
   - The release-train coupling note (MCP package release must follow agent-brain-server 10.2.0).
   - The risk #178 (Kuzu SIGSEGV) carry-forward note and operator workaround (`graphrag.store_type: simple`).

10. **Checkpoint — request human review of the `uriTemplate` strings.** This is a forward-incompatible commitment; once advertised, MCP client libraries lock onto them. Re-confirm:
    - `chunk://{chunk_id}` vs `chunk://{id}` (consistency: per-scheme parameter name)
    - `graph-entity://{type}/{id}` vs `graph-entity://{entity_type}/{entity_id}` (matches HTTP route shape; the abbreviated form matches CONTEXT.md decision B)
    - `job://{job_id}` (matches existing CLI conventions)
    - `file://{+path}` (RFC 6570 reserved expansion vs default expansion)
    
    Confirm against CONTEXT.md decision B before merging.

11. **Run quality gates:**
    ```bash
    cd agent-brain-mcp && poetry run pytest -v
    task mcp:test
    task mcp:contract
    task check:layering
    task before-push
    task pr-qa-gate
    ```

## Verification

- `poetry run pytest agent-brain-mcp/tests/test_resources_templates_list.py -v` — all template-list tests pass.
- `poetry run pytest agent-brain-mcp/tests/test_e2e_stdio.py -v` — end-to-end SDK test exercising templates/list + per-scheme reads passes.
- `poetry run pytest agent-brain-mcp/tests/test_version_compat.py -v` — version-floor enforcement bumped to `10.2.0`.
- `poetry run pytest agent-brain-mcp/tests/ -v` — entire MCP test suite passes (no regression in Plans 01-03 tests, no regression in v1 tests).
- Manual smoke against a running server (server must be ≥10.2.0 for the version-floor check to pass — if testing against an older server, expect the MCP process to exit with the floor error):
  ```bash
  agent-brain start --uds
  scripts/mcp-templates-list.sh | agent-brain-mcp --backend uds | \
    jq -e '.result.resourceTemplates | length == 4'
  scripts/mcp-templates-list.sh | agent-brain-mcp --backend uds | \
    jq -e '[.result.resourceTemplates[].uriTemplate] | contains(["chunk://{chunk_id}", "graph-entity://{type}/{id}", "job://{job_id}", "file://{+path}"])'
  agent-brain stop
  ```
- All five quality gates (`task mcp:test`, `task mcp:contract`, `task check:layering`, `task before-push`, `task pr-qa-gate`) exit 0.
- Phase 51 success criteria from ROADMAP.md item 5: "An MCP client calling `resources/templates/list` receives templates for all four schemes" — verified by `test_e2e_templates_list_and_read_all_schemes`.

## Risk Notes

- **Risk (forward-compat):** Template URI strings, once advertised, are a public commitment. Client libraries (including future Agent Brain CLI v3 work) will lock onto them. The checkpoint in step 10 is the only chance to catch a wrong choice before this lands.
- **Risk (release coupling):** `MIN_BACKEND_VERSION = "10.2.0"` requires `agent-brain-server 10.2.0` to ship before `agent-brain-mcp` does. Mitigation: documented in design-doc release plan; CI release script ordering (Phase 55) enforces this. If the MCP package accidentally ships first, operators get the version-floor error at startup — recoverable, but a bad first impression. CHANGELOG entry must call out the floor bump prominently.
- **Risk (SDK API drift):** `@server.list_resource_templates()` decorator exists in the MCP SDK ≥1.0 (per CONTEXT.md citing `lowlevel/server.py:319-327`). If the pinned SDK version in `pyproject.toml` is older, the handler registration won't bind. Verify pinned version supports the decorator before merge; bump if needed.
- **Risk (capability negotiation):** The MCP spec auto-discovers `resourceTemplates` capability from handler presence in some SDK versions; in others, it requires an explicit `resources.subscribe` or similar bit. Re-read the SDK's `_get_capabilities` method to confirm — if explicit capability is needed, this plan must update the `notification_options` block in `run_stdio` (server.py:248-270). CONTEXT.md says the capability advertisement is unchanged; verify this is still true with the actual pinned SDK version.
- **Risk (test fixture coverage):** The end-to-end test in step 7 exercises all four schemes. For `chunk://` and `graph-entity://`, the fake backend in conftest.py must serve the stub responses defined in Plan 02. For `file://`, the test must use a tmpdir + stub `list_folders` defined in Plan 03. If either fixture is missing or has drifted from this plan's expectations, the e2e test fails first. This is the integration point that proves Plans 01-04 work together.
- **Quality gate:** All five gates exit 0 before push, per CLAUDE.md #1 rule. This is the last plan in the phase — it's the gate before the phase transition.

---
*Plan 04 of Phase 51*
