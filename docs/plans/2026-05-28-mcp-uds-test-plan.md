# Agent Brain — MCP + UDS v1 Test Plan

**Status:** Draft, drives Phase 2–6 TDD.
**Parent design:** [`2026-05-28-mcp-uds-transport-design.md`](./2026-05-28-mcp-uds-transport-design.md).
**Date:** 2026-05-28.
**Author:** Rick Hightower.

This doc is the test contract for v1. Every line of production code added from Phase 2 onward is preceded by a failing test from one of the suites below. The plan's §12.3 19 functional acceptance items each map to a concrete test file:test_name pair in §7.

---

## 1. Philosophy

1. **TDD throughout.** Iron Law: no production code without a failing test first. Watch RED, write minimal GREEN, refactor green. The `superpowers:test-driven-development` skill applies to every code-producing turn.
2. **Three test rings.** Unit (fast, isolated, ≤ 50ms each), integration (real components, in-process), end-to-end (real processes, real wire protocols, opt-in). Each ring catches a class of bug the others can't.
3. **Each ring owns failures.** A bug found in integration that a unit test could have caught means we backfill the unit test, not just patch the bug.
4. **Adversarial tests are not optional.** Phase 5 dedicates a full day to security-boundary cases. They live alongside the happy paths so a future contributor can't miss them.
5. **Test the wire, not the implementation.** MCP tests use the official MCP Python SDK as the client. CLI tests run real Click subprocesses. UDS tests bind real sockets. We test what users hit.
6. **Stay opt-in for v1.** Per plan DR-1, the new packages have their own `task uds:pr-qa-gate` / `task mcp:pr-qa-gate` / `task mcp:e2e` (slow, optional) tasks. Root `before-push` is unchanged in v1.

---

## 2. Test pyramid for v1

```
                ╱╲
               ╱  ╲   E2E (Phase 4+)
              ╱────╲  - real agent-brain-serve + real agent-brain-mcp
             ╱      ╲ - official MCP SDK as client
            ╱        ╲ - tiny fixture corpus
           ╱──────────╲
          ╱            ╲ Integration
         ╱              ╲ - real uvicorn UDS bind (Phase 2)
        ╱                ╲ - real Click subprocesses (Phase 3)
       ╱                  ╲ - real MCP stdio handshake against fake backend (Phase 4)
      ╱────────────────────╲
     ╱                      ╲ Unit
    ╱                        ╲ - paths/permissions/errors/schemas/models
   ╱                          ╲ - tool/resource/prompt registries
  ╱                            ╲ - error mapping tables
 ╱──────────────────────────────╲
```

Approximate target counts at v1 ship:

| Ring | Package | Count |
|---|---|---|
| Unit | agent-brain-uds | ~28 (28 today, Phase 5 adds adversarial) |
| Unit | agent-brain-server | ~25 (RuntimeState, ConfigStatus, /health/config, uds_bind helpers) |
| Unit | agent-brain-cli | ~12 (transport selector, resolve_transport, debug-transport) |
| Unit | agent-brain-mcp | ~50 (7 tools × {schema, happy, error}, 5 resources × {list, read}, 6 prompts × {list, get}, error mapping, version compat) |
| Integration | agent-brain-server | ~8 (dual-bind, SIGTERM cleanup, /health/config under env override) |
| Integration | agent-brain-cli | ~10 (every command under --transport http vs uds parity) |
| Integration | agent-brain-mcp | ~10 (MCP SDK over stdio against fake backend; subscription-shape checks even though subscribe: false in v1) |
| E2E | agent-brain-mcp | ~6 (full plan §12.2 manual commands automated) |

Total: ~150 tests at v1 ship. Phase 0+1 ship 28.

---

## 3. Phase-by-phase test inventory

### Phase 2 — Server-side UDS bind + `GET /health/config`

**Goal:** wire `agent-brain-server` to honor `--uds` / `--uds-only`, add `socket_path` to `RuntimeState`, ship the `ConfigStatus` model + endpoint that backs `corpus://config`.

| File | Type | Tests | Acceptance |
|---|---|---|---|
| `agent-brain-server/tests/unit/test_runtime_socket_path.py` | unit | `socket_path` defaults to `None`; populates round-trip via `write_runtime`/`read_runtime`; old runtime.json without the field still parses; passing a non-str raises ValidationError | #4 |
| `agent-brain-server/tests/unit/test_models_config_status.py` | unit | `ConfigStatus` rejects unknown values for `storage_backend`; `stores` must include vector/bm25/graph keys; serializes to JSON with documented field names | #16 (data shape) |
| `agent-brain-server/tests/unit/api/test_health_config.py` | unit | `GET /health/config` returns 200; body matches `ConfigStatus.model_json_schema()`; `storage_backend` reflects `AGENT_BRAIN_STORAGE_BACKEND=postgres` env override; `stores.graph` reflects graph index state | #16 |
| `agent-brain-server/tests/unit/api/test_uds_bind_helpers.py` | unit | `serve_uds_only(app, socket_path)` binds a stub app and answers `/health/`; SIGTERM-equivalent (`should_exit = True`) unlinks the socket file; refuses to bind when parent dir absent (errors with actionable msg) | #3 (small slice) |
| `agent-brain-server/tests/integration/test_uds_dual_bind.py` | integration | Boot uvicorn via `serve_dual()` in a thread; assert HTTP `/health/` AND UDS `/health/` both return 200 simultaneously; assert SIGTERM cleans both; assert no orphan socket file | #3 |
| `agent-brain-cli/tests/test_start_uds_flag.py` | unit | `agent-brain start --uds` passes `AGENT_BRAIN_UDS=1` (or equivalent) through; `--uds-only` passes `AGENT_BRAIN_UDS_ONLY=1`; mutually-exclusive validation; `start` without flag is unchanged | (supports #3 and Phase 3 #7) |

Phase 2 exit gate: all 6 files green; coverage on touched modules ≥ 80% (matches new-package floor).

### Phase 3 — CLI dual transport

**Goal:** `agent-brain --transport {http,uds,auto}` works; every existing command produces parity output under HTTP and UDS; `auto` resolves correctly.

| File | Type | Tests | Acceptance |
|---|---|---|---|
| `agent-brain-cli/tests/test_resolve_transport.py` | unit | `resolve_transport()` precedence (per-command flag → env → cli.toml → default `auto`); returns `("http", url)` vs `("uds", socket_path)`; raises actionable error on unreachable transport | #6, #7 |
| `agent-brain-cli/tests/test_open_client.py` | unit | `open_client(ctx)` constructs `DocServeClient` via `from_httpx(uds_client)` when transport=uds, via `DocServeClient(base_url=...)` when transport=http; honors `--socket-path` / `--base-url` overrides | (supports #5, #6) |
| `agent-brain-cli/tests/test_api_client_from_httpx.py` | unit | `DocServeClient.from_httpx(client)` retains every existing method; preserves response shape; reuses the provided `httpx.Client` (no second client created) | #5 |
| `agent-brain-cli/tests/integration/test_cli_parity.py` | integration | Boot a stub uvicorn dual-binding HTTP + UDS, run `agent-brain query "X" --json` under both transports, diff the JSON output excluding timing fields — must be byte-identical | #5 |
| `agent-brain-cli/tests/integration/test_cli_auto.py` | integration | With socket present → CLI picks UDS; with socket absent but `runtime.json` present → CLI picks HTTP; with neither → exits non-zero with clear error pointing at `agent-brain start` | #6 |
| `agent-brain-cli/tests/integration/test_cli_uds_only_collision.py` | integration | Start server with `--uds-only`; invoke CLI with `--transport http` — must raise an explicit error (not hang) | #7 |
| `agent-brain-cli/tests/test_debug_transport_output.py` | unit | `agent-brain --debug-transport query "X"` emits the resolved transport + socket/url + per-call duration to stderr | (supports debuggability) |

### Phase 4 — `agent-brain-mcp` v1 (7 tools + 5 resources + 6 prompts)

**Goal:** stdio MCP server, structured tool output, version-compat startup check, every tool/resource/prompt exercised against a fake `ApiClient` and once end-to-end via the official MCP SDK.

#### Initialize, lifecycle, version compat

| File | Type | Tests | Acceptance |
|---|---|---|---|
| `agent-brain-mcp/tests/test_initialize.py` | unit | `initialize` advertises `tools.listChanged: false`, `resources.subscribe: false`, `prompts.listChanged: false`; `serverInfo.name == "agent-brain"`; `_meta.agentBrainApiVersion` reads `/health/`; no other capabilities | #8 |
| `agent-brain-mcp/tests/test_version_compat.py` | unit | When fake `/health/` returns a version `< pyproject.toml` floor, server exits with a clear `ValueError`/exit code; valid version passes | #14 |

#### Tools (one file per concern; parametrized across the 7)

| File | Type | Tests | Acceptance |
|---|---|---|---|
| `agent-brain-mcp/tests/test_tools_list.py` | unit | `tools/list` returns exactly the 7 documented names; each has `inputSchema`, `outputSchema`, `annotations` per §6.2 | #8 |
| `agent-brain-mcp/tests/test_tool_schemas.py` | unit | Each tool's `inputSchema` validates the corresponding Pydantic model's `json_schema()`; types/required-fields match | (supports #8, #9) |
| `agent-brain-mcp/tests/test_tool_structured_output.py` | unit | Every tool returns `content[0].text` (human summary) AND `structuredContent` (typed JSON); structuredContent conforms to `outputSchema` | #9 |
| `agent-brain-mcp/tests/test_search_documents.py` | unit | Mode param accepts `vector|bm25|hybrid|graph|multi`; passes through `top_k`, `similarity_threshold`, `alpha`, `entity_types`, `relationship_types`, `explain`; surfaces `QueryResponse` | (supports #9) |
| `agent-brain-mcp/tests/test_cancel_job_confirm.py` | unit | `cancel_job` without `confirm: true` returns MCP `-32602 InvalidParams`; with `confirm: true` reaches backend | #10 |
| `agent-brain-mcp/tests/test_list_jobs_pagination.py` | unit | `list_jobs` cursor is `base64(offset)`; page-1's `nextCursor` decodes to the offset for page-2 | #13 |
| `agent-brain-mcp/tests/test_tool_cancellation.py` | unit | `notifications/cancelled` triggers `httpx.Cancel` against the underlying client within 1s | #12 |

#### Resources (5 schemes, all read-only in v1)

| File | Type | Tests | Acceptance |
|---|---|---|---|
| `agent-brain-mcp/tests/test_resources_list.py` | unit | `resources/list` returns exactly 5 URIs: `corpus://config`, `corpus://status`, `corpus://health`, `corpus://providers`, `corpus://folders` | #17 |
| `agent-brain-mcp/tests/test_resources_read_corpus_config.py` | unit | Reads `GET /health/config`; returns documented `ConfigStatus` fields | #17 |
| `agent-brain-mcp/tests/test_resources_read_corpus_status.py` | unit | Reads `GET /health/status`; returns chunk counts, graph index status, cache stats | #17 |
| `agent-brain-mcp/tests/test_resources_read_corpus_health.py` | unit | Reads `GET /health/`; returns `HealthStatus` fields | #17 |
| `agent-brain-mcp/tests/test_resources_read_corpus_providers.py` | unit | Reads `GET /health/providers`; returns provider list with model + status | #17 |
| `agent-brain-mcp/tests/test_resources_read_corpus_folders.py` | unit | Reads `GET /index/folders/`; each FolderInfo has `folder_path`, `chunk_count`, `last_indexed`, `watch_mode`, `watch_debounce_seconds` | #17 |
| `agent-brain-mcp/tests/test_resources_no_subscribe.py` | unit | `resources/subscribe` returns `Method not found` (capability advertised as `subscribe: false`) | (supports #8) |

#### Prompts (6 templates)

| File | Type | Tests | Acceptance |
|---|---|---|---|
| `agent-brain-mcp/tests/test_prompts_list.py` | unit | `prompts/list` returns exactly 6 names: `find-callers`, `find-implementation`, `explain-architecture`, `compare-search-modes`, `onboard-to-codebase`, `audit-indexed-folders` | #18 |
| `agent-brain-mcp/tests/test_prompts_arguments.py` | unit | Each prompt declares its required and optional `arguments` with descriptions and JSON-Schema validation | #18 |
| `agent-brain-mcp/tests/test_prompts_get.py` | unit | `prompts/get <name> <args>` returns non-empty `messages`; required-argument-missing rejected with clear error; `{{template}}` placeholders are interpolated | #18 |
| `agent-brain-mcp/tests/test_prompt_find_callers.py` | unit | Resulting plan calls `search_documents` with `mode=graph`, `relationship_types=["calls"]` | (supports #18) |
| `agent-brain-mcp/tests/test_prompt_audit_indexed_folders.py` | unit | Plan reads `corpus://folders`, identifies stale and unwatched, suggests `index_folder` calls | (supports #18) |

#### Error mapping

| File | Type | Tests | Acceptance |
|---|---|---|---|
| `agent-brain-mcp/tests/test_error_mapping.py` | unit | Parametrized across 8 HTTP statuses (400/404/409/422/500/502/503/504); each maps to the documented JSON-RPC code; `data.cause` and `data.httpStatus` present | #11 |

#### End-to-end (Phase 4 also seeds the E2E harness, see §4)

| File | Type | Tests | Acceptance |
|---|---|---|---|
| `agent-brain-mcp/tests/test_e2e_stdio.py` | e2e | Official MCP Python SDK as client over stdio; `initialize → tools/list → tools/call search_documents → resources/list → resources/read corpus://stats → prompts/list → prompts/get onboard-to-codebase` all succeed against a real `agent-brain-serve` (fixture corpus, UDS backend) | #8, #9, #17, #18, #19 |

### Phase 5 — Adversarial security + error-mapping coverage

**Goal:** the security boundary cases that the happy paths don't exercise.

| File | Type | Tests |
|---|---|---|
| `agent-brain-uds/tests/test_permissions_adversarial.py` | unit | Phase 1 ships the basic versions; Phase 5 adds: pointer-file owned by another uid, symlink pointing inside `state_dir` to a socket outside, world-writable pointer file, sticky-bit on parent, ACL-set extra perms on macOS |
| `agent-brain-mcp/tests/test_destructive_tool_safety.py` | unit | `clear_cache`, `remove_folder`, `cancel_job` each require `confirm: true` server-side (annotations are hints) |
| `agent-brain-server/tests/integration/test_uds_orphan_cleanup.py` | integration | Server is killed with SIGKILL while bound; new server start unlinks the stale socket cleanly |

### Phase 6 — Docs + ship

No new test files; ship gate requires every test from Phases 0–5 green and the manual E2E commands in §12.2 of the main plan pass locally. Roadmap GitHub issues are filed per plan §15.

---

## 4. E2E test harness design

### 4.1 Where it lives

`agent-brain-mcp/tests/e2e/` (new directory). Per plan §2 verified-facts table, `e2e-cli/adapters/` holds AI-runtime adapters, not transport adapters — wrong home for these tests. The MCP package owns the e2e suite because every e2e test is "MCP client → MCP server → real backend".

### 4.2 Layout

```
agent-brain-mcp/tests/e2e/
├── __init__.py
├── conftest.py          # The big fixture file — see §4.3
├── fixtures/
│   └── tiny_corpus/     # ~5 markdown files + ~3 Python files for indexing
│       ├── README.md
│       ├── docs/auth.md
│       ├── docs/storage.md
│       ├── src/query_service.py
│       └── src/auth.py
├── test_e2e_smoke.py             # initialize → tools/list → quick search
├── test_e2e_search.py            # all 5 modes, explain=true, structured output
├── test_e2e_index_and_query.py   # index_folder → get_job (poll) → search returns new chunks
├── test_e2e_resources.py         # read all 5 resources end-to-end
├── test_e2e_prompts.py           # prompts/list + prompts/get for each of the 6
└── test_e2e_lifecycle.py         # SIGTERM cleanup, stale socket recovery, no orphan agent-brain-mcp procs
```

### 4.3 Core fixtures (in `conftest.py`)

```
@pytest.fixture(scope="session")
def short_state_dir() -> Path:
    """/tmp/abmcp-e2e-<random>/  — short enough for AF_UNIX on macOS."""

@pytest.fixture(scope="session")
def indexed_server(short_state_dir, tiny_corpus_path):
    """Spawn `agent-brain-serve --uds-only` as a subprocess against
    short_state_dir, wait for /health/ healthy, index tiny_corpus,
    wait for the job, yield (state_dir, socket_path). Teardown sends
    SIGTERM and asserts the socket is unlinked."""

@pytest.fixture
def mcp_client(indexed_server):
    """Spawn `agent-brain-mcp --backend uds --state-dir <dir>` as the
    MCP server, use the official MCP Python SDK to open a stdio client
    against it. Yield the connected client. Teardown closes the client
    and asserts no orphan agent-brain-mcp processes remain."""

@pytest.fixture
def fixture_corpus_path(tmp_path_factory) -> Path:
    """Copy tests/e2e/fixtures/tiny_corpus into a session-scoped tmpdir."""
```

### 4.4 Marker + opt-in

E2E tests are slow (spawn 2 subprocesses, real index, real query). Marked `@pytest.mark.e2e` and excluded from `task mcp:test` by default. Opt-in via:

```bash
task mcp:e2e         # runs only e2e suite
task mcp:test:all    # unit + integration + e2e
```

CI runs `task mcp:e2e` nightly, not on every PR.

### 4.5 Scenarios (mirroring main plan §12.2 manual commands)

Each manual E2E command in main plan §12.2 has a 1:1 automated counterpart in `agent-brain-mcp/tests/e2e/`:

| Manual command | Automated test |
|---|---|
| `agent-brain start --uds` + curl /health/ over both transports | `agent-brain-server/tests/integration/test_uds_dual_bind.py::test_dual_bind_responds_on_both_transports` |
| `agent-brain query` parity HTTP vs UDS | `agent-brain-cli/tests/integration/test_cli_parity.py::test_query_byte_identical_under_both_transports` |
| `agent-brain-mcp --backend uds` + JSON-RPC tape | `test_e2e_smoke.py::test_initialize_tools_resources_prompts_all_listed` |
| Resource read + prompt expansion | `test_e2e_resources.py` + `test_e2e_prompts.py` |
| Adversarial UDS perms | `agent-brain-uds/tests/test_permissions_adversarial.py` |
| Error-code mapping | `agent-brain-mcp/tests/test_error_mapping.py` |
| `task check:layering` | already runs in CI via import-linter |
| `./scripts/quick_start_guide.sh` | unchanged; v1 doesn't replace it |

---

## 5. Adversarial security matrix (Phase 5 expansion)

Each row is a test case in `test_permissions_adversarial.py` or a new `test_uds_attacks.py`. The Phase 1 happy-path coverage in `test_permissions.py` is the baseline.

| # | Attack | Expected behavior | File |
|---|---|---|---|
| A1 | Socket replaced by symlink pointing to another uid's socket | Refuse with `SocketPermissionError` (already tested in Phase 1) | `test_permissions.py::test_symlink_rejected` |
| A2 | Socket mode 0666 (world-rw) | Refuse (Phase 1) | `test_world_readable_socket_rejected` |
| A3 | Socket mode 0640 (group-r) | Refuse (Phase 1) | `test_group_readable_socket_rejected` |
| A4 | Socket owned by uid+1 | Refuse (Phase 1) | `test_cross_uid_socket_rejected` |
| A5 | Parent dir mode 0755 | Refuse (Phase 1) | `test_loose_parent_dir_rejected` |
| A6 | Pointer file owned by another uid | Refuse with `SocketPermissionError` | `test_permissions_adversarial.py::test_pointer_file_cross_uid_rejected` |
| A7 | Pointer file world-writable | Refuse | `test_permissions_adversarial.py::test_pointer_file_world_writable_rejected` |
| A8 | Pointer file pointing to a socket outside the state_dir's parent | Refuse with explicit "pointer escape" message | `test_permissions_adversarial.py::test_pointer_file_escape_rejected` |
| A9 | Parent dir has sticky bit set | Accept (sticky is benign for owner-only access) — documented behavior, not a refusal | `test_permissions_adversarial.py::test_sticky_bit_parent_accepted` |
| A10 | Socket exists but no listener (stale) | `SocketStaleError` with remediation | `test_permissions_adversarial.py::test_stale_socket_detection` |
| A11 | macOS ACLs grant extra perms (skip on Linux) | Refuse | `test_permissions_adversarial.py::test_macos_acl_extra_perms_rejected` |

---

## 6. CI matrix

| Trigger | What runs |
|---|---|
| Every PR | `task uds:pr-qa-gate`, `task mcp:pr-qa-gate`, `task mcp:contract`, `task check:layering`, existing `task before-push` |
| Nightly | All of the above + `task mcp:e2e` (full E2E suite; slow) |
| Pre-release | Manual `./scripts/quick_start_guide.sh` + `python scripts/bench_uds_vs_http.py` recorded in CHANGELOG |

Per plan DR-1, **new packages are NOT added to root `task before-push` in v1.** They get rolled in at v2 after one stable release cycle.

---

## 7. Acceptance criteria → test mapping

Every functional-acceptance item from main plan §12.3 has at least one backing test. The mapping is the authoritative "no test, no acceptance" check before marking any phase complete.

| #  | Acceptance item (paraphrased) | Backing test file:test_name | Phase |
|----|---|---|---|
| 1  | paths.py resolver: 5 branches + pointer-file fallback | `agent-brain-uds/tests/test_paths.py::test_explicit_state_dir_takes_precedence` (+10 others) | 1 ✅ |
| 2  | permissions.py rejects symlink/world/group/cross-UID/loose-parent | `agent-brain-uds/tests/test_permissions.py::test_*` (10 tests) | 1 ✅ |
| 3  | Dual-bind serves HTTP+UDS in one process; SIGTERM cleans both | `agent-brain-server/tests/integration/test_uds_dual_bind.py::test_dual_bind_responds_on_both_transports` (+ Phase 1 spike already proven) | 2 |
| 4  | `RuntimeState.socket_path` field, backwards-compat | `agent-brain-server/tests/unit/test_runtime_socket_path.py::*` | 2 |
| 5  | CLI parity HTTP vs UDS | `agent-brain-cli/tests/integration/test_cli_parity.py::test_query_byte_identical_under_both_transports` | 3 |
| 6  | `--transport auto` resolves; clear error if unreachable | `agent-brain-cli/tests/integration/test_cli_auto.py::*` | 3 |
| 7  | `--uds-only` + `--transport http` errors explicitly | `agent-brain-cli/tests/integration/test_cli_uds_only_collision.py::test_uds_only_server_rejects_http_client` | 3 |
| 8  | `initialize` reports correct capabilities + counts | `agent-brain-mcp/tests/test_initialize.py::*` + `test_e2e_stdio.py::test_initialize_capabilities` | 4 |
| 9  | Each of 7 tools returns `content` + `structuredContent` | `agent-brain-mcp/tests/test_tool_structured_output.py::*` (parametrized) | 4 |
| 10 | `cancel_job` without `confirm: true` returns -32602 | `agent-brain-mcp/tests/test_cancel_job_confirm.py::test_confirm_required` | 4 |
| 11 | HTTP→MCP error-code mapping (8 statuses) | `agent-brain-mcp/tests/test_error_mapping.py::test_mapping[*]` | 4/5 |
| 12 | `notifications/cancelled` cancels in-flight httpx within 1s | `agent-brain-mcp/tests/test_tool_cancellation.py::test_cancellation_within_one_second` | 4 |
| 13 | `list_jobs` cursor pagination roundtrip | `agent-brain-mcp/tests/test_list_jobs_pagination.py::test_cursor_roundtrip` | 4 |
| 14 | MCP server refuses to start if `/health/` version below floor | `agent-brain-mcp/tests/test_version_compat.py::test_refuse_start_on_old_server` | 4 |
| 15 | `task check:layering` fails when contract-violating import added | `agent-brain-server/tests/test_layering_enforcement.py::test_layering_catches_violation` (uses CI dry-run trick) | 0/2 |
| 16 | `GET /health/config` shape + env-override | `agent-brain-server/tests/unit/api/test_health_config.py::test_config_endpoint_returns_storage_backend_from_env` | 2 |
| 17 | `resources/list` returns 5 URIs; each `read` returns valid JSON | `agent-brain-mcp/tests/test_resources_*.py` | 4 |
| 18 | `prompts/list` returns 6; `prompts/get` expands | `agent-brain-mcp/tests/test_prompts_*.py` | 4 |
| 19 | `prompts/get onboard-to-codebase` end-to-end produces briefing | `agent-brain-mcp/tests/e2e/test_e2e_prompts.py::test_onboard_to_codebase_full_run` | 4 (e2e) |

---

## 8. Already done (Phases 0+1)

- **Phase 0** (`1e95576`): scaffold, import-linter contracts (`.importlinter`), `task check:layering` task. 2 smoke tests pass per package. Layering contracts: 3 kept, 0 broken.
- **Phase 1** (`0a9439d`): `agent-brain-uds` client modules + `scripts/spike_dual_bind.py`. **28 unit tests pass, 99% coverage, spike PASS.**

Phase 0+1 alone backs acceptance items #1, #2, and (via the passing spike script) the architectural premise behind #3.

---

## 9. Failure-mode taxonomy (the things this test plan is intentionally guarding against)

These are the categories of failure each ring is designed to catch. Worth keeping in mind when writing new tests: which ring catches *this* class of bug?

| Ring | Catches | Misses |
|---|---|---|
| Unit | Type errors, schema drift, boundary math, refactor breakage | Wire-protocol incompatibility, real OS perms, signal handling, subprocess lifecycle |
| Integration | Real socket bind, real CLI invocation, real signal handling, lifespan ordering | Multi-process race, MCP-client compatibility, real model behavior |
| E2E | End-to-end protocol, real subprocess lifecycle, fixture corpus behavior, no-orphan-procs | Performance regressions (separate `scripts/bench_*` recorded-only suite), real LLM call quality |

When debugging a failure: backfill the test at the lowest ring that could have caught it.

---

## 10. Maintenance: when to update this doc

- Adding a new test? Add the row to §3 or §5 with its acceptance link.
- Adding a new acceptance criterion? Add the row in §7 and ensure §3 has a backing file.
- Changing a marker / test task layout? Update §6.
- Shipping a roadmap phase (v2/v3/v4)? Each gets its own test-plan doc, this one stays frozen to v1.
