---
phase: 58-runtime-discovery-helper-commands
verified: 2026-06-06T00:00:00Z
status: passed
score: 8/8 must-haves verified
---

# Phase 58: Runtime discovery + helper commands Verification Report

**Phase Goal:** Make the MCP HTTP listener self-advertising: define the mcp.runtime.json schema, land `agent-brain mcp start` (loopback bind, port auto-allocation, psutil socket-bind verification — reuses v10.2 HTTP-02 pattern), and `agent-brain mcp stop` (SIGTERM/SIGKILL escalation, runtime file cleanup).

**Verified:** 2026-06-06
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #   | Truth                                                                                                                | Status     | Evidence                                                                                                                                                                                                                                                                                                                                                                                                                       |
| --- | -------------------------------------------------------------------------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| SC1 | `agent-brain mcp start` launches subprocess + writes mcp.runtime.json AFTER psutil verifies listener accepting conns | VERIFIED   | `commands/mcp.py:61` `@click.group("mcp")`; `:138` `@mcp_group.command("start")`; `:223` `start_new_session=True` in `subprocess.Popen`; `:237` `is_listening(pid, host, port, ...)` called BEFORE `:281` `write_mcp_runtime(...)`. Runtime dict at `:273-280` contains all 5 fields {host, port, pid, started_at, transport}. On listener timeout (`:244`), `release_lock` + `SystemExit(1)` and runtime is NOT written.       |
| SC2 | `--transport mcp --mcp-transport http query "X"` with NO `--mcp-url` reads mcp.runtime.json and connects             | VERIFIED   | `client.py:835` `McpHttpBackend.__init__` accepts `url: str \| None = None` + `state_dir: Path \| None = None`; `:860` calls `_discover_url(state_dir)` when url is None; `:866` `_discover_url` lazy-imports `agent_brain_cli.mcp_runtime` + calls `read_mcp_runtime`. `config.py:541` `resolve_mcp_transport` has `state_dir` kwarg; `:594` calls `read_mcp_runtime`. Integration test at `test_mcp_helper_commands.py` exists. |
| SC3 | `agent-brain mcp stop` reads runtime, SIGTERM, escalates to SIGKILL after grace, removes runtime on clean exit       | VERIFIED   | `commands/mcp.py:324` `@mcp_group.command("stop")`; `:405` `os.killpg(pgid, signal.SIGTERM)`; `:329` `--grace` flag + `envvar="AGENT_BRAIN_MCP_STOP_GRACE"`; `:437` `os.killpg(pgid, signal.SIGKILL)` escalation; `:442-443` `delete_mcp_runtime + release_lock` after kill. Idempotent path at `:360` returns "not_running" exit 0 when nothing running.                                                                          |
| SC4 | Concurrent `mcp start` against running instance fails fast with verbatim "already running on port N" + non-zero exit | VERIFIED   | `mcp_runtime.py:174` `LockAcquisitionError(f"agent-brain mcp already running on port {holder_port} (pid {holder_pid}); run 'agent-brain mcp stop' first")` — verbatim wording. `commands/mcp.py:185` catches `LockAcquisitionError` and `:190` `raise SystemExit(1) from exc` for non-zero exit.                                                                                                                                |
| SC5 | §3.5 wording swap (Phase 57 carry-forward closure)                                                                   | VERIFIED   | `grep -c "discovery file support lands in Phase 58" agent-brain-cli/agent_brain_cli/config.py` returns `0` (recursive across `agent_brain_cli/` also returns 0). `grep -c "discovery file not found at" agent-brain-cli/agent_brain_cli/config.py` returns `2` (verbatim §3.5 wording present at `:605` and `:615`).                                                                                                             |
| SC6 | psutil dep addition                                                                                                  | VERIFIED   | `grep -c 'psutil = "\^5.9"' agent-brain-cli/pyproject.toml` returns `1`; `grep -c '^name = "psutil"' agent-brain-cli/poetry.lock` returns `1`.                                                                                                                                                                                                                                                                                  |
| SC7 | `task before-push` gate honored                                                                                      | VERIFIED   | 58-01 SUMMARY line 195: "task before-push exits 0 ✓"; 58-02 SUMMARY line 197: "task before-push exits 0 ✓"; 58-03 SUMMARY line 234: "task before-push exits 0 ✓". All three "Self-Check: PASSED".                                                                                                                                                                                                                              |
| SC8 | Requirements traceability                                                                                            | VERIFIED   | REQUIREMENTS.md: CLI-MCP-08, CLI-MCP-09, CLI-MCP-10 all marked `[x]` complete with phase-58 attribution in coverage table.                                                                                                                                                                                                                                                                                                      |

**Score:** 8/8 truths verified

### Required Artifacts

| Artifact                                                              | Expected                                       | Status     | Details                                                                                                                                                              |
| --------------------------------------------------------------------- | ---------------------------------------------- | ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `agent-brain-cli/agent_brain_cli/mcp_runtime.py`                      | Schema constants + 6 helpers + LockError class | VERIFIED   | 273 lines (≥120 required). Contains `MCP_RUNTIME_FILE`, `MCP_LOCK_FILE`, `read/write/delete_mcp_runtime`, `acquire/release_lock`, `is_listening`, `LockAcquisitionError`. |
| `agent-brain-cli/agent_brain_cli/commands/mcp.py`                     | Click group + start + stop subcommands         | VERIFIED   | 453 lines (≥180 required). Contains `@click.group("mcp")`, `@mcp_group.command("start")`, `@mcp_group.command("stop")`, `start_new_session=True`.                       |
| `agent-brain-cli/agent_brain_cli/commands/__init__.py`                | Re-exports mcp_group                           | VERIFIED   | Contains `from .mcp import mcp_group` (line 13) and `"mcp_group"` in `__all__` (line 33).                                                                              |
| `agent-brain-cli/agent_brain_cli/cli.py`                              | Registers mcp_group under top-level cli        | VERIFIED   | Line 21 imports `mcp_group`, line 161 `cli.add_command(mcp_group, name="mcp")`.                                                                                       |
| `agent-brain-mcp/agent_brain_mcp/client.py`                           | McpHttpBackend discovery + _discover_url       | VERIFIED   | `__init__` widened to accept `url: str \| None = None` + `state_dir: Path \| None = None`; `_discover_url` staticmethod at line 866 reads mcp.runtime.json.            |
| `agent-brain-cli/agent_brain_cli/config.py`                           | resolve_mcp_transport discovery + §3.5 wording | VERIFIED   | `resolve_mcp_transport` at line 541 with `state_dir` kwarg; reads `read_mcp_runtime` at line 594; verbatim §3.5 wording at lines 605 + 615.                          |
| `agent-brain-cli/agent_brain_cli/client/transport.py`                 | open_backend threads state_dir                 | VERIFIED   | `_resolve_state_dir_for_discovery` at line 46; called at line 102; `state_dir=state_dir` passed to `resolve_mcp_transport` at line 106.                              |
| `agent-brain-cli/tests/test_mcp_runtime.py`                           | Unit tests for runtime helpers                 | VERIFIED   | 342 lines (≥80 required). 19 tests pass.                                                                                                                              |
| `agent-brain-cli/tests/test_mcp_start_command.py`                     | Unit tests for start command                   | VERIFIED   | 380 lines (≥150 required). 12 tests pass.                                                                                                                             |
| `agent-brain-cli/tests/test_mcp_stop_command.py`                      | Unit tests for stop command                    | VERIFIED   | 360 lines. 11 tests pass.                                                                                                                                              |
| `agent-brain-cli/tests/test_resolve_mcp_transport_discovery.py`       | Unit tests for resolver discovery              | VERIFIED   | 6 tests pass.                                                                                                                                                          |
| `agent-brain-mcp/tests/test_mcp_http_backend_discovery.py`            | Unit tests for backend discovery               | VERIFIED   | 6 tests pass.                                                                                                                                                          |
| `agent-brain-cli/tests/integration/test_mcp_helper_commands.py`       | End-to-end integration test                    | VERIFIED   | 250 lines (≥80 required). 3 tests (1 OPENAI_API_KEY-gated, 2 cheap). Both cheap tests pass.                                                                          |
| `agent-brain-cli/pyproject.toml`                                      | psutil dep declared                            | VERIFIED   | Contains `psutil = "^5.9"`.                                                                                                                                            |
| `agent-brain-cli/poetry.lock`                                         | psutil locked                                  | VERIFIED   | Contains `name = "psutil"` entry.                                                                                                                                       |

### Key Link Verification

| From                                  | To                                  | Via                                                | Status     | Details                                                                                                       |
| ------------------------------------- | ----------------------------------- | -------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------- |
| commands/mcp.py                       | mcp_runtime.py                      | imports acquire_lock, write_mcp_runtime, is_listening, read_mcp_runtime, delete_mcp_runtime, release_lock | WIRED      | All imports present at lines 36-46. Used in start_command (lines 184, 237, 251, 281) and stop_command (lines 357, 361, 373, 383, 408, 425, 442). |
| commands/mcp.py                       | agent-brain-mcp subprocess          | subprocess.Popen with start_new_session=True       | WIRED      | Popen call at line 217 with `cmd = [sys.executable, "-m", "agent_brain_mcp", "--transport", "http", "--host", "127.0.0.1", "--port", str(resolved_port)]`. |
| cli.py                                | mcp_group                           | cli.add_command registration                       | WIRED      | Line 161: `cli.add_command(mcp_group, name="mcp")`. Verified live via `poetry run agent-brain mcp --help`.   |
| commands/mcp.py (stop)                | os.killpg + signal.SIGTERM/SIGKILL  | stop subcommand process-group termination          | WIRED      | `os.killpg(pgid, signal.SIGTERM)` at line 405; `os.killpg(pgid, signal.SIGKILL)` at line 437.                |
| agent-brain-mcp/client.py             | agent_brain_cli/mcp_runtime.py      | McpHttpBackend._discover_url reads mcp.runtime.json | WIRED      | Lazy import at line 879-882; calls `read_mcp_runtime(state_dir)` at line 888.                                |
| agent-brain-cli/config.py             | agent_brain_cli/mcp_runtime.py      | resolve_mcp_transport checks mcp.runtime.json      | WIRED      | Lazy import at line 588-592; calls `read_mcp_runtime(state_dir)` at line 594.                                |
| client/transport.py                   | config.py + mcp_runtime.py          | open_backend threads state_dir down                | WIRED      | `_resolve_state_dir_for_discovery()` at line 102; result passed as `state_dir=state_dir` at line 106.       |

### Requirements Coverage

| Requirement | Source Plan       | Description                                                                                                          | Status     | Evidence                                                                                                                                                                                                                                                                       |
| ----------- | ----------------- | -------------------------------------------------------------------------------------------------------------------- | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| CLI-MCP-08  | 58-01, 58-03      | mcp.runtime.json written by start, read by CLI when --transport mcp --mcp-transport http used without --mcp-url      | SATISFIED  | Schema constants in mcp_runtime.py (Plan 58-01); write_mcp_runtime called by start subcommand (Plan 58-02); read_mcp_runtime called by McpHttpBackend.__init__ (Plan 58-03) AND by resolve_mcp_transport (Plan 58-03). Integration test test_mcp_start_query_stop_round_trip drives full cycle. REQUIREMENTS.md [x]. |
| CLI-MCP-09  | 58-02             | agent-brain mcp start helper with loopback bind, port auto-allocation, mcp.runtime.json write on listener-ready      | SATISFIED  | start_command in commands/mcp.py implements full flow: `_resolve_preferred_port` + `_allocate_port` (EADDRINUSE fallback), Popen with `start_new_session=True`, `is_listening` psutil probe BEFORE `write_mcp_runtime`. REQUIREMENTS.md [x].                                  |
| CLI-MCP-10  | 58-03             | agent-brain mcp stop reads runtime, sends SIGTERM, escalates SIGKILL after grace, removes mcp.runtime.json           | SATISFIED  | stop_command in commands/mcp.py: 4 idempotent fast paths, then `os.killpg(pgid, SIGTERM)`, `_wait_for_pid_exit` poll, `os.killpg(pgid, SIGKILL)` escalation, `delete_mcp_runtime + release_lock` cleanup. REQUIREMENTS.md [x].                                              |

### Anti-Patterns Found

None. No TODO/FIXME/XXX/HACK/PLACEHOLDER markers in mcp_runtime.py, commands/mcp.py, or agent-brain-mcp/client.py. No stub returns. No empty handlers.

### Test Execution Results

- `agent-brain-cli/tests/test_mcp_runtime.py`: 19 tests passed (in 48-test batch).
- `agent-brain-cli/tests/test_mcp_start_command.py`: 12 tests passed.
- `agent-brain-cli/tests/test_mcp_stop_command.py`: 11 tests passed.
- `agent-brain-cli/tests/test_resolve_mcp_transport_discovery.py`: 6 tests passed.
- Combined: 48 tests passed in 1.30s.
- `agent-brain-mcp/tests/test_mcp_http_backend_discovery.py`: 6 tests passed in 0.23s.
- `agent-brain-cli/tests/integration/test_mcp_helper_commands.py`: 2 cheap tests passed (`test_mcp_stop_idempotent_when_nothing_running`, `test_discovery_error_wording_matches_section_3_5`); full round-trip test skips gracefully without OPENAI_API_KEY.

### Live CLI Verification

- `poetry run agent-brain mcp --help` exits 0; shows `start` + `stop` subcommands.
- `poetry run agent-brain mcp start --help` exits 0; shows `--port`, `--start-timeout`, `--state-dir`, `--json` flags.

### Commit Trail

All seven commits documented in SUMMARYs are present in git history:
- `da37239` feat(58-01): mcp_runtime.py shared helpers + psutil verifier + 0o600 perms
- `3b2272c` docs(58-01): complete mcp_runtime.py helpers plan
- `152c305` feat(58-02): agent-brain mcp start subcommand (CLI-MCP-09)
- `084232b` docs(58-02): complete agent-brain mcp start plan
- `9f53b17` feat(58-03): add agent-brain mcp stop subcommand (CLI-MCP-10)
- `9a0cea9` feat(58-03): McpHttpBackend discovery + resolve_mcp_transport widening + §3.5 wording swap
- `00e906a` test(58-03): end-to-end integration test for mcp start -> query -> stop
- `a713dcd` chore(58-03): black/ruff fixes + harden discovery-error test env
- `7f02cd4` docs(58-03): complete agent-brain mcp stop + McpHttpBackend discovery plan

### Human Verification Required

None. All 8 must-have success criteria verified programmatically. Optional human verification: drive the full discovery happy path with a real OPENAI_API_KEY (`pytest tests/integration/test_mcp_helper_commands.py::test_mcp_start_query_stop_round_trip -v -m integration`) — though this is already covered by the automated test when the env var is set.

### Gaps Summary

No gaps. Phase 58 fully delivers the goal:
1. mcp.runtime.json schema locked to the 5-field §2.4 design-doc contract (host, port, pid, started_at, transport) with 0o600 perms.
2. `agent-brain mcp start` spawns a detached agent-brain-mcp subprocess on a loopback port (with EADDRINUSE fallback), psutil-verifies the listener BEFORE writing the runtime file, and surfaces verbatim "already running" wording with exit 1 on lock collision.
3. `agent-brain mcp stop` reads the runtime, uses `os.killpg` for process-group termination with SIGTERM → grace → SIGKILL escalation, cleans up runtime + lock files. Idempotent across 4 fast paths.
4. `McpHttpBackend.__init__` discovery + `resolve_mcp_transport` discovery + `transport.open_backend` state_dir threading close the end-to-end discovery loop. Phase 57 placeholder wording deleted; verbatim §3.5 wording surfaces on miss.
5. psutil = "^5.9" added to agent-brain-cli runtime deps and locked.
6. All three requirements (CLI-MCP-08/09/10) marked complete in REQUIREMENTS.md.
7. `task before-push` exits 0 documented in all three plan SUMMARYs.

---

_Verified: 2026-06-06_
_Verifier: Claude (gsd-verifier)_
