---
last_validated: 2026-06-03
---

# Changelog

All notable changes to Agent Brain will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

(nothing yet)

---

## [10.2.0] - 2026-06-03

### Security

- **Injector scripts now require explicit hash-allowlisting** (`agent_brain_server/services/injector_allowlist.py`, `agent_brain_server/services/content_injector.py`, `agent_brain_server/api/routers/index.py`, `agent_brain_cli/commands/inject.py`, `docs/USER_GUIDE.md`). Previously, `POST /index` and `POST /index/dry-run` accepted any caller-supplied `.py` path and executed it via `importlib.util.exec_module` in the server process — an unauthenticated RCE that allowed credential exfiltration (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`) and arbitrary code execution by anyone who could reach the HTTP boundary. The fix requires operators to declare trusted scripts in `.agent-brain/config.yaml` (project) and/or `~/.config/agent-brain/config.yaml` (global) with both their path and sha256 hash; any script not in the allowlist, or whose hash does not match the listed value, is rejected with HTTP 403 before any code is loaded. The default — no config or empty `injector_scripts:` — is fail-closed: every script is rejected. The gate is enforced at two layers (`api/routers/index.py` for synchronous 403 + `services/content_injector.ContentInjector._load_script` for defense-in-depth against any future internal caller) so the trust boundary lives where the dangerous operation lives, not at each HTTP entry point. Project-local allowlist entries take precedence over global entries for the same resolved path. Operators of any existing `agent-brain inject --script` workflow MUST add the script's path and sha256 to `injector_scripts:` before re-running; the CLI surfaces a clear 403 message pointing at the config schema. 11 adversarial unit tests in `tests/test_injector_allowlist.py` pin the fail-closed default, hash-mismatch rejection, malformed-entry handling, path resolution, and project↔global precedence. 2 integration tests in `tests/integration/test_api.py` confirm both `POST /index` and `POST /index` with `dry_run=true` return 403 for unlisted scripts. Closes #181.

- **`allow_external` query parameter replaced by server-side setting** (`agent_brain_server/api/routers/index.py`, `agent_brain_server/config/settings.py`, `agent_brain_server/job_queue/job_service.py`, `agent_brain_cli/client/api_client.py`, `agent_brain_cli/commands/index.py`, `agent_brain_cli/commands/inject.py`, `scripts/query_benchmark.py`, `docs/API_REFERENCE.md`, `.env.example`). The previous `POST /index/?allow_external=true` query parameter let any HTTP caller bypass project-root path containment. Combined with the lack of endpoint authentication on the server, this enabled directory-traversal-style exfiltration: a caller could index `~/.ssh`, `~/.config/sops`, or any other sensitive path and read the contents back through `POST /query`. The parameter is now removed from both `POST /index` and `POST /index/add`; containment is controlled exclusively by the new `AGENT_BRAIN_ALLOW_EXTERNAL_PATHS` server-side environment variable (default `false`). Operators who relied on the per-request override must set the variable on the server process after reading the threat model in `.env.example`. The CLI's `--allow-external` flag was removed from `agent-brain index` and `agent-brain inject` to match. Internal callers such as `file_watcher_service` continue to pass `allow_external=True` directly to `JobQueueService.enqueue_job()`; only the HTTP boundary is locked down. Six new tests in `tests/unit/job_queue/test_job_service_path_validation.py` and `tests/integration/test_api.py` pin the four-quadrant containment matrix and the rejection-path contract. Closes #180.

### Added

- **MCP v2 — 16-tool surface complete** (closes [#186](https://github.com/SpillwaveSolutions/agent-brain/issues/186)). The 9 tools deferred from v10.1's v1 surface now ship — `agent-brain-mcp` exposes all 16 MCP tools originally scoped in `docs/plans/2026-05-28-mcp-uds-transport-design.md` §15.1. The new tools are: `explain_result` (provenance + scoring breakdown for a `chunk_id`), `add_documents` (incremental indexing without recreating the corpus), `inject_documents` (enrichment via a hash-allowlisted injector script per #181), `wait_for_job` (the first async MCP tool handler in the codebase — emits `notifications/progress` at least every 2s during long-running jobs), `list_folders`, `remove_folder`, `cache_status`, `clear_cache`, `list_file_types`. `cancel_job`-style destructive operations are gated as required `confirm: Literal[True]` schema fields (continued from v10.1's pattern). All 16 tools advertise both `inputSchema` and `outputSchema`, return `content[0]: TextContent` plus a `structuredContent` dict matching the declared shape, and produce structured MCP error codes (`-32602 InvalidParams`, `-32000 BackendConflict`, `-32001 BackendUnavailable`, etc.) with `data.httpStatus` + `data.cause`.

- **Resource subscriptions** (`resources/subscribe` capability — VAL-02). Three subscribable URIs ship: `job://{job_id}` (1s cadence, terminates on terminal status), `corpus://status` (30s cadence, drops volatile timestamp keys via `DEFAULT_DROP_KEYS` so deeply-nested uvicorn request timestamps don't spam `notifications/resources/updated`), and `corpus://folders` (watcher-driven). Per-session `SubscriptionManager` cancels polling tasks on `unsubscribe`, `cleanup_session`, and `cleanup_all`; `run_stdio` and the new HTTP transport both fire `cleanup_all` on client disconnect (stdio EOF or HTTP TCP RST). The polling primitive is reused by `wait_for_job` for progress notifications. `MIN_BACKEND_VERSION` bumped to `10.2.0` (server-side endpoints `GET /query/chunk/{id}` and `GET /graph/entity/{type}/{id}` ship in this release; older `agent-brain-mcp` builds against an older server fail loudly at startup).

- **Streamable HTTP transport for MCP** (`agent-brain-mcp --transport http`, loopback-only — VAL-03). New `agent_brain_mcp.http.run_http()` runs the official MCP SDK's `StreamableHTTPSessionManager` behind a uvicorn loopback bind with `validate_loopback_host` rejecting `--host 0.0.0.0` or any non-127.0.0.1/::1 address at startup (CVE-class drift-prevention — there is no auth on this transport in v10.2; OAuth lands in v4). Mount path is `/mcp` (`MCP_MOUNT_PATH` constant) plus a `/healthz` probe for readiness. `--transport {auto,stdio,http}` selector resolves with no silent fallback: explicit `--transport http` against a port conflict raises rather than degrading to stdio.

- **Deferred URI schemes** (URI-01..05). `resources/templates/list` advertises four RFC 6570 templates — `chunk://{chunk_id}`, `graph-entity://{type}/{id}`, `job://{job_id}`, and `file://{+path}` (reserved expansion so `/` survives) — implemented via a single `agent_brain_mcp.resources.parameterized` dispatcher. The strings are a **forward-compatibility commitment**: once published in 10.2.0, MCP client libraries lock onto them and changes are breaking (pinned by `test_registry_uri_templates_match_expected_set`). The `file://` handler shares Phase 50's sandbox helper via a pure re-export shim at `agent_brain_mcp.security.__init__` — no policy fork.

- **Parameterized contract tests against the official MCP SDK** (VAL-01). New `agent-brain-mcp/tests/contract/` directory with a single source-of-truth tool matrix (`_tool_matrix.py`) driving both Layer 1 (in-process, 16-row `tests/test_each_tool.py`) and Layer 2 (SDK over stdio, `test_tools_contract.py` — 32 assertions: 16 happy-path + 16 negative-arg). Layer 2 over HTTP (`test_http_transport_contract.py`, 6 assertions) proves transport-equivalence — the same 16-tool + 5-corpus-URI surface that stdio pins. Subscription lifecycle (`test_subscription_lifecycle.py`, 4 tests including the disconnect-cleanup EOF code path) exercises all three subscribable URIs end-to-end. Total contract suite: **49 tests in ~25s**; opted out of the fast-path by default (`-m contract` marker) so per-tool feedback stays sub-second. Inheritance pattern locked: a `mcp_stdio_session` callable + async-context-manager fixture dodges anyio's cross-task `CancelScope.__exit__` trap that bites async-generator fixtures wrapping `stdio_client` / `streamablehttp_client`.

- **`GET /query/chunk/{chunk_id}` and `GET /graph/entity/{type}/{id}` server endpoints** (Phase 50). Backs the `chunk://` and `graph-entity://` URI schemes. Both endpoints return ChromaDB-backed and Kuzu/Simple-backed records respectively; the graph endpoint returns 503 with `reason="kuzu_unavailable"` (parseable slug) when Kuzu corruption is detected per #178 fallback.

### Changed

- **`agent-brain-mcp` and `agent-brain-uds` now run as part of root `task before-push` and `task pr-qa-gate`** — adds **approximately 60-90s to local pre-push time**, but catches MCP/UDS regressions before push instead of waiting for CI. The MCP package coverage floor stays at 80% (security-boundary code per v1 plan §9); UDS at 80% as well. Per-package `before-push` tasks added to each package's `Taskfile.yml` (`format:check → lint → typecheck → test:cov`). The existing `before_push_lock_guard.sh` (issue #174) wraps the new sub-tasks so any in-tree `poetry.lock` drift from MCP/UDS `poetry install` calls is auto-reverted. **Closes [DR-5](https://github.com/SpillwaveSolutions/agent-brain/blob/main/docs/plans/2026-05-28-mcp-uds-transport-design.md#L595)** from `docs/plans/2026-05-28-mcp-uds-transport-design.md` §14 #5 ("New packages don't join root `before-push` in v1 … Folds into root only after 10.1.0 ships green and one release cycle elapses (target: 10.2.0)"). v10.1 has shipped green; v10.2 ships the integration.

- **`agent-brain-uds` smoke test version assertion loosened** from a hardcoded `__version__ == "10.0.7"` to a `MAJOR.MINOR.PATCH` regex. The hardcoded check was Phase 0 placeholder code and silently broke at v10.1.0 (because the per-package `task uds:before-push` wasn't yet wired into root, so CI never ran it). Caught by Plan 55-05's standalone `task uds:before-push` invocation.

### Roadmap

The v10.2 MCP v2 surface deliberately defers several capabilities to MCP v3 (#187) and MCP v4 (#188):

- **MCP v3** — CLI-via-MCP (`agent-brain --transport mcp`), framework integration matrix (OpenAI Agents SDK, LangChain, LlamaIndex, Pydantic AI, Mastra, Vercel AI SDK, Autogen), `/mcp/subscriptions/__debug` observability endpoint ([#194](https://github.com/SpillwaveSolutions/agent-brain/issues/194) — currently log-scraped per Phase 55 Plan 03).
- **MCP v4** — OAuth 2.1 for the HTTP transport (PRM, DCR, Resource Indicators, optional DPoP). v10.2's HTTP transport is loopback-only as a result.

### Validation

- VAL-01 (16-tool contract) → 32 SDK assertions over stdio + 6 over HTTP; Layer 1 in-process 16-row matrix shares one SOT.
- VAL-02 (subscription E2E) → 4 SDK-driven tests; disconnect-cleanup via raw `subprocess.Popen` EOF path + stderr-log scrape per CONTEXT D-06; follow-up #194 filed.
- VAL-03 (HTTP transport SDK test) → 5 SDK contract tests + 1 mount-path sanity pin via `mcp.client.streamable_http.streamablehttp_client`.
- VAL-04 (root QA gate integration) → `task before-push` exit 0 in 160s; `task pr-qa-gate` exit 0 in 152s; `task check:layering` 3 contracts kept (164 files / 414 deps). Per-package coverage: agent-brain-mcp 91.83%, agent-brain-uds 99%. Phase 55 `VALIDATION.md` at `.planning/phases/55-validation-and-qa-gate/VALIDATION.md`.

---

## [10.1.2] - 2026-05-29

### Fixed

- **PyPI publish completes for all four packages after pending publishers were registered.** v10.1.0 and v10.1.1 each failed at the new-package publish step because the projects had not been pre-registered for Trusted Publisher OIDC on PyPI. `agent-brain-mcp` additionally hit PyPI's typosquatting filter (similar to existing `agentbrain-mcp` 0.2.0) and was renamed to **`agent-brain-ag-mcp`** as its PyPI distribution name. The MCP `agent-brain-mcp` CLI command and Python import path stay unchanged — only the `pip install` string differs (`pip install agent-brain-ag-mcp` now). No functional changes vs the 10.1.1 design.

---

## [10.1.1] - 2026-05-29

### Fixed

- **PyPI publish workflow now handles the 4-package monorepo bootstrap.** The `publish-to-pypi` quality gate's `Install CLI` step had a `sed` flip for the `agent-brain-rag` path-dep but no equivalent for the new `agent-brain-uds` PyPI pin shipped in CLI 10.1.0; `Install MCP` was missing entirely. The 10.1.0 release tag triggered the workflow, the quality gate failed at the CLI install step, and no packages were published. 10.1.1 carries the workflow fix only — extending both Install steps to flip `agent-brain-rag` AND `agent-brain-uds` path-deps so all four packages resolve during quality gate, plus an Install MCP step for symmetry. Functional surface is byte-identical to the 10.1.0 design (see entry below). v10.1.0 tag is preserved as a historical marker but holds no PyPI artifacts.

---

## [10.1.0] - 2026-05-29

### Added

- **Unix-domain-socket transport (`agent-brain-uds`)** — new client-only package (`agent-brain-uds/`) shipping a `socket-path resolver`, an `httpx.HTTPTransport(uds=...)` client factory (`make_client` / `make_async_client`), and an adversarial permission validator (`validate_socket`). The validator enforces the full local-trust model in one place: rejects symlinked socket paths via `os.lstat`, rejects sockets with any group/world permission bits set, rejects cross-UID ownership, requires `0700` on the parent directory, and (Phase 5) hardens the long-path pointer-file fallback by rejecting symlinked pointers, non-regular pointer files, embedded null bytes, and relative paths before `read_text` parses anything attacker-controlled. The server-side bind helper (`agent_brain_server/api/uds_bind.py`) runs two `uvicorn.Server` instances on the shared asyncio loop — one bound to TCP, one to AF_UNIX — and atomically cleans up the socket on `SIGTERM`. The dual-bind pattern was validated by `scripts/spike_dual_bind.py` before any production code shipped, with documented fallback to a separate `--uds-only` process if uvicorn's `(host,port)` ↔ `uds` mutual-exclusion ever changes. `RuntimeState.socket_path` is a new optional field; runtime.json files written by older releases still parse. New `agent-brain start --uds` and `--uds-only` CLI flags toggle the bind mode; `AGENT_BRAIN_UDS=1` / `AGENT_BRAIN_UDS_ONLY=1` / `AGENT_BRAIN_UDS_PATH` provide the env-var equivalents. 32 tests across `agent-brain-uds/tests/` (98.56% coverage) cover the 5 socket-path resolver branches, the pointer-file roundtrip, the full adversarial permission matrix, and an end-to-end client/server roundtrip against a stub uvicorn UDS server.

- **CLI transport selector (`agent-brain --transport {auto,http,uds}`)** — every command now opens its `DocServeClient` through `agent_brain_cli/client/transport.py::open_client(ctx)`, which reads four new root-group options (`--transport`, `--socket-path`, `--base-url`, `--debug-transport`) plus the `AGENT_BRAIN_TRANSPORT` env var. Resolution precedence: explicit flag → env var → `runtime.json::socket_path` (UDS) or `base_url` (HTTP) → defaults. `--transport auto` (the default) tries UDS first when a validated socket is present and falls back to HTTP loudly — never silently. `DocServeClient.from_httpx(client)` is a new classmethod that lets callers inject a pre-configured `httpx.Client` (UDS or HTTP) without re-deriving a base URL. `--transport uds` against a missing/invalid socket raises with the specific `SocketPermissionError` remediation rather than hanging on a TCP retry. Every existing CLI command (`status`, `query`, `index`, `reset`, `cache`, `jobs`, `inject`, `folders`) was refactored to `open_client(ctx)` with no behavioral change in HTTP mode; existing CLI tests stay green under both transports.

- **MCP server (`agent-brain-mcp`)** — new stdio-only Model Context Protocol server (`agent-brain-mcp/`) implementing the v1 surface the plan committed to: **7 tools, 5 read-only resources, 6 prompts**. The server speaks MCP to the LLM client and HTTP (or UDS) to the Agent Brain backend via `agent_brain_mcp/config.py::open_backend_client(...)`, which selects transport via `--backend {auto,uds,http}` / `AGENT_BRAIN_MCP_BACKEND`. A startup version-compat check (`check_backend_version`) refuses to start when the backend `/health/` reports a `version` below the floor pinned at `MIN_BACKEND_VERSION = "10.0.7"` (plan §12.3 #14). The 7 tools (`search_documents`, `query_count`, `index_folder`, `get_job`, `list_jobs`, `cancel_job`, `server_health`) each return both a human-readable `content` block and a structured `structuredContent` payload with declared `outputSchema` generated via `pydantic.TypeAdapter`. `cancel_job` enforces a destructive-operation gate as a *required input-schema field* (`confirm: Literal[True]`), not via an annotation — the JSON-Schema validation rejects `{"confirm": false}` or absence with `-32602 InvalidParams` before the handler runs. The 5 resources (`corpus://config`, `corpus://status`, `corpus://health`, `corpus://providers`, `corpus://folders`) are read-on-demand (`resources.subscribe: false` in v1) and map 1:1 to existing `/health/*` and `/index/folders/` endpoints. The 6 prompts (`find-callers`, `find-implementation`, `explain-architecture`, `compare-search-modes`, `onboard-to-codebase`, `audit-indexed-folders`) mirror the most-used plugin commands and validate required arguments before expansion. The 8 HTTP→MCP error-code mappings from plan §6.3 are exhaustively parameterized in `test_error_mapping.py`: 400/404/422 → `-32602`, 409 → `-32000 InvalidRequest`, 500 → `-32603`, 502 → custom `-32001 BackendUnavailable`, 503 → `-32002 ServiceIndexing`, 504 → `-32003 BackendTimeout`; every error carries `data.httpStatus` and `data.cause`. **Phase 5** wraps every tool/resource handler in `asyncio.to_thread` so the asyncio event loop stays responsive while sync `httpx` calls are in flight — making MCP `notifications/cancelled` actually propagate (plan §6.4 / §12.3 #12) and two concurrent tool calls overlap instead of serializing. 70 unit/integration tests + 4 official-MCP-Python-SDK subprocess e2e tests (86.70% coverage). The MCP server installs as `agent-brain-mcp` and is intended to be wired into Claude Desktop / Code via `"mcpServers": {"agent-brain": {"command": "agent-brain-mcp", "args": ["--backend", "auto"]}}`. See `docs/USER_GUIDE.md` "Using Agent Brain via MCP" for the full config.

- **`GET /health/config` endpoint + `ConfigStatus` model** (`agent_brain_server/api/routers/health.py`, `agent_brain_server/models/health.py`). Returns the active storage backend (`chroma` / `postgres`), which stores are enabled (vector / BM25 / graph), the active embedding + rerank model names, the graph extractor provider, and whether the file watcher is running. The shape mirrors *configuration* (static across the run), not runtime stats (those stay in `/health/status`). The MCP `corpus://config` resource is the primary consumer; this is also the first endpoint the MCP server hits at startup for its version-compat check. Reflects `AGENT_BRAIN_STORAGE_BACKEND` env override.

- **Import-linter contracts (`.importlinter` + `task check:layering`)** locking the four-package dependency direction: `agent_brain_server` MUST NOT import upward (no `agent_brain_uds`, `_mcp`, `_cli`); `agent_brain_uds` may only touch `agent_brain_server.models`; `agent_brain_mcp` MUST NOT call `agent_brain_server.services`/`api`/`indexing`/`storage` (all backend calls go through HTTP/UDS via the shared client). Verified by a one-shot manual test (plan §12.3 #15): temporarily adding `import agent_brain_cli` to `agent_brain_server/api/main.py` makes `lint-imports` exit 201 with `server has no upward deps BROKEN`.

### Roadmap

The MCP v1 surface deliberately defers several capabilities so each can land with its own design doc. Tracking issues are filed alongside this release:

- **MCP v2** — `resources/subscribe` capability + the 2 deferred URI schemes (`chunk://<id>`, `graph-entity://<type>/<id>` — both need new server endpoints) + Streamable HTTP MCP transport + `wait_for_job` with progress notifications + the remaining 9 deferred tools (`explain_result`, `add_documents`, `inject_documents`, `wait_for_job`, `list_folders`, `remove_folder`, `cache_status`, `clear_cache`, `list_file_types`). Roadmap body: `docs/roadmaps/mcp/v2-subscriptions-and-resources.md`.
- **MCP v3** — CLI-via-MCP (`agent-brain --transport mcp`) + framework integration matrix (OpenAI Agents SDK, LangChain, LlamaIndex, Pydantic AI, Mastra, Vercel AI SDK, Autogen) + `docs/INTEGRATIONS.md`. Roadmap body: `docs/roadmaps/mcp/v3-cli-via-mcp-and-frameworks.md`.
- **MCP v4** — OAuth 2.1 for remote Agent Brain instances (Protected Resource Metadata, Dynamic Client Registration, Resource Indicators, DPoP optional). Roadmap body: `docs/roadmaps/mcp/v4-oauth-for-remote.md`.

### Internal

- **Phased delivery + TDD discipline** — six PR-sized phases on `feat/mcp-uds-transport`: Phase 0 scaffold + import-linter contracts, Phase 1 UDS package + dual-bind spike, Phase 2 server-side UDS + `/health/config`, Phase 3 CLI transport selector, Phase 4 MCP v1 surface, Phase 5 cancellation + pointer-file hardening, Phase 6 docs + ship. Every phase landed RED → GREEN where applicable, with per-package `task uds:pr-qa-gate` / `task mcp:pr-qa-gate` gates in addition to root `task before-push`. New packages deliberately not yet added to root `task before-push` / `task pr-qa-gate` (matches `docs/plans/2026-mcp-server-design.md` precedent); they fold into the root gate after 10.1.0 ships green and one release cycle elapses.

- **Plan supersedence** — `docs/plans/2026-mcp-server-design.md` was the original design-only scoping artifact; replaced by `docs/plans/2026-05-28-mcp-uds-transport-design.md` which adds UDS, narrows the MCP surface to a v1 that ships, and documents the v2/v3/v4 roadmap.

### Query / Retrieval

- **Opt-in `explain=true` query parameter** (`agent_brain_server/models/query.py`, `agent_brain_server/services/query_service.py`, `agent_brain_server/api/routers/query.py`, `agent_brain_server/storage/protocol.py`, `agent_brain_server/storage/chroma/backend.py`, `agent_brain_server/storage/postgres/keyword_ops.py`). When the client sends `{"explain": true}` on `POST /query`, each result now carries a structured `explanation` block: a deterministic "why this rank" `reason` string, the BM25 `matched_terms` that hit the document, a `fusion` breakdown for hybrid/multi modes (per-retriever weighted scores or RRF ranks), the `graph_path` for graph contributors, and the signed `rerank_movement` when reranking fired. Default (`explain=false`) keeps the wire format byte-identical to historical responses — the field is *excluded* from serialization, not present-with-null. The retriever handlers stash intermediate fusion data in a transient `metadata["_explain_scratch"]` dict that the final drain pass clears before the response is built, so the scratch never leaks. The cache is bypassed for `explain=true` requests so cached responses can't serve stale explanations across request shapes. `SearchResult` gained an optional `matched_terms` field; the Chroma BM25 backend uses `bm25s.tokenize` (mirroring LlamaIndex BM25Retriever's tokenizer — lowercase + English stopword strip, no stemmer) to produce the intersection, while the Postgres backend uses `ts_headline()` with a `<<<...>>>` sentinel wrapper parsed back into a deduplicated list. A new `--explain` flag on `agent-brain query` surfaces the same payload as a Rich sub-panel beneath each result, with matched terms highlighted in bold yellow. 41 new tests cover the wire-format contract (4), service-layer builder priority order and per-mode payload assembly (21), storage-tier tokenization/headline parsing (14), CLI rendering (5), and rerank-movement annotation (2 end-to-end). Closes #159.

---

## [10.0.7] - 2026-05-27

### Fixed

- **Vector store and BM25 manager singletons now converge with the lifespan-registered instance** (`agent_brain_server/storage/vector_store.py`, `agent_brain_server/indexing/bm25_index.py`, `agent_brain_server/api/main.py`). The FastAPI lifespan correctly resolved `chroma_db/` and `bm25_index/` paths under `AGENT_BRAIN_STATE_DIR` and stored the configured managers in `app.state`, but the module-level singletons (`_vector_store`, `_bm25_manager`) were never updated. Any caller that pulled through `get_vector_store()` or `get_bm25_manager()` — including `IndexingService`, `QueryService`, and `ChromaBackend` — constructed a *separate* manager that fell back to the CWD-relative defaults `./chroma_db` and `./bm25_index`, leaking a stray `chroma_db/` directory next to the project root and (in the worst case) writing to a different ChromaDB than the lifespan registered. Fix: new `set_vector_store(instance)` and `set_bm25_manager(instance)` helpers that the lifespan now calls after construction, so the singleton and `app.state.*` point at the same state-dir-resolved manager. The unset-getter path emits a clear WARNING ("called before set_*; using CWD-relative default …") so silent fallbacks become visible in tests and dev runs. The lifespan also performs a startup `_warn_about_stray_cwd_data_dirs(state_dir)` check that detects `./chroma_db`, `./bm25_index`, and `./graph_index` directories at CWD from pre-fix releases and logs the canonical path plus a manual `rm -rf` command — no silent migration, because the stray directory may hold real embedding work. The legacy `CHROMA_PERSIST_DIR = "./chroma_db"` and `BM25_INDEX_PATH = "./bm25_index"` defaults in `config/settings.py:34-35` are deliberately preserved as documented fallbacks for ad-hoc scripts and unit tests; the fix lives in the wiring, not the defaults. Eight regression tests in `tests/unit/test_issue_170_singleton_path_resolution.py` lock the setter-then-getter convergence, the unset-getter warning, the stray-dir warning under three CWD shapes, and a source-level assertion that `main.py` still calls the setters. Closes #170.

### Internal

- **Planning artifact drift caught up with v10.0.x reality.** `.planning/STATE.md` had been pinned at `v9.6.0 / Phase 46` since 2026-04-01 even though releases v9.3.0 → v10.0.6 had shipped in the intervening eight weeks. Audited `.planning/todos/pending/` — seven of ten entries were demonstrably resolved by code already in `main` (Gemini → `google-genai` migration in `b19ab35`; ChromaDB telemetry suppression at `api/main.py:167-169`; `agent-brain start --timeout` default raised 30s → 120s at `start.py:166-169`; Ollama broken-pipe retry at `providers/embedding/ollama.py:88`; AST + LangExtract first-class config wizard option at `agent-brain-config.md:590-592` from v9.3.0; port auto-discover documented at `agent-brain-start.md:58,275`; Object Pascal language support shipped via direct commits `de34cd0`, `4777890`). Each archived file in `.planning/todos/done/` now carries `status: closed`, `closed_at`, and `closed_by_release` frontmatter plus a one-line audit-trail blockquote at the top of the body. `STATE.md` rewritten to reflect the v10.0.x patch train (graph durability, Kuzu resilience, doctor diagnostic) and to mark the v9.6.0 runtime-parity milestone as parked. The three genuinely-still-open items were promoted to GitHub issues with bidirectional cross-references: **#170** (this release's fix), **#171** (verify-and-close — pre-authorize setup-assistant across six setup commands; static inspection confirmed all six already carry `context: fork` + `agent: setup-assistant`), and **#172** (verify-and-close — setup-assistant Bash/Write/Edit permission scopes; confirmed present at `agent-brain-plugin/agents/setup-assistant.md:23-33`, `last_validated` refreshed). The three remaining `.planning/todos/pending/` files each gained a `Tracked in: #NNN` blockquote linking back to the corresponding issue. Plan archived at `docs/plans/2026-05-27-low-hanging-fruit-triage.md`.

---

## [10.0.6] - 2026-05-26

### Fixed

- **Kuzu graph store now self-heals from kill-mid-write corruption.** When the server was killed (SIGKILL or even SIGTERM) during the `langextract` triplet phase, the on-disk Kuzu catalog at `.agent-brain/data/graph_index/kuzu_db` could enter a state where `kuzu.Database(path)` raises `IndexError: unordered_map::at: key not found` from the pybind11 C++ constructor — every subsequent `agent-brain index` job then failed instantly inside `_initialize_kuzu_store` with no actionable recovery hint. Manual `rm kuzu_db` worked but destroyed all previously-extracted triplets (real `gpt-4o-mini` API spend). `_initialize_kuzu_store` in `agent_brain_server/storage/graph_store.py` now wraps `kuzu.Database()` in defensive `try/except (IndexError, RuntimeError)`. On catch it logs a loud actionable WARN, quarantines `kuzu_db` (and `kuzu_db.wal`) to `.corrupted-<ts>` sibling files (never deletes — forensic preservation), then retries on the now-empty path. A second failure raises a structured `RuntimeError` with explicit reset instructions. The lifespan in `agent_brain_server/api/main.py` calls a new `preflight_check()` at startup so corruption is detected once at boot rather than on the first user-facing indexing job. Same shape as the existing `#151` stale-directory self-heal pattern. Cross-reference: upstream [kuzudb/kuzu#6020](https://github.com/kuzudb/kuzu/issues/6020) tracks the catalog-load fragility on a different code path. Closes #166.

### Added

- **Triplet snapshots during langextract** (`agent_brain_server/storage/graph_snapshot.py` + hook in `agent_brain_server/indexing/graph_index.py`). `build_from_documents` now writes JSON triplet snapshots to `<graph_index>/snapshots/snapshot-<ISO8601>.json` on a hybrid cadence — whenever either `GRAPH_SNAPSHOT_CHUNKS` chunks (default 25) OR `GRAPH_SNAPSHOT_INTERVAL_SEC` seconds (default 60) have elapsed — plus a final tail snapshot at end-of-build. Rotation keeps the `GRAPH_SNAPSHOT_KEEP` most recent (default 3). Writes are atomic (`tmp + os.fsync + os.replace`). When the corruption-recovery path detects a quarantined Kuzu DB, it walks newest-to-oldest snapshots (skipping any that themselves got corrupted) and replays the triplets into the fresh database — silently restoring previously-extracted work with a single WARN log line. Snapshot write failure is non-fatal (a disk-full `OSError` logs WARN and indexing continues; the snapshot is a safety net, not a critical path). New env-var settings: `GRAPH_SNAPSHOT_CHUNKS`, `GRAPH_SNAPSHOT_INTERVAL_SEC`, `GRAPH_SNAPSHOT_KEEP`.
- **`agent-brain doctor` now checks Kuzu DB health** (`agent_brain_cli/agent_brain_cli/diagnostics.py`). When GraphRAG is enabled with `store_type: kuzu`, the new `graph_store_health` check briefly opens `kuzu_db` in-process and reports OK / FAIL with an actionable fix hint. `agent-brain doctor --fix` extends to recover a corrupted Kuzu DB offline: refuses to run while a `server.lock` exists (avoids racing the live server), quarantines `kuzu_db` + `kuzu_db.wal` to `.corrupted-<ts>` siblings, and replays the newest valid triplet snapshot into a fresh DB. The CLI peeks at `config.yaml` directly for the `graphrag` block since `AgentBrainConfig` doesn't model graphrag (server concern). Closes the remaining graph DB durability gap from `#146`.

### Internal

- Server-side snapshot manager (`GraphSnapshotManager`) is deliberately backend-agnostic — operates on plain `SnapshotTriplet` dataclasses, never imports Kuzu directly. Same module could later snapshot SimplePropertyGraphStore. Loads sort snapshots by mtime (with filename tie-break) rather than filename alone — collision-suffixed names like `snapshot-T-001.json` sort *before* `snapshot-T.json` lexically, the wrong direction for "newest first". Test coverage: 36 new unit tests across `tests/unit/storage/test_graph_snapshot.py` (write/list/load/rotate lifecycle, corruption handling), `tests/unit/storage/test_graph_store_recovery.py` (defensive recovery state machine with a mocked Kuzu), and `tests/unit/test_graph_index_snapshot.py` (hybrid-cadence hook). Five new doctor tests in `agent-brain-cli/tests/test_resolver_and_doctor.py`.

---

## [10.0.5] - 2026-05-26

### Fixed

- **Graph search with Anthropic summarization now works out of the box.** When `graphrag.enabled: true` and `summarization.provider: anthropic`, `LangExtractExtractor` silently produced zero triplets per chunk because Claude model ids (`claude-haiku-4-5-…`, etc.) are not in `langextract`'s provider registry — the per-chunk WARNING that should have surfaced the failure used `logger.warning(..., extra={"error": ...})`, which the default formatter does not render. Three layers of fix in `agent_brain_server/indexing/graph_extractors.py`: (a) when `summarization.provider` is anthropic / claude and no explicit `graphrag.langextract_{provider,model}` override is configured, the extractor auto-routes to `openai/gpt-4o-mini` with a clear INFO log; (b) startup-time validation now calls `langextract.providers.router.resolve(model_id)` and raises a `ConfigurationError` naming the YAML keys to set when the resolved model would be rejected; (c) the per-chunk WARNING now interpolates the underlying error text via `%s` so it shows in any default-formatted log. Also fixed two latent bugs surfaced by the new validation: `_resolve_model_id`'s ollama default (`ollama/llama3.1:8b`) was always rejected by langextract — switched to the bare `llama3.1:8b` form; and `self.model` no longer inherits `summarization.model` when the caller passed an explicit `provider=` (the cross-wiring made `LangExtractExtractor(provider="ollama")` resolve to a Claude model in the wild). `langextract_provider` and `langextract_model` are now documented in `agent-brain-plugin/skills/configuring-agent-brain/SKILL.md` and `docs/GRAPHRAG_GUIDE.md`. Closes #149.
- `agent-brain jobs <job_id>` no longer crashes with `TypeError: unsupported format string passed to dict.__format__` when the server returns a structured `JobProgress` payload (the default since the job-queue rework — `progress` is a dict with `percent_complete`, `files_processed`, `files_total`, `chunks_created`, `current_file`). The CLI assumed a float and used `f"{progress:.1f}%"` unconditionally on `jobs.py:33,34,126,129`. `_format_progress` was rewritten to dispatch on type — extracts `percent_complete` from the structured dict, falls back to a `key=value` pretty-print for unknown dicts, keeps the legacy float path, and coerces unknown types to `str(...)` rather than raising. The detail view (`_create_job_detail_panel`) now centralizes formatting through the same helper so list view and detail view never diverge. New regression suite in `agent-brain-cli/tests/test_jobs_progress.py` pins each input shape, including the exact failing payload from the issue. Closes #150.
- Kuzu graph-store initialization now self-heals when a stale empty `kuzu_db/` directory is left over from a v10.0.2 upgrade. Pre-v10.0.4 created `kuzu_db/` as a directory; v10.0.4's `#144` fix expects either no path or a kuzu single-file database there, so the upgrade path raised `RuntimeError: Database path cannot be a directory: …/kuzu_db` on the first indexing job. `_initialize_kuzu_store` in `agent_brain_server/storage/graph_store.py` now `rmdir()`s an empty stale dir before opening (only succeeds on empty dirs — safe), and raises a clearer `RuntimeError` that names the directory + suggests `GRAPH_INDEX_PATH` if the leftover is non-empty (never silently deletes user data). Two regression tests in `tests/integration/test_kuzu_graph_e2e.py` pin both paths. Closes #151.

### Added

- `agent-brain doctor` gained the `--fix` flag for safe, idempotent, offline remediations: appends `.agent-brain/` to `.gitignore` (creating it if missing) and creates a stub state dir + `config.json` when the project is uninitialized. The doctor report re-runs after fixing so the printed table reflects the new state. Network calls, API keys, and user code are explicitly off-limits — those still require manual action. Closes part of #146.
- `agent-brain doctor` now reports the installed `agent-brain-cli` version as its own check (catches broken installs at the top of the report instead of letting the user discover them later), and explains *which* rule selected the project root (`.agent-brain/` match, git top-level, `.claude/` marker, etc.) on monorepos. When the server is reachable, the server check additionally pulls `/health/status` and surfaces a one-line indexing summary (state + chunk count). When `graphrag.enabled: true`, doctor checks that `langextract` is importable and hints at the `[graphrag]` extra if not. Closes #146.

### Internal

- `resolve_project_root` in `agent_brain_cli/config.py` now has a sibling `resolve_project_root_with_strategy()` that returns `(root, strategy_label)` — the strategy is a stable identifier (`agent_brain_dir`, `git_root`, `pyproject`, etc.) for use by `agent-brain doctor`. The original signature is unchanged and now delegates to the new function.
- Confirmed via codebase audit that issue #147 (auto-suggest doctor on connection failures) was already implemented end-to-end in v10.0.4: all five commands (`status`, `query`, `jobs`, `index`, `reset`) import `doctor_hint_message` from `agent_brain_cli.diagnostics` and print it on `ConnectionError`, and the helper already distinguishes "no runtime.json found" from "server unreachable." Closed with evidence; no code change in this release.

---

## [10.0.4] - 2026-05-26

### Fixed

- **Graph search with Kuzu now works.** The `--mode graph` retrieval path had been silently broken since the `llama-index-graph-stores-kuzu` package bumped to `>=0.9.0`, which renamed the `KuzuGraphStore` constructor parameters and removed the legacy positional signature Agent Brain was passing. Indexing in graph mode raised `TypeError: __init__() got an unexpected keyword argument` and the server fell back to vector-only retrieval without surfacing the failure. The constructor call in `agent_brain_server/storage/graph_store.py` has been migrated to the new keyword-only API (`db_path=`, plus optional `node_table_name`/`rel_table_name`), the optional dependency pin in `agent-brain-server/pyproject.toml` has been raised to `^0.9.0`, and an integration test exercises a full graph-mode index + query cycle so the regression cannot reoccur. Closes #144.
- `exclude_patterns` now uses gitignore-style glob semantics via the `pathspec` library instead of naive substring matching. Previously a pattern like `**/node_modules/**` matched only paths that literally contained the string `**/node_modules/**`, so users had to enumerate every level (`node_modules/**`, `*/node_modules/**`, ...) to get the same effect they get from `.gitignore`. The matcher in `agent_brain_server/indexing/document_loader.py` was rewritten to compile patterns through `pathspec.PathSpec.from_lines("gitwildmatch", ...)`, which gives the same precedence and wildcard rules as Git. `pathspec` is now a required dependency. Existing simple patterns (`*.log`, `__pycache__`) continue to work unchanged. Closes #142.
- BM25 indexing no longer crashes when a folder produces zero indexable chunks (e.g., a directory of only binary files, or a folder where every file is filtered out by `exclude_patterns`). `BM25Retriever.from_defaults([])` raises `ValueError: docstore must contain at least one node` in `llama-index-retrievers-bm25`, which propagated as a 500 from `/index` and aborted the whole queued job. `agent_brain_server/services/indexing_service.py` now short-circuits before constructing the retriever, logs a `WARNING` with the folder path, marks the job `completed` with `indexed_count=0`, and returns. The vector store path was already a no-op in this case, so behavior is now consistent across backends. Closes #143.

### Internal

- Removed a duplicate `resolve_project_root()` definition in `agent_brain_cli/commands/stop.py` that shadowed the shared implementation in `agent_brain_cli.utils.project`. The shadow had drifted: it silently returned `Path.cwd()` when no `.agent-brain/` marker was found, whereas the canonical version walks up the tree and raises a clear error. Behavior of `agent-brain stop` outside an initialized project is now consistent with `start`/`status`/`list`. Closes #131.

## [10.0.3] - 2026-05-26

### Fixed

- Multi-page PDF indexing silently lost data because `chunk_id` was derived from only `(source, idx)`. Every page reset `idx` to 0, so chunks collided and ChromaDB's upsert kept only the last page (a 128-page PDF was indexed as only a handful of chunks, all from later pages). The collisions were masked by a last-occurrence-wins dedupe in `vector_store.py` with only a server-log warning. Fix: `DocumentLoader` now preserves the per-part identifier PyMuPDFReader sets in `metadata["source"]` as `page_label`, and both `chunking.py` and the `CodeChunker` mix `page_label` into the id_seed when present (using `#` as a URL-fragment-style separator so filenames like `foo.pdf_3` cannot collide with `foo.pdf#3_0`). Non-PDF sources without `page_label` keep the legacy `f"{source}_{idx}"` seed, so already-indexed corpora are unaffected. Includes new regression suite `tests/unit/test_chunk_id_uniqueness.py` covering disjoint IDs across pages, legacy-formula backwards compat, and stability across re-indexing. Closes #141.

## [10.0.2] - 2026-05-25

### Fixed

- Release automation now refuses to proceed if `docs/CHANGELOG.md` is missing an entry for the new version. Previously the release agent silently shipped without updating the CHANGELOG, requiring a post-release docs catchup commit each time (see PR #139 for v10.0.1). The new pre-release check (Check #6 in `.claude/agents/release_agent.md`, Check #5 in `.claude/commands/ag-brain-release.md`) computes the target version from the bump type and greps `docs/CHANGELOG.md` for a matching `## [X.Y.Z]` heading. On failure it aborts with a clear instruction to add the section and commit before re-running. Same root cause as #135 (release agent's documented contract diverging from automation) — now resolved structurally. Closes #138.

### Internal

- This v10.0.2 CHANGELOG entry self-demonstrates the new check: the release that ships it is the first release to actually run the check, and it will validate its own existence in `docs/CHANGELOG.md` before proceeding.

## [10.0.1] - 2026-05-25

### Fixed

- `scripts/quick_start_guide.sh` was silently broken since v9.0.0 — line 68 still invoked the legacy `doc-serve` binary (renamed to `agent-brain-serve` in v9.0.0) and the script's exported `DOC_SERVE_URL` env var was no longer read by the modern CLI. The script is cited as a mandatory pre-release gate in `.claude/CLAUDE.md`, so the gate had been effectively bypassed for the entire v9.x line. Replaced the binary call, updated three echo banners from "Doc-Serve" to "Agent Brain", and renamed `DOC_SERVE_URL` to `AGENT_BRAIN_URL`. Closes #134.
- Release automation now bumps `agent-brain-plugin/.claude-plugin/plugin.json` in lockstep with `pyproject.toml` and `__init__.py` files. The release agent's documented contract required the plugin manifest to match (line 119) but its actual step list only enumerated 4 files, requiring a manual catchup commit each release (see `4997007` for v10.0.0). Both `.claude/agents/release_agent.md` and `.claude/commands/ag-brain-release.md` now list 5 files. The v10.0.1 release commit (`fc8f9bb`) is the first to bump `plugin.json` automatically. Closes #135.

### Internal

- Identified `.claude/commands/ag-brain-release.md` as the runtime source of truth for the release slash command — its "Task" section is what the skill follows, not the duplicate file list in the agent definition. PR #137 was needed because PR #136 only updated the agent file.

## [10.0.0] - 2026-05-25

### Breaking

- `cohere` is now an optional extra. Install with `pip install 'agent-brain-rag[cohere]'` to use the Cohere provider. Without the extra, selecting cohere raises a clear `ImportError` with install hint. Closes #122, #125.

### Added

- `agent-brain doctor` CLI command — checks Python version, project init, provider config, required API keys, optional deps (`cohere`/`langextract`), `.gitignore` hygiene, and server reachability. Supports `--json` and exits non-zero on critical failures.
- Connect-time hints — when `status`, `query`, `jobs`, `index`, `reset` hit `ConnectionError`, they now print a context-sensitive tip pointing at `agent-brain doctor` or the missing `runtime.json`.
- Plugin delegation — `ab-setup-check.sh` now calls `agent-brain doctor --json` when the CLI is installed.

### Fixed

- File watcher infinite re-index loop — `.agent-brain/` and `.claude/` added to `AgentBrainWatchFilter`'s ignore_dirs. Closes #123.
- Monorepo project-root resolver — CLI/server walked past nested `.agent-brain/` to the git root in mono-repos, so `status` always queried port 8000. Unified four duplicate project-root resolvers; check for a local state dir before consulting git. Closes #124, #128.
- `graphrag:` YAML section was silently ignored — added `GraphRAGConfig` Pydantic model + `get_graphrag_config()` accessor that merges YAML over env-var defaults. Graph index dir resolved under `{state_dir}/data/graph_index` instead of CWD. Closes #126.
- `langextract` 1.x migration — `extract_relations` removed from the public API; migrated `LangExtractExtractor` to `lx.extract()` with a prompt + few-shot examples, kept a legacy fallback path, stopped swallowing `AttributeError` as "not installed." Closes #129.
- `tiktoken` rejected `<|endoftext|>` literals in indexed text — added `ALLOW_SPECIAL_TOKENS_IN_TEXT` (on by default) and a `_safe_token_count` helper used by every `encode()` call in chunking. Closes #114.

### Performance

- Prune excluded dirs during traversal instead of after walking them — significantly faster indexing on large trees with deep ignore patterns. Closes #127.

### Internal

- Test-isolation fix — `isolate_provider_settings` autouse fixture now honors `AGENT_BRAIN_CONFIG` env-var overrides while still blocking home/XDG/walk-up YAML lookups. Unblocked CI on the pgvector contract/integration/load test suites that had been erroring with `column cannot have more than 2000 dimensions for hnsw index`.
- CI — `provider-e2e.yml` workflow now installs the `[cohere]` extra so the cohere matrix step works after the cohere-is-optional change.

---

## [9.6.0] - 2026-04-03

### Added

- Repo-owned runtime parity harness workspaces under `e2e_workdir/`
- Shared shell helpers for E2E workspace lifecycle, reporting, and runtime install verification
- Structured runtime parity failure payloads with remediation guidance
- OpenCode global scope mutation regression coverage

### Changed

- Runtime parity plumbing now uses runtime-specific `<runtime>-runtime/` directories with `cleanup/` and `logs/`
- E2E runtime documentation now describes the verification contract: structure check, install JSON validation, then dry JSON probe

### Fixed

- Prevented runtime parity installs from silently targeting forbidden global runtime paths
- Fixed workspace cleanup so only disposable runtime `project/` trees are removed on success

---

## [3.0.0] - 2026-02-03

### Added

**Server-Side Job Queue:**
- JobQueueStore with JSONL persistence and file locking
- JobWorker background processor with timeout handling
- JobQueueService with deduplication and backpressure
- New endpoints: GET /index/jobs/, GET /index/jobs/{id}, DELETE /index/jobs/{id}

**CLI Jobs Command:**
- `agent-brain jobs` - List all jobs in queue
- `agent-brain jobs --watch` - Watch queue with live Rich table updates
- `agent-brain jobs JOB_ID` - Show detailed job information
- `agent-brain jobs JOB_ID --cancel` - Cancel a pending or running job

**Runtime Autodiscovery:**
- CLI config module reads runtime.json for automatic server URL discovery
- Foreground mode now writes runtime.json before exec
- Config resolution order: AGENT_BRAIN_URL > runtime.json > config.yaml > default:8000

**Integration Testing:**
- Local integration check script: `scripts/local_integration_check.sh`
- Validates runtime.json creation, job completion, and query functionality
- Added `task local-integration` to Taskfile

### Changed

**Breaking API Changes:**
- POST /index now returns 202 Accepted with job_id (was blocking)
- POST /index/add now returns 202 Accepted with job_id
- Response includes queue_position, queue_length, dedupe_hit

**Version Bump:**
- Major version increment from 2.0.0 to 3.0.0 due to API contract change

### Fixed

- BM25 top_k capping for small corpus
- Runtime.json race condition in foreground mode
- Jobs endpoint trailing slash consistency
- locking.py no longer incorrectly deletes runtime.json

### Removed

- `--daemon` flag (server backgrounds by default)

### Runtime.json Expectations

Both foreground and background modes write runtime.json before the server starts:

```json
{
  "base_url": "http://127.0.0.1:49321",
  "port": 49321,
  "bind_host": "127.0.0.1",
  "pid": 12345,
  "started_at": "2026-02-03T10:00:00Z",
  "foreground": false
}
```

Location: `.claude/agent-brain/runtime.json`

### CLI Resolution Order

The CLI resolves server URL in this priority:
1. `AGENT_BRAIN_URL` environment variable
2. `.claude/agent-brain/runtime.json` (searches cwd upward)
3. `config.yaml` (if contains URL)
4. Default: `http://127.0.0.1:8000`

### Migration Notes

**For API Clients:**

If your code waits for indexing completion synchronously, update to poll the job status:

```python
# Before (v2.x)
response = requests.post(f"{url}/index", json={"folder_path": "/docs"})
# Blocking - returns when done

# After (v3.x)
response = requests.post(f"{url}/index", json={"folder_path": "/docs"})
job_id = response.json()["job_id"]

# Poll for completion
while True:
    status = requests.get(f"{url}/index/jobs/{job_id}").json()
    if status["status"] in ["done", "failed", "cancelled"]:
        break
    time.sleep(2)
```

**For CLI Users:**

No changes required. The `agent-brain index` command works as before but now returns immediately with a job ID. Use `agent-brain jobs --watch` to monitor progress.

---

## [2.0.0] - 2026-01-15

### Added

- GraphRAG integration with knowledge graph search
- Pluggable provider system (OpenAI, Ollama, Cohere, Anthropic, Gemini, Grok)
- Multi-instance support with per-project servers
- AST-aware code chunking for 10+ languages

### Changed

- Renamed from doc-serve to agent-brain
- Default embedding model changed to text-embedding-3-large

### Fixed

- BM25 index persistence across restarts
- Memory leak in large document indexing

---

## [1.2.0] - 2026-01-01

### Added

- Hybrid search mode combining BM25 and vector search
- Alpha parameter for tuning hybrid balance
- Code summarization with LLM

### Changed

- Improved chunk overlap handling
- Better error messages for missing API keys

---

## [1.1.0] - 2025-12-15

### Added

- BM25 keyword search
- Source type filtering (doc/code)
- Language filtering for code queries

### Fixed

- Unicode handling in document parsing
- Path normalization on Windows

---

## [1.0.0] - 2025-12-01

### Added

- Initial release
- Vector-based semantic search
- Document indexing with ChromaDB
- CLI tool with query and index commands
- FastAPI REST API
- Claude Code plugin integration
