# Phase 51: URI schemes + templates — Context

**Gathered:** 2026-06-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire the four deferred MCP URI schemes through `agent-brain-mcp` so MCP clients can address them via `resources/read`, and publish RFC 6570 templates for them via `resources/templates/list`:

1. `chunk://<chunk_id>` — backed by Phase 50's new `GET /query/chunk/{id}`
2. `graph-entity://<type>/<id>` — backed by Phase 50's new `GET /graph/entity/{type}/{id}`
3. `job://<job_id>` — backed by the existing `GET /index/jobs/{job_id}` (no new server endpoint; this phase establishes the URI as a *resource*, ahead of Phase 52's subscriptions)
4. `file://<abs-path>` — backed by direct filesystem reads in the MCP process, gated through the Phase 50 sandbox helper derived from `folders.list()`

Plus advertise all four schemes via `resources/templates/list` (URI-05) so MCP clients can discover them programmatically.

Phase 51 stops at "addressable + advertised." Subscriptions for `job://` (1s polling cadence + `notifications/resources/updated`) are Phase 52. No new server endpoints in this phase — all server-side work landed in Phase 50.

</domain>

<decisions>
## Implementation Decisions

### A. Resource-vs-template separation in `resources/list`

- **`resources/list` keeps the existing 5 `corpus://` static resources only.** The four new schemes are *parameterized* — every concrete `chunk://abc123` is a different resource. Listing them concretely is unbounded; listing them generically would mis-advertise them as static.
- **`resources/templates/list` advertises the 4 new schemes as RFC 6570 URI templates** per MCP spec (URI-05). Concrete reads still go through `resources/read`.
- **Decision: do not retrofit `corpus://*` into templates.** They are genuinely static (5 fixed URIs, no parameters) — they belong in `resources/list`, not `resources/templates/list`. This matches how the MCP spec distinguishes the two listings.
- **Rationale:** Keeps v1 backward compatible (`resources/list` shape unchanged) and matches MCP client expectations — clients that call only `resources/list` continue to see exactly the 5 corpus resources they saw before, with no breakage.

### B. URI template strings (RFC 6570)

The exact `uriTemplate` strings the server advertises in `resources/templates/list`:

| Scheme | uriTemplate | mimeType |
|--------|-------------|----------|
| chunk | `chunk://{chunk_id}` | `application/json` |
| graph-entity | `graph-entity://{type}/{id}` | `application/json` |
| job | `job://{job_id}` | `application/json` |
| file | `file://{+path}` | `null` (per-read; see decision E) |

- **`{+path}` (reserved expansion) for `file://`** — file paths contain `/`, which the default RFC 6570 expansion percent-encodes. The `+` operator preserves reserved characters, which is what filesystem paths need.
- **`{chunk_id}` and `{job_id}` are opaque strings** — chunk ids today are `chunk_<sha>` style; job ids are UUIDs. No validation hint in the template (the spec doesn't carry regex constraints in `uriTemplate`).
- **`{type}/{id}` for graph-entity** mirrors the HTTP endpoint shape `GET /graph/entity/{type}/{id}` from Phase 50 decision B 1:1.

### C. URI parsing + dispatch in `read_resource`

- **Single dispatcher in `server.py`'s `read_resource` handler.** The existing `RESOURCE_REGISTRY` is keyed by exact URI string and only works for static resources. Add a **scheme-prefix lookup** before the registry lookup: if `uri.scheme in {"chunk", "graph-entity", "job", "file"}`, route to a per-scheme handler; otherwise fall through to the existing `RESOURCE_REGISTRY.get(uri_str)` path.
- **Scheme-keyed handler table** lives in a new module (recommend `agent_brain_mcp/resources/parameterized.py`) so `corpus.py` stays the static-resource registry and the new file remains the parameterized-scheme registry.
- **Handler signature:** `Callable[[ApiClient, ParsedURI], dict[str, Any]]` — same pattern as the static handlers, with one extra `ParsedURI` arg carrying the per-scheme params (`chunk_id`, `(type, id)`, `job_id`, `path`). Keep the existing JSON-encoded `ReadResourceContents` return path so the server code only changes at the dispatch boundary.
- **Parse failure** (malformed URI, missing required segment) → `McpError(INVALID_PARAMS)` with `data: {"uri": "<input>", "reason": "missing_chunk_id" | "missing_type" | "missing_id" | "missing_job_id" | "missing_path"}`. Matches v1's `INVALID_PARAMS` precedent for `Unknown resource:` (server.py:153).

### D. HTTP-error → MCP-error mapping for the 3 backend-backed schemes

- **Reuse `errors.raise_for_status` from v1 (`agent_brain_mcp/errors.py`) verbatim.** It already maps 404 → `INVALID_PARAMS`, 503 → `SERVICE_INDEXING`, 502 → `BACKEND_UNAVAILABLE`. No new error codes needed.
- **Per-scheme refinement of `data` blob:** wrap the response so MCP clients can distinguish *scheme-level* failures from *transport* failures:
  - `chunk://abc` → 404 → `INVALID_PARAMS` with `data: {"scheme": "chunk", "chunk_id": "abc", "httpStatus": 404, "cause": "..."}`
  - `graph-entity://Function/foo` → 503 from Phase 50 decision B (GraphRAG disabled) → `SERVICE_INDEXING` with `data: {"scheme": "graph-entity", "reason": "graphrag_disabled", "hint": "..."}` — pass through the Phase 50 hint verbatim
  - `job://xyz` → 404 → `INVALID_PARAMS` with `data: {"scheme": "job", "job_id": "xyz"}`
- **No new ApiClient methods reused from `agent_brain_cli`** — extend `client.py` with `get_chunk(chunk_id)`, `get_graph_entity(type, id)`, and reuse the existing `get_job(job_id)`. Stays consistent with v1's "MCP process is Click/Rich-free" stance.

### E. `file://` scheme: read pipeline + sandbox enforcement

This is the only scheme that doesn't hit the FastAPI server — it's a direct filesystem read inside the MCP process.

- **Sandbox check first, file read second.** The MCP handler:
  1. Parses the URI → absolute path
  2. Calls Phase 50's `is_path_allowed(path, roots)` helper from `agent_brain_server/security/file_sandbox.py`
  3. If denied → `McpError(INVALID_PARAMS)` with the structured `data.reason` Phase 50 defined (`outside_indexed_roots` | `size_limit` | `hidden_file`)
  4. If allowed → `aiofiles.open()` (or `asyncio.to_thread(Path.read_bytes)`) and emit `ReadResourceContents`
- **The sandbox helper must be importable from `agent_brain_mcp`** — Phase 50 deliberately landed `file_sandbox.py` under `agent_brain_server/security/`. Phase 51 either (a) re-exports it through a small shim package or (b) duplicates the helper into `agent_brain_mcp/security/file_sandbox.py`. **Recommended: (a) re-export.** The MCP package already depends on `agent_brain_server` transitively via test fixtures; explicit re-export is cleaner than fork.
- **Roots come from `folders.list()` at read time** (Phase 50 decision A) via the existing `ApiClient.list_folders()` method. Cache TTL: **none — re-fetch on every `file://` read.** Folders can be added/removed during a session and stale roots would silently widen the sandbox.
- **MIME type:** sniffed at read time by Python's `mimetypes.guess_type(path)`. Default to `application/octet-stream` if unknown. Binary files (no text encoding hint) return `BlobResourceContents` (base64-encoded); text files return `ReadResourceContents` with the text body. Match MCP SDK helpers.
- **Size cap:** Phase 50 decision A defines 10 MB default. Enforce **in the `file://` handler**, not just at sandbox-check time — operator could configure a larger limit, but a single read still pulls everything into memory before encoding. Stream the read into a `bytearray` with a guarded length check and abort early if the cap is exceeded.

### F. `job://` is `resources/read` only in Phase 51 — subscription handler is Phase 52

- **Phase 51 lands the `job://` read path but NOT `resources/subscribe`.** Subscriptions are Phase 52 (SUB-01) and require notification infrastructure that doesn't exist yet (`server.py` currently advertises `resources.subscribe = False`).
- **Server capability flag stays at `resources.subscribe = False`** until Phase 52. URI-03's success criterion is "client can call `resources/read` with `job://<id>` and receive current job state" — that's a one-shot read, not a subscription. Phase 52 flips the capability flag and adds the subscribe handler.
- **Read shape mirrors the existing `GET /index/jobs/{job_id}`** response (`JobDetailResponse`) verbatim — no transformation. MCP clients reading `job://abc` get the same JSON as `agent-brain jobs abc`.

### G. v1 test pattern reused, not rewritten

- **New test file: `tests/test_resources_templates_list.py`** — asserts the 4 templates appear with the exact `uriTemplate` strings from decision B. Same shape as the existing `tests/test_resources_list.py`.
- **New test file: `tests/test_resources_read_parameterized.py`** — parameterized across the 4 schemes, mirrors `tests/test_resources_read.py`. Uses the existing `fake_httpx_client` fixture from `conftest.py` for the three server-backed schemes; for `file://` adds a `tmp_path`-based fixture with a fake `folders.list()` whitelist.
- **Backend-version floor stays at `10.0.7`** in `server.py`. Phase 50's new endpoints will be shipped in `agent-brain-server 10.2.0+` — bump `MIN_BACKEND_VERSION` to `10.2.0` in this phase so the MCP process refuses to start against an older server that doesn't expose `/query/chunk/{id}` and `/graph/entity/{type}/{id}`.

### Claude's Discretion

- Where exactly to draw the line between `parameterized.py` and `corpus.py` (single module vs two) — planner picks based on review surface
- Whether `file://` reads emit `text/plain` for `.md`/`.py` or also `text/markdown`/`text/x-python` (MIME registry is messy; pick reasonable defaults)
- Exact wording of `data.reason` values inside parse-failure errors (decision C lists candidates; planner can refine)
- Whether to expose the Phase 50 sandbox config (max read size) via an MCP server flag or read it only from the server's YAML — defer to whichever planner picks for Phase 50 wiring
- Whether to fold the new `ApiClient.get_chunk` / `get_graph_entity` methods into a single PR with the URI handlers or split — planner decides based on review surface

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 50 carry-forward (load-bearing)
- `.planning/phases/50-server-endpoint-prep-v2-design-doc/50-CONTEXT.md` — Phase 50 decisions A/B/C define the server endpoints and sandbox helper this phase wires through MCP; decision E here imports the sandbox helper Phase 50 builds at `agent_brain_server/security/file_sandbox.py`
- `docs/plans/2026-06-XX-mcp-v2-subscriptions.md` (filed by Phase 50, VAL-05) — v2 design doc; per-phase decisions section covers Phase 51 URI dispatch

### MCP design lineage
- `docs/plans/2026-05-28-mcp-uds-transport-design.md` — v1 master design; §6.5 documents the 5 `corpus://` resources Phase 51 must not break; §11 v2 row sketches the URI work this phase delivers
- `docs/roadmaps/mcp/v2-subscriptions-and-resources.md` §"Deferred resource schemes" — scope contract for the 4 URI schemes + `resources/templates/list`; defines DoD
- `docs/roadmaps/mcp/README.md` — meta-roadmap; confirms Phase 52 (subscriptions) depends on Phase 51 landing `job://` as an addressable resource first

### MCP package (existing patterns to extend)
- `agent-brain-mcp/agent_brain_mcp/server.py` — `read_resource` handler (line 147) and `RESOURCE_REGISTRY` dispatch; decision C's scheme-prefix lookup slots in before line 150
- `agent-brain-mcp/agent_brain_mcp/resources/corpus.py` — static `ResourceSpec` registry pattern; parameterized handler module follows this shape with the extra `ParsedURI` arg
- `agent-brain-mcp/agent_brain_mcp/client.py` — `ApiClient` pattern; new `get_chunk` / `get_graph_entity` methods extend lines 80-124
- `agent-brain-mcp/agent_brain_mcp/errors.py` — `raise_for_status` mapping (line 68); decision D reuses this verbatim, `INVALID_PARAMS` / `SERVICE_INDEXING` codes
- `agent-brain-mcp/tests/test_resources_read.py` — existing v1 read-test pattern; phase 51 mirrors this for the 4 new schemes
- `agent-brain-mcp/tests/test_resources_list.py` — existing v1 list-test pattern; mirrored for `resources/templates/list`
- `agent-brain-mcp/tests/conftest.py` — `fake_httpx_client` fixture; reused for the 3 server-backed schemes

### Server endpoints (Phase 50 outputs, consumed here)
- `agent-brain-server/agent_brain_server/api/routers/query.py` — `GET /query/chunk/{id}` lands here (Phase 50 decision C); `client.get_chunk()` calls this path
- `agent-brain-server/agent_brain_server/api/routers/` — Phase 50 may add a new `graph.py` or extend an existing router for `GET /graph/entity/{type}/{id}`; `client.get_graph_entity()` calls this path
- `agent-brain-server/agent_brain_server/api/routers/jobs.py` — `GET /index/jobs/{job_id}` (line 42, already exists); `client.get_job()` already calls this, no change
- `agent-brain-server/agent_brain_server/api/routers/folders.py` — `GET /index/folders/`; the `file://` sandbox handler refreshes its allowed-roots list from this on every read (decision E)
- `agent-brain-server/agent_brain_server/security/file_sandbox.py` — Phase 50 deliverable; Phase 51 imports `is_path_allowed`, `canonicalize_path`, and `MAX_READ_BYTES` from here

### MCP SDK (vendored under `.venv`, external spec)
- `agent-brain-mcp/.venv/.../mcp/server/lowlevel/server.py` lines 319-327 — `@server.list_resource_templates()` decorator pattern; Phase 51 wires the new list-templates handler the same way `@server.list_resources()` is wired today
- `agent-brain-mcp/.venv/.../mcp/types.py` line 794 — `ResourceTemplate` model (`uriTemplate`, `name`, `description`, `mimeType`); decision B's template specs become 4 instances of this type

### Existing requirements
- `.planning/REQUIREMENTS.md` §"Deferred URI Schemes (URI)" — URI-01 through URI-05; this phase's exact contract
- `.planning/ROADMAP.md` Phase 51 — 5 success criteria; Phase 52 dependency note

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`agent_brain_mcp/server.py:147-164` `read_resource` handler** — the only MCP-side wiring point. Today it does `RESOURCE_REGISTRY.get(uri_str)`. Decision C inserts a scheme-prefix lookup *before* this line; the existing path stays for `corpus://*`.
- **`agent_brain_mcp/resources/corpus.py` `ResourceSpec` dataclass** — copy the shape for the parameterized registry, just adding a `params: ParsedURI` arg to the handler signature.
- **`agent_brain_mcp/client.py` `ApiClient`** — extension point for `get_chunk(chunk_id)` and `get_graph_entity(entity_type, entity_id)`. `get_job(job_id)` already exists (line 114). All three use `self._get(...)` which already runs through `errors.raise_for_status`.
- **`agent_brain_server/storage/protocol.py:224` `get_by_id(chunk_id)` already exists** on `StorageBackendProtocol`. Phase 50's new `GET /query/chunk/{id}` route delegates to this — no protocol change needed in Phase 51.
- **`agent_brain_server/api/routers/jobs.py:42-70` `GET /index/jobs/{job_id}`** — `JobDetailResponse` body is exactly what `job://` should expose. Zero transformation needed; the MCP `read_resource` handler JSON-encodes it through the existing `ReadResourceContents` path.
- **`tests/conftest.py` `fake_httpx_client`** — the v1 tests fake the HTTP layer entirely. Phase 51 tests extend this fixture's URL-to-response map with stub `GET /query/chunk/<id>`, `GET /graph/entity/<type>/<id>`, `GET /index/jobs/<id>` responses.

### Established Patterns

- **Sync httpx in async handler via `asyncio.to_thread`** (server.py:130, 158) — the parameterized handlers MUST keep this pattern for the 3 server-backed schemes, otherwise stdio freezes on a blocking call. The `file://` handler does *not* need `to_thread` for the filesystem read — `aiofiles` is async-native — but the sandbox-roots refresh (`ApiClient.list_folders()`) is sync httpx and DOES need `to_thread`.
- **Error mapping table is closed** (errors.py:91-112) — no new codes for Phase 51. Reuse `INVALID_PARAMS` (-32602) for "no such chunk / entity / job / unknown path" and `SERVICE_INDEXING` (-32002) for "GraphRAG disabled." Phase 50's design doc already aligned the HTTP status mapping for both new endpoints.
- **`json.dumps(data, indent=2, default=str)` on the way out** (server.py:161) — keep this for the 3 JSON schemes. For `file://`, return raw bytes through `BlobResourceContents` (binary) or the text body through `ReadResourceContents` (text); skip the JSON wrapper.
- **Backend-version floor enforced at startup** (server.py:42, 296-299) — Phase 51 bumps `MIN_BACKEND_VERSION = "10.0.7"` → `"10.2.0"`. This is the only place the v2-server-required guard lives; once raised, an older `agent-brain-server` cannot ship without `/query/chunk/{id}` and `/graph/entity/{type}/{id}`.

### Integration Points

- **MCP server capability negotiation** (server.py:248-270 `run_stdio`) — `notification_options.resources_changed=False` stays. `resources.subscribe` stays False (Phase 52 flips it). Phase 51 does **not** touch the capability advertisement.
- **`@server.list_resource_templates()` decorator** (MCP SDK lowlevel/server.py:319) — new handler wired alongside the existing `@server.list_resources()` block at server.py:135. Returns `list[types.ResourceTemplate]` (4 instances, hard-coded from decision B).
- **`fake_httpx_client` URL routing** in `tests/conftest.py` — add the 3 new server-backed URL patterns to whatever route map the fixture exposes. For `file://` tests, stub the filesystem with `tmp_path` and patch `ApiClient.list_folders()` to return the stub roots.
- **`pyproject.toml` `agent-brain-mcp` dependency floor** — bumping `MIN_BACKEND_VERSION` also requires bumping the `agent-brain-rag` (or whatever the server distribution is named) version pin in `agent-brain-mcp/pyproject.toml` if any is set. Audit the pin and the version-floor constant in lockstep.

### Greenfield (no existing pattern)

- **No URI template support exists anywhere in the codebase.** This phase creates the first `list_resource_templates` handler. There's no shared RFC 6570 string-template helper to reuse; the 4 templates are hard-coded strings in decision B.
- **No `ParsedURI` value type.** Recommend a small dataclass in the new `parameterized.py` module with fields per scheme (`chunk_id`, `entity_type`, `entity_id`, `job_id`, `path`) — only the scheme-relevant fields populated. Cheaper than 4 separate parse-result types.
- **No filesystem I/O exists in `agent_brain_mcp` today.** Adding `aiofiles` (or `asyncio.to_thread` + `pathlib`) is a new dependency surface. Prefer `asyncio.to_thread(Path(p).read_bytes)` to avoid a new dependency unless the planner sees a concrete need.

</code_context>

<specifics>
## Specific Ideas

- **The v2 design doc (filed by Phase 50, VAL-05) MUST document the exact `uriTemplate` strings from decision B** in its per-phase section for Phase 51. Reviewers need to challenge the `{+path}` choice for `file://` before it ships — once a template string is advertised by a server, client libraries lock onto it and changing it is a breaking change.
- **The `file://` sandbox helper SHARING design is load-bearing.** Phase 50 decision A says the helper is the *single source of truth* for path policy. If Phase 51 forks the logic into `agent_brain_mcp/security/file_sandbox.py`, drift between server-side `file://` reads (none today) and MCP-side `file://` reads (this phase) becomes a security risk. Re-export, do not fork. Planner should make this explicit in the per-phase plan.
- **`MIN_BACKEND_VERSION` bump to `"10.2.0"` is a release-train coupling.** The MCP package must be released *after* `agent-brain-server 10.2.0` ships, otherwise the version-compat check at startup (server.py:296-299) refuses to start. Document this ordering in the v2 design doc's release plan section.
- **Phase 52 will subscribe to `job://`.** Phase 51's parameterized handler signature should leave room for a future `subscribe` companion — i.e., split URI parsing from the read body so Phase 52 can reuse the parsed `job_id` extraction without duplicating it. Concretely: parse the URI once in the dispatcher; pass the parsed result to either the `read` handler (Phase 51) or the `subscribe` handler (Phase 52).
- **Risk #178 (Kuzu SIGSEGV) carries forward.** If Phase 50's `GET /graph/entity/{type}/{id}` returns 503 because Kuzu is disabled, MCP `read_resource` on `graph-entity://*` surfaces `SERVICE_INDEXING` with the Phase 50 hint. Note this in the design doc's risk register; operator workaround is `graphrag.store_type: simple` until #178 is fixed.

</specifics>

<deferred>
## Deferred Ideas

- **`resources/subscribe` for `job://<id>`** — Phase 52 (SUB-01). Phase 51 lands the URI as addressable but stops short of the subscribe handler and the 1s polling cadence.
- **`resources/subscribe` for `corpus://status` and `corpus://folders`** — Phase 52 (SUB-02, SUB-03). Static resources gain subscription support there.
- **`resources/list` pagination** — the MCP `ListResourceTemplatesResult` is a `PaginatedResult`. v2 returns all 4 templates in one page (well under any client buffer). Pagination becomes interesting if v3 expands the template count significantly.
- **Per-scheme metadata in `ResourceTemplate.annotations`** — MCP supports `Annotations` on each template (audience, priority). Phase 51 omits these (no values worth advertising yet). Could add `audience: ["assistant"]` on `chunk://` later if MCP clients start filtering on it.
- **`file://` writes (`resources/write` or a `write_file` tool)** — completely out of scope. v2 is read-only. Any write capability needs auth (v4 OAuth work).
- **`file://` with relative path resolution against `roots/list`** — v2 spec only addresses absolute paths after canonicalization. Relative-path support (e.g., `file://./README.md` resolved against the current `roots[0]`) is a v3 ergonomics concern.
- **Batch read (`POST /resources/read` with multiple URIs)** — not part of MCP spec yet. If a future MCP spec revision adds it, agent-brain can fold it in trivially because the per-scheme handlers are already independent.
- **`chunk://` with `?include=embedding` query** — Phase 50 decision C explicitly excludes embeddings from the chunk response. If a downstream consumer needs embeddings, they go through `/query` directly. Don't open the door in Phase 51.
- **`graph-entity://` multi-hop neighbors** — Phase 50 decision B caps at 1-hop. Multi-hop traversal would be a new endpoint (`GET /graph/entity/{type}/{id}/neighbors?depth=N`) and a new scheme (`graph-walk://`); both deferred.
- **MCP `roots/list` request handler** — the *server-side* `roots/list` handler that exposes which absolute paths the MCP server considers addressable. The MCP spec puts `roots/list` on the *client* (it's how the client tells the server which paths it's allowed to touch). Server-side enforcement uses the sandbox helper directly. If MCP clients need to discover roots they should call `corpus://folders`. Re-evaluate if MCP spec gains a server-side `roots/list`.

</deferred>

---

*Phase: 51-uri-schemes-templates*
*Context gathered: 2026-06-02*
