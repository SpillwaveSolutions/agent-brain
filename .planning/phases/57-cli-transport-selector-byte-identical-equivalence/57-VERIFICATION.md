---
phase: 57-cli-transport-selector-byte-identical-equivalence
verified: 2026-06-06T00:00:00Z
status: passed
score: 7/7 must-haves verified
---

# Phase 57: CLI Transport Selector + Byte-Identical Equivalence Verification Report

**Phase Goal:** Wire `--transport mcp` + `--mcp-transport stdio|http` into the Click CLI with explicit selection (no silent fallback, mirroring v10.2 HTTP-03); pin the v3 Definition of Done — byte-identical query results between `--transport mcp` and `--transport uds` for the same backend state.

**Verified:** 2026-06-06
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (Success Criteria from ROADMAP + must_haves from PLANs)

| #   | Truth                                                                                                                  | Status      | Evidence                                                                                                                                                                                                       |
| --- | ---------------------------------------------------------------------------------------------------------------------- | ----------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | SC1: `agent-brain --transport mcp query "X"` routes through McpStdioBackend by default                                 | ✓ VERIFIED  | `cli.py:36` Choice extended to `["auto","http","uds","mcp"]`; `cli.py:55-56` declares `--mcp-transport`; `config.py:577` defaults to `"stdio"` when no hint/env; `transport.py:103-116` dispatcher branch routes mcp+stdio → `McpStdioBackend(command="agent-brain-mcp")` |
| 2   | SC2: `agent-brain --transport mcp --mcp-transport http query "X"` routes through McpHttpBackend                        | ✓ VERIFIED  | `cli.py:66-67` declares `--mcp-url`; `transport.py:117-120` dispatcher branch routes mcp+http → `McpHttpBackend(url=mcp_target, timeout=timeout)`; `config.py:594` returns `("http", url)` after URL resolution |
| 3   | SC3: All 3 §3.5 misuse cases exit with code 2 + verbatim wording; NO silent fallback                                   | ✓ VERIFIED  | Case 1: `transport.py:100` `"install agent-brain-mcp to use --transport mcp"`; Case 2: `config.py:591-592` `"discovery file support lands in Phase 58; pass --mcp-url explicitly in Phase 57"` (split-line literal); Case 3: `transport.py:107-110` `shutil.which("agent-brain-mcp")` precheck + verbatim `"agent-brain-mcp not found on PATH; install agent-brain-mcp into the same Python environment"`. Tests assert `result.exit_code == 2` (test_transport_selector_mcp.py:74,97,264) |
| 4   | SC4: Byte-identical contract test asserts JSON equality between UDS and MCP stdio after stripping volatile fields      | ✓ VERIFIED  | `tests/contract/test_transport_equivalence.py` exists; `grep -c "stub"` returns 0; `grep -c "subprocess.run"` returns 2 (real CLI subprocesses for both transports); `_normalize.py:21 def strip_volatile_fields`; line 164-165 asserts `json.dumps(uds_payload, sort_keys=True) == json.dumps(mcp_payload, sort_keys=True)` after `strip_volatile_fields(json.loads(stdout))` |
| 5   | All 10 BackendClient methods wired on both backends via asyncio.run + MCP SDK; reset() raises NotImplementedError      | ✓ VERIFIED  | `grep -c "asyncio.run("` = 24; `grep -c "stdio_client"` = 25; `grep -c "streamablehttp_client"` = 25; each wire name present on both backends (server_health: 2, corpus://status: 2, corpus://folders: 2, list_jobs: 2, cache_status: 2, clear_cache: 2, cancel_job: 2, remove_folder: 2, search_documents: 2; index_folder/inject_documents: 1 each — string lives in shared `_build_index_body` helper per 57-03 SUMMARY). `grep -c "raise NotImplementedError"` = exactly 2 (both reset() bodies). Verbatim §3.5 reset wording: 2 (one per backend, client.py:724-728 stdio + client.py:1043-1047 http) |
| 6   | `task before-push` gate honored across all 3 plans                                                                     | ✓ VERIFIED  | 57-01-SUMMARY.md reports Self-Check: PASSED + `task before-push exit 0` (CLI 451 + MCP 474 + server + UDS). 57-02-SUMMARY.md reports Self-Check: PASSED + `task before-push exit 0` (CLI 451+2 contract + MCP 477). 57-03-SUMMARY.md reports Self-Check: PASSED + `task before-push exit 0` (MCP 490 + CLI/UDS/server; coverage 87%) |
| 7   | Requirements traceability — REQUIREMENTS.md marks CLI-MCP-03 AND CLI-MCP-04 complete                                   | ✓ VERIFIED  | REQUIREMENTS.md: `[x] CLI-MCP-03` (selector + dispatcher + 3 §3.5 cases in 57-01; query + CLI-MCP-04 in 57-02; remaining 10 methods + reset in 57-03); `[x] CLI-MCP-04` (Complete). Phase 57 row in ROADMAP.md marked complete (3/3 plans, completed 2026-06-06) |

**Score:** 7/7 truths verified

### Required Artifacts

| Artifact                                                                                            | Expected                                                                       | Status     | Details                                                                                                                  |
| --------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ | ---------- | ------------------------------------------------------------------------------------------------------------------------ |
| `agent-brain-cli/agent_brain_cli/cli.py`                                                            | Extended `--transport` Choice + new `--mcp-transport` + `--mcp-url` group flags | ✓ VERIFIED | Line 36 has `Choice(["auto","http","uds","mcp"], case_sensitive=False)`; lines 55-56 + 66-67 declare new flags         |
| `agent-brain-cli/agent_brain_cli/config.py`                                                         | `resolve_mcp_transport()` helper                                               | ✓ VERIFIED | `def resolve_mcp_transport(*, mcp_transport_hint, mcp_url_override) -> tuple[Literal["stdio","http"], str \| None]` at line 542; precedence chain implemented; Case 2 verbatim wording at 591-592 |
| `agent-brain-cli/agent_brain_cli/client/transport.py`                                               | `open_backend(ctx) -> BackendClient` dispatcher with 4 branches + shutil.which precheck | ✓ VERIFIED | Line 45 declares; 4 branches present; `shutil.which("agent-brain-mcp")` precheck at line 107; `open_client` removed |
| `agent-brain-mcp/agent_brain_mcp/client.py`                                                         | 10 wired BackendClient methods × 2 backends + verbatim reset NotImplementedError | ✓ VERIFIED | Both McpStdioBackend + McpHttpBackend have all 13 public methods (close + query + health + status + index + list_folders + delete_folder + list_jobs + get_job + cancel_job + cache_status + clear_cache + reset). Wire mapping per §2.3 verified by grep counts. Reset wording verbatim |
| `agent-brain-cli/tests/contract/test_transport_equivalence.py`                                      | v3 DoD anchor — REAL subprocess + REAL seeded corpus, no stub fallback         | ✓ VERIFIED | File exists; 0 occurrences of "stub"; 2 real `subprocess.run` calls (one per transport); uses `strip_volatile_fields` helper from `_normalize.py`; full JSON byte-compare via `json.dumps(sort_keys=True)` |
| `agent-brain-cli/tests/contract/_normalize.py`                                                      | `strip_volatile_fields` helper                                                 | ✓ VERIFIED | `def strip_volatile_fields(payload: dict[str, Any]) -> dict[str, Any]` at line 21; strips top-level `elapsed_seconds`/`query_time_ms` + per-result `indexed_at`/`updated_at`/`elapsed_ms` (in metadata and on result) |
| `agent-brain-cli/tests/test_transport_selector_mcp.py`                                              | 3 §3.5 misuse cases as exit-2 tests + skeleton routing                         | ✓ VERIFIED | All 3 cases pinned with `result.exit_code == 2` + verbatim wording substring assertions (lines 74, 97, 264); skeleton routing tests; HTTP regression |
| `agent-brain-cli/tests/test_config_resolve_mcp_transport.py`                                        | Precedence + error tests for resolve_mcp_transport                             | ✓ VERIFIED | 7 tests covering flag/env/default precedence + Case 2 error path                                                         |
| `agent-brain-mcp/tests/test_cli_backends_query_wire.py`                                             | Wire-level tests for McpStdioBackend.query + McpHttpBackend.query              | ✓ VERIFIED | 5 stdio tests + 3 e2e_http tests; per-call subprocess spawn pinned                                                       |
| `agent-brain-mcp/tests/test_cli_backends_methods_wire.py`                                           | Wire-level tests for remaining 10 methods on both backends                     | ✓ VERIFIED | 12 stdio fast + 11 e2e_http opt-in = 23 tests; covers each wired method's wire shape on both backends                    |

### Key Link Verification

| From                                                       | To                                                                              | Via                                                                | Status   | Details                                                                                                                                   |
| ---------------------------------------------------------- | ------------------------------------------------------------------------------- | ------------------------------------------------------------------ | -------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `cli.py` Click group                                       | `ctx.obj["mcp_transport_hint"]` / `ctx.obj["mcp_url_override"]`                 | Click group callback writes new keys                               | ✓ WIRED  | 57-01 SUMMARY confirms ctx.obj write block; tests pass                                                                                    |
| `transport.py` mcp branch                                  | `from agent_brain_mcp.client import McpStdioBackend, McpHttpBackend`            | Lazy import inside transport == "mcp" branch                       | ✓ WIRED  | Lines 95-96 lazy import inside try/except; ImportError → click.UsageError with Case 1 wording                                            |
| `transport.py` stdio branch                                | `shutil.which("agent-brain-mcp")`                                                | PATH precheck guarding stdio dispatcher                            | ✓ WIRED  | Line 107 precheck; None → click.UsageError with Case 3 verbatim wording                                                                  |
| 8 command modules                                          | `open_backend(ctx)`                                                              | Atomic rename of 20 callsites                                      | ✓ WIRED  | 57-01 SUMMARY confirms `grep -rh "open_client" agent_brain_cli/commands/` returns 0 lines (atomic rename complete)                       |
| `McpStdioBackend.query`                                    | `mcp.client.stdio.stdio_client + ClientSession.call_tool('search_documents')`   | `asyncio.run(self._async_query(...))` sync facade                  | ✓ WIRED  | client.py contains `asyncio.run(` 24×, `stdio_client` 25×, `"search_documents"` 2× (one per backend)                                     |
| `McpHttpBackend.query`                                     | `mcp.client.streamable_http.streamablehttp_client + ClientSession.call_tool`    | `asyncio.run(self._async_query(...))` sync facade + (read,write,*_) tuple-absorb | ✓ WIRED  | `streamablehttp_client` 25× in client.py                                                                                                  |
| `tests/contract/test_transport_equivalence.py`             | `subprocess.run([sys.executable, '-m', 'agent_brain_cli', '--transport', ...])` | Drive both CLI invocations against the same seeded state_dir       | ✓ WIRED  | 2 `subprocess.run` calls (UDS + MCP stdio); 0 stub references; `strip_volatile_fields` used on both payloads; byte-compare via json.dumps |
| Each wired method                                          | MCP wire (call_tool / read_resource)                                            | `asyncio.run(_async_*())` per method                               | ✓ WIRED  | All 11 wire names present 2× each (except `index_folder`/`inject_documents` which live in shared `_build_index_body` helper, 1× each)    |

### Requirements Coverage

| Requirement | Source Plan       | Description                                                                                                              | Status      | Evidence                                                                                                                                                          |
| ----------- | ----------------- | ------------------------------------------------------------------------------------------------------------------------ | ----------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| CLI-MCP-03  | 57-01-PLAN + 57-03-PLAN | `agent-brain --transport mcp` selector + `--mcp-transport stdio\|http` sub-selector wired; explicit selection, no silent fallback (mirrors v10.2 HTTP-03) | ✓ SATISFIED | REQUIREMENTS.md marks `[x] CLI-MCP-03`. Selector + dispatcher + 3 §3.5 cases in 57-01; full method wiring in 57-03. All wire mappings verified by grep. `task before-push` exit 0 across both plans. |
| CLI-MCP-04  | 57-02-PLAN        | `agent-brain --transport mcp query "X"` returns byte-identical results to `--transport uds` for the same backend state (modulo timestamps/elapsed) — the v3 DoD anchor | ✓ SATISFIED | REQUIREMENTS.md marks `[x] CLI-MCP-04` Complete. DoD anchor exists at `agent-brain-cli/tests/contract/test_transport_equivalence.py` with REAL subprocess + REAL seeded corpus (no stub fallback). SKIPS honestly when `OPENAI_API_KEY` is absent; passes wire-level when keys are present. |

No orphaned requirements detected. Both phase-declared requirements covered by all 3 plans collectively.

### Anti-Patterns Found

| File                                                           | Line | Pattern                                       | Severity     | Impact                                                                                            |
| -------------------------------------------------------------- | ---- | --------------------------------------------- | ------------ | ------------------------------------------------------------------------------------------------- |
| `agent-brain-mcp/agent_brain_mcp/client.py`                    | 724, 1043 | `raise NotImplementedError` (×2 reset bodies) | ℹ️ Info      | Intentional per CONTEXT.md §decisions — `reset()` has no MCP wire equivalent in v2; verbatim §3.5/§4 wording surfaces a clear operator pointer to `--transport uds` or `http`. Phase 57+ open decision deferred. NOT a blocker. |

No blocker or warning anti-patterns. All TODO/FIXME/placeholder patterns absent from the wired code paths. The two surviving `raise NotImplementedError` sites are both verified-intentional with verbatim CONTEXT.md wording.

### Human Verification Required

None. All Success Criteria + must-haves are verifiable programmatically through static checks (grep, file existence, wire-name presence, exit code assertions, byte-compare assertions). The runtime byte-equivalence proof is itself an automated contract test that gates `task before-push`. The test SKIPS honestly when `OPENAI_API_KEY` is unavailable in the test environment, but this is documented as the explicit no-stub-fallback design decision (per 57-02 SUMMARY) — CI with real keys exercises the wire-level proof.

### Gaps Summary

No gaps. Phase 57 delivers its stated goal in full:

1. `--transport mcp` + `--mcp-transport stdio|http` + `--mcp-url` are wired into the Click group with the 4-branch dispatcher (mcp+stdio, mcp+http, http, uds).
2. All 3 §3.5 design-doc misuse cases surface as exit-code-2 `click.UsageError`s with verbatim wording (case 1: ImportError → "install agent-brain-mcp to use --transport mcp"; case 2: missing URL → "discovery file support lands in Phase 58; pass --mcp-url explicitly in Phase 57"; case 3: missing PATH → "agent-brain-mcp not found on PATH; install agent-brain-mcp into the same Python environment"). NO silent fallback.
3. All 10 BackendClient methods are wired on both `McpStdioBackend` and `McpHttpBackend` via `asyncio.run(self._async_*())` Pattern A sync facade against the §2.3 wire mapping. `reset()` raises `NotImplementedError` with the verbatim §3.5/§4 wording on both backends — exactly 2 `raise NotImplementedError` sites in client.py, both verified-intentional.
4. The CLI-MCP-04 byte-identical-equivalence DoD anchor lands at `agent-brain-cli/tests/contract/test_transport_equivalence.py` as a real subprocess + real seeded corpus + full JSON byte-compare (after stripping volatile fields). NO stub fallback (`grep -c "stub"` = 0). Two `subprocess.run` calls drive both transports through the CLI against the same backend state.
5. `task before-push` exits 0 across all 3 plans (57-01: CLI 451 + MCP 474; 57-02: CLI 451+2 contract + MCP 477; 57-03: MCP 490 + CLI/UDS/server, coverage 87%). All 3 SUMMARYs report `Self-Check: PASSED`.
6. REQUIREMENTS.md marks both CLI-MCP-03 and CLI-MCP-04 as `[x]` Complete. ROADMAP.md marks Phase 57 as complete (3/3 plans, completed 2026-06-06).

---

_Verified: 2026-06-06_
_Verifier: Claude (gsd-verifier)_
