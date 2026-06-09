# Phase 58: Runtime discovery + helper commands - Context

**Gathered:** 2026-06-07 (auto mode)
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers:

1. **`<state_dir>/mcp.runtime.json` schema** locked per v3 design doc §2.4 — `{host, port, pid, started_at, transport}`. Single file, single-instance per `state_dir`, written by `agent-brain mcp start` AFTER psutil verifies the listener is accepting connections, removed by `agent-brain mcp stop` on clean exit.
2. **`agent-brain mcp start` Click command** that launches `agent-brain-mcp --transport http` as a detached background subprocess on a free loopback port (`127.0.0.1`), psutil-verifies the listener is up, and writes `mcp.runtime.json`. Mirrors the existing `agent-brain start` server-helper pattern. Reuses the v10.2 HTTP-02 psutil socket-bind verification approach.
3. **`agent-brain mcp stop` Click command** that reads `mcp.runtime.json`, sends SIGTERM to the process group, escalates to SIGKILL after a configurable grace period, removes `mcp.runtime.json`, releases the lock. Idempotent (no-op if not running).
4. **`McpHttpBackend.__init__` discovery integration** — when `--mcp-url` is omitted, read `<state_dir>/mcp.runtime.json` to find `host:port`. Replaces the Phase 57 placeholder error message (`"discovery file support lands in Phase 58; pass --mcp-url explicitly in Phase 57"`) with the design-doc §3.5 wording about the discovery file when neither source resolves.

Out of phase scope (deferred to later phases in this milestone):
- Subprocess hygiene (pinned cwd, env allowlist, SIGTERM/SIGKILL refinement, persistent subprocess for stdio backend, 1000-invocation pgrep orphan test) → Phase 60
- `agent-brain prompt <name>` + `agent-brain resources list|read <uri>` commands → Phase 59
- Multi-instance MCP listeners (per project) → out of v10.3 (v3 design doc explicitly: single-file, single-instance per state_dir)
- Auto-restart on crash / supervisor behavior → out of scope (operators run `agent-brain mcp start` manually)
- Log rotation, structured logging from MCP subprocess → Phase 60 hygiene work
- Windows process-group semantics → out of CLAUDE.md project scope (Python 3.10+ on macOS/Linux only)

</domain>

<decisions>
## Implementation Decisions

### CLI command structure
- **`agent-brain mcp` is a Click sub-group** (NOT two top-level commands). The group registers `start` and `stop` subcommands. New file: `agent-brain-cli/agent_brain_cli/commands/mcp.py` (NOT extending existing `start.py`/`stop.py` which manage the agent-brain-server, not MCP).
- **No `--foreground` mode** in v3. To run MCP HTTP in the foreground for debugging, operators invoke `agent-brain-mcp --transport http` directly. `agent-brain mcp start` is exclusively the "spawn a daemon, write the runtime file, exit" command.
- **`--state-dir` override flag** on both `start` and `stop` (mirrors existing server-side commands; tests need it for isolation).
- **Shared helpers** live in `agent-brain-cli/agent_brain_cli/mcp_runtime.py` (new module): `read_mcp_runtime(state_dir)`, `write_mcp_runtime(state_dir, data)`, `delete_mcp_runtime(state_dir)`, `MCP_RUNTIME_FILE = "mcp.runtime.json"`, `MCP_LOCK_FILE = "agent-brain-mcp.lock"`, and the psutil verifier.

### Port allocation
- **Strategy:** `--port` argument (default `8765`) defines the **preferred** port; if `bind(127.0.0.1, preferred_port)` fails with `EADDRINUSE`, **fall back to `bind(127.0.0.1, 0)`** so the OS picks a free port. No range scan.
- **Loopback enforcement at CLI layer:** pre-flight check rejects any `--host` override that isn't in `{127.0.0.1, localhost, ::1}` with a `click.UsageError` (exit 2). v3 stays loopback-only per v10.2 HTTP-02 carry-forward.
- **Configurable preferred port:** `--port` flag + `AGENT_BRAIN_MCP_PORT` env (precedence: flag > env > default `8765`).
- **No --host flag in v3:** the loopback-only contract makes `--host` configuration a footgun. Operators who need non-loopback wait for v10.4 OAuth (#188).

### State_dir + lock semantics
- **Reuse `resolve_state_dir_with_fallback`** from `agent-brain-cli/agent_brain_cli/migration.py` — same resolution chain as the server commands.
- **Lock file:** `<state_dir>/agent-brain-mcp.lock` (sibling to existing `agent-brain.lock` for the server). Acquired before the subprocess Popen with `os.open(path, O_CREAT | O_EXCL | O_WRONLY)`; lock file contents = pid of the **parent** `agent-brain mcp start` process for diagnostic value (the spawned subprocess pid lives in `mcp.runtime.json`).
- **Stale lock detection:** on start, if `agent-brain-mcp.lock` exists, read its pid (or `mcp.runtime.json`'s pid if present), check `psutil.pid_exists(pid)`. If the process is dead, **reclaim** the lock (delete + retry). If alive, fail fast with `"agent-brain mcp already running on port {port} (pid {pid}); run 'agent-brain mcp stop' first"` and exit code 1.
- **Lock released on stop:** `agent-brain mcp stop` deletes both `mcp.runtime.json` AND the lock file after process termination.

### Process management
- **`subprocess.Popen` with `start_new_session=True`** (POSIX detach — the subprocess gets its own process group, so SIGTERM via `os.killpg(-pid, SIGTERM)` from `stop` reaches the subprocess + any children it might spawn).
- **Command:** `[sys.executable, "-m", "agent_brain_mcp", "--transport", "http", "--host", "127.0.0.1", "--port", str(resolved_port)]` — uses the current Python interpreter, ensuring the subprocess sees the same venv as the CLI.
- **PID source-of-truth:** the spawned subprocess pid lives ONLY in `mcp.runtime.json`. No separate `mcp.pid` file (avoids drift between two pid sources, lesson from existing server commands).
- **Stdout/stderr capture:** pipe to `<state_dir>/mcp.stdout.log` and `<state_dir>/mcp.stderr.log` (append mode; rotate-free for v3 — Phase 60 hygiene work will revisit if log volume becomes a problem). Subprocess `stdout`/`stderr` close the file handles after the Popen call.
- **Environment:** subprocess inherits the parent CLI's full environment (Phase 60 hardens this to an allowlist). API key + state_dir env vars propagate naturally.
- **Working directory:** subprocess inherits `os.getcwd()` (Phase 60 pins this to a deterministic value).

### Listener-ready verification (psutil + socket polling)
- **Method:** poll `psutil.Process(pid).connections(kind="inet")` filtering for `(LISTEN, laddr.ip == "127.0.0.1", laddr.port == resolved_port)`. Mirrors the v10.2 HTTP-02 pattern in `agent-brain-mcp/agent_brain_mcp/http.py`.
- **Timeout:** `--start-timeout` flag, default **10 seconds**, env `AGENT_BRAIN_MCP_START_TIMEOUT`. (Faster than server's 120s because MCP doesn't load ML deps.)
- **Poll interval:** 100ms (cheap, fast feedback).
- **On success:** write `mcp.runtime.json`, print success line (`"agent-brain-mcp listening on http://127.0.0.1:{port} (pid {pid})"`), exit 0.
- **On timeout:** SIGTERM the subprocess (best-effort), `raise click.ClickException` with stdout/stderr log paths embedded ("agent-brain-mcp did not start within {timeout}s; see {state_dir}/mcp.stderr.log"), exit 1.
- **On subprocess crash during verification:** `psutil.Process(pid)` raises `NoSuchProcess` → surface the stderr log path + last 20 lines, exit 1.

### Stop semantics
- **Grace period:** `--grace` flag, default **5 seconds**, env `AGENT_BRAIN_MCP_STOP_GRACE`.
- **Termination flow:**
  1. Read `mcp.runtime.json`. If missing → print `"agent-brain mcp not running"`, exit 0 (idempotent).
  2. Read pid. If `psutil.pid_exists(pid)` is False → cleanup runtime + lock files, print info message, exit 0.
  3. `os.killpg(os.getpgid(pid), signal.SIGTERM)` — signals the entire process group (catches child processes).
  4. Poll `psutil.pid_exists(pid)` for `--grace` seconds at 100ms intervals.
  5. If still alive after grace → `os.killpg(..., signal.SIGKILL)`, wait additional 1s.
  6. Delete `mcp.runtime.json`, release `agent-brain-mcp.lock`, print success line.
- **Process-group termination:** uses `os.killpg(-pid, SIG)` semantics so any child processes get the signal too. Required because `start_new_session=True` puts the MCP subprocess in its own process group.
- **Idempotent and safe:** running `agent-brain mcp stop` when nothing is running exits 0 with an informational message — not an error.

### CLI integration with `--mcp-transport http`
- **`McpHttpBackend.__init__` discovery hook** — when constructor `url` argument is None (no `--mcp-url` passed, no `AGENT_BRAIN_MCP_URL` env), read `<state_dir>/mcp.runtime.json`, construct `http://{host}:{port}`. Phase 57's `resolve_mcp_transport` in `config.py` lines 591-592 gets the placeholder error message swapped for the design-doc §3.5 wording: `"discovery file not found at <state_dir>/mcp.runtime.json; run 'agent-brain mcp start' or pass --mcp-url"`.
- **Precedence chain (locked):** `--mcp-url` flag → `AGENT_BRAIN_MCP_URL` env → `<state_dir>/mcp.runtime.json` discovery → error (exit 2) with design-doc wording.
- **No silent fallback** — same v10.2 HTTP-03 contract.

### Claude's Discretion
- **Exact log-rotate policy** — v3 ships rotate-free (Phase 60 revisits). Planner picks whether to ship a basic size-based truncation or genuinely append-forever.
- **`--port 0` semantics** — whether `--port 0` explicitly means "ask the OS for a free port" (skipping the preferred-port try). Planner picks; recommend yes — gives operators a clean escape hatch.
- **`mcp.runtime.json` file permissions** — recommend `0o600` (mirrors `config.json` API key file permissions per issue #179). Planner verifies no test fixture relies on world-readable.
- **Whether `start` writes the lock file BEFORE or AFTER the Popen** — recommend BEFORE (acquire lock → Popen subprocess → on Popen failure, release lock). Atomic semantics.
- **Exit code for "already running" case** — recommend `1` (not `2`). Exit code `2` is reserved for usage errors per v10.2 HTTP-03; "already running" is an operational state, not misuse.
- **psutil dependency in `agent-brain-cli`** — `agent-brain-cli` doesn't currently pin psutil. The new mcp commands require it. Planner adds `psutil = "^5.9"` to `agent-brain-cli/pyproject.toml` and notes the dep addition in SUMMARY.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### v3 design doc — the locked schema
- `docs/plans/2026-06-05-mcp-v3-cli-via-mcp.md` §2.4 (lines 176-191) — `mcp.runtime.json` schema verbatim: `{host, port, pid, started_at, transport}`. **All five fields are mandatory and load-bearing.** Phase 58 cannot add or rename fields without a design-doc amendment.
- `docs/plans/2026-06-05-mcp-v3-cli-via-mcp.md` §3.5 (lines 233-235) — no-silent-fallback error wording. Phase 58 finally swaps the Phase 57 placeholder error message for the §3.5 wording about `mcp.runtime.json` discovery.
- `docs/plans/2026-06-05-mcp-v3-cli-via-mcp.md` §4.3 (lines 253-255) — Phase 58 scope per design doc.
- `docs/roadmaps/mcp/v3-cli-via-mcp-and-frameworks.md` — Issue-body v3 scope; helper-command DoD.

### Prior phase artifacts (carry-forward contracts)
- `.planning/phases/57-cli-transport-selector-byte-identical-equivalence/57-CONTEXT.md` — Phase 57 decisions on Click flag wiring, no-silent-fallback, and Phase 58 hand-off points.
- `agent-brain-cli/agent_brain_cli/config.py` lines 591-592 — Phase 57 placeholder error string Phase 58 must replace.
- `agent-brain-mcp/agent_brain_mcp/client.py` — `McpHttpBackend.__init__` is where the discovery-file read lands.

### v10.2 HTTP-02 psutil + socket bind pattern (the reusable verifier)
- `agent-brain-mcp/agent_brain_mcp/http.py` — `run_http()` already uses psutil to verify the kernel bound the port to 127.0.0.1 before announcing the listener. Phase 58's `agent-brain mcp start` reuses the same psutil pattern (poll `Process.connections()` filtering for LISTEN + laddr matches).
- `agent-brain-mcp/tests/test_http_loopback.py` and `tests/test_http_listener.py` — existing test patterns for binding/listening verification.

### Existing server-side helper commands (the structural template for `mcp.py`)
- `agent-brain-cli/agent_brain_cli/commands/start.py` — existing `agent-brain start` server command. `read_config`, `read_runtime`, `LOCK_FILE`, `PID_FILE`, `RUNTIME_FILE` patterns. Phase 58's `mcp.py` mirrors this structure for MCP.
- `agent-brain-cli/agent_brain_cli/commands/stop.py` — existing `agent-brain stop` server command. SIGTERM → grace → SIGKILL flow.
- `agent-brain-cli/agent_brain_cli/migration.py` — `resolve_state_dir_with_fallback` (used identically by start/stop server commands; Phase 58 reuses).
- `agent-brain-cli/agent_brain_cli/xdg_paths.py` — `get_xdg_state_dir`, `migrate_legacy_paths` (Phase 58 commands need these via the standard resolution chain).

### Security + auth carry-forward (issue #179)
- `agent-brain-cli/agent_brain_cli/config.py::resolve_api_key()` — Phase 58's spawned MCP subprocess must receive the API key via env so it can authenticate against agent-brain-server.
- `mcp.runtime.json` file permissions should be `0o600` to match the `config.json` API-key-bearing file pattern from issue #179.

### Click sub-group pattern
- `agent-brain-cli/agent_brain_cli/commands/__init__.py` — how commands are registered with the top-level `cli` group. Phase 58 adds `cli.add_command(mcp)` where `mcp` is the new sub-group exposing `start`/`stop`.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`resolve_state_dir_with_fallback`** (`agent-brain-cli/agent_brain_cli/migration.py`) — same state-dir resolution as server start/stop. Phase 58 reuses identically.
- **`read_config(state_dir)` + `read_runtime(state_dir)` helpers** (`agent-brain-cli/agent_brain_cli/commands/start.py`) — pattern to copy into `mcp_runtime.py` for the MCP variants.
- **psutil + socket-bind verification pattern** (`agent-brain-mcp/agent_brain_mcp/http.py`) — the canonical kernel-bind check; clone for `agent-brain mcp start`'s readiness probe.
- **`get_xdg_state_dir()` + `migrate_legacy_paths()`** (`agent-brain-cli/agent_brain_cli/xdg_paths.py`) — standard state-dir lookup; Phase 58 commands need both.
- **`resolve_api_key()`** (`agent-brain-cli/agent_brain_cli/config.py`) — Phase 58's spawned subprocess gets the API key propagated via env (mirroring how `--transport http`/`uds` works today).

### Established Patterns
- **`subprocess.Popen` + `start_new_session=True` for detached daemons** — already used in `start.py` for the server; same pattern for MCP.
- **`runtime.json` written AFTER bind verification** — the agent-brain-server's `runtime.json` follows this rule; Phase 58 inherits it.
- **Lockfile + stale-pid reclamation** — server `start.py` already has this; copy verbatim.
- **`--state-dir` test-isolation override** — every server command exposes this; Phase 58 follows.
- **No silent fallback (v10.2 HTTP-03 + Phase 57 carry-forward)** — every transport selection failure exits non-zero with verbatim wording.

### Integration Points
- **Top-level `cli` Click group** (`agent-brain-cli/agent_brain_cli/cli.py`) — register the new `mcp` sub-group here.
- **`agent-brain-cli/agent_brain_cli/commands/__init__.py`** — add `from .mcp import mcp` and register.
- **`agent-brain-mcp/agent_brain_mcp/client.py::McpHttpBackend.__init__`** — discovery-file read lands here when `url=None`.
- **`agent-brain-cli/agent_brain_cli/config.py::resolve_mcp_transport()`** lines 591-592 — Phase 57 placeholder error string replaced with §3.5 wording.
- **`agent-brain-cli/pyproject.toml`** — add `psutil = "^5.9"` dep (new for CLI; already pinned in agent-brain-mcp).

</code_context>

<specifics>
## Specific Ideas

- **Mirror server's `start.py`/`stop.py` structurally but DO NOT extend them.** A separate `commands/mcp.py` keeps the `agent-brain mcp ...` namespace clean and avoids the `start` command meaning "server OR MCP" depending on args (footgun).
- **Use `os.killpg` + process-group semantics** (not plain `os.kill`) so children of the MCP subprocess get the signal too. This becomes load-bearing in Phase 60's 1000-invocation orphan test — Phase 58 lays the foundation.
- **`mcp.runtime.json` is `0o600`** matching the `config.json` API-key file convention from issue #179.
- **The `psutil` dep addition to `agent-brain-cli/pyproject.toml`** is a real dep change — planner verifies `task before-push` exit 0 and notes it in SUMMARY (`+1 transitive dep across CLI package`).
- **Plans should be sequenced:**
  - Plan 58-01: `mcp_runtime.py` shared helpers + schema + file IO + lockfile + psutil verifier (CLI-MCP-08 prereq).
  - Plan 58-02: `commands/mcp.py` with `mcp start` (port allocation, Popen, lock, psutil-verified write of `mcp.runtime.json`) + Click registration + `--state-dir`/`--port`/`--start-timeout` flags (CLI-MCP-09).
  - Plan 58-03: `commands/mcp.py` `mcp stop` (SIGTERM → grace → SIGKILL → cleanup) + `McpHttpBackend.__init__` discovery integration + Phase 57 placeholder wording swap (CLI-MCP-08 + CLI-MCP-10). Plan 58-03 closes the loop end-to-end with an integration test: `mcp start → agent-brain --transport mcp --mcp-transport http query "X"` succeeds with NO `--mcp-url` → `mcp stop` cleans up.

</specifics>

<deferred>
## Deferred Ideas

- **Subprocess hygiene** (pinned cwd, env allowlist, persistent subprocess for stdio backend, 1000-invocation orphan test) → Phase 60. Phase 58 ships full env inheritance + `os.getcwd()` defaults.
- **Log rotation / structured logging from MCP subprocess** → Phase 60 hygiene work; v3 ships append-forever logs.
- **Multi-instance MCP listeners per state_dir** → out of v10.3 (design doc §2.4 explicitly: single-file, single-instance).
- **`agent-brain mcp restart`** companion → not in v10.3 scope; operators chain `stop && start` manually.
- **`agent-brain mcp status`** companion (read runtime, show pid + uptime + port) → nice-to-have but NOT a milestone DoD; planner may add as a fourth plan if cost is trivial, otherwise leave for v10.4.
- **Health endpoint polling** as an alternative to psutil bind verification → considered but rejected for v3 (psutil pattern is already proven in HTTP-02; HTTP roundtrip adds dep on full uvicorn boot).
- **`--port 0` explicit "ask OS" semantics** — Claude's Discretion; planner may ship this in Plan 58-02 as a small UX win.
- **Auto-restart on crash / supervisor** → out of v10.3 scope.
- **Windows process-group semantics** → out of project scope per CLAUDE.md.
- **OAuth 2.1 for remote MCP** → v10.4 (#188); requires `--host` override which v3 explicitly forbids.

</deferred>

---

*Phase: 58-runtime-discovery-helper-commands*
*Context gathered: 2026-06-07 (auto mode — recommended defaults selected)*
