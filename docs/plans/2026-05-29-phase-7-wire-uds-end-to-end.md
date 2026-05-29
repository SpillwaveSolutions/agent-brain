# Phase 7 — Wire UDS End-to-End + Reviewer Findings

**Date:** 2026-05-29
**Status:** Approved — execute on `feat/mcp-uds-transport`
**Source:** Code-review findings on commits `1e95576..a23ca15`; user picked "Fix UDS, ship full 10.1.0"
**Parent plan:** `docs/plans/2026-05-28-mcp-uds-transport-design.md`

---

## 1. Pre-flight

- Branch: `feat/mcp-uds-transport`, 12 commits ahead of main, clean working tree
- `task before-push` green at HEAD
- TDD: every new code path lands RED → GREEN

## 2. Root cause

Three findings collapse to one root cause: **between Phase 1 spike and Phase 2 production, the CLI → server UDS wire was never connected**.

- CLI's `start.py:322-330` builds `python -m uvicorn agent_brain_server.api.main:app …` — bypasses the server's `cli()` / `run()` entry entirely.
- Server's `run()` (`main.py:779`) ignores `AGENT_BRAIN_UDS*` env vars; calls plain `uvicorn.run(host=..., port=...)`.
- `uds_bind.serve_dual` / `serve_uds_only` exist, are tested directly, never called from production.
- Server-side socket is created by uvicorn at default umask (~0755); `validate_socket()` rejects.
- `write_pointer_file()` is exported but has zero non-test callers; long-path fallback dead end-to-end.

Tests didn't catch any of this because every `serve_dual`/`serve_uds_only` test calls those helpers directly, never the public `agent-brain start --uds` path.

## 3. Scope — MUST-FIX (blocks release)

### A1 — Route CLI through `agent-brain-serve`, wire `run()` to honor UDS env vars

- `agent-brain-cli/agent_brain_cli/commands/start.py:322-331` — replace `python -m uvicorn agent_brain_server.api.main:app --host X --port Y` with `agent-brain-serve --host X --port Y` (state_dir still passed via `AGENT_BRAIN_STATE_DIR` env). Behaviour identical for HTTP-only because `cli()` → `run()` → `uvicorn.run(...)` is unchanged.
- `agent-brain-server/agent_brain_server/api/main.py::run()` — at the top, read `AGENT_BRAIN_UDS_ONLY` and `AGENT_BRAIN_UDS` env. Resolve socket path from `AGENT_BRAIN_UDS_PATH` or compute from `state_dir`. Branch:
  - `_ONLY=1` → `asyncio.run(uds_bind.serve_uds_only(app, socket_path=...))`
  - `_UDS=1` (dual) → `asyncio.run(uds_bind.serve_dual(app, host=..., port=..., socket_path=...))`
  - neither → existing `uvicorn.run(...)` (no behaviour change)
- Loud refusal when `state_dir` is None and UDS is requested without an explicit `AGENT_BRAIN_UDS_PATH`.

### A2 — chmod 0600 the socket post-bind

- `agent-brain-server/agent_brain_server/api/uds_bind.py` — gain a private `_chmod_socket_when_ready(socket_path)` async task that polls (≤5 s, 100 ms cadence) for socket existence and then `os.chmod(socket_path, 0o600)`. Also `os.chmod(parent_dir, 0o700)` if not already.
- `serve_uds_only` / `serve_dual` add the chmod task to their gather set. Gather doesn't terminate when one task completes; servers keep running.
- Plan §8 docstring on `permissions.py::validate_socket` is now actually true.

### A3 — Long-path fallback + `write_pointer_file` server-side

- Add a helper in `uds_bind.py` (or factor into a new helper module) that, given a `(state_dir, requested_socket_path)`:
  - If `len(str(requested_socket_path)) >= MAX_SOCKET_PATH_BYTES`: derive the `/tmp/agent-brain-<hash>.sock` fallback path (use `resolve_socket_path`'s logic OR import `_short_fallback_path`) and call `write_pointer_file(state_dir, fallback)`.
  - Return the path uvicorn should actually bind.
- `run()` calls this helper before invoking the bind helpers.
- Unit test in `agent-brain-server/tests/` driving the helper with a long mock path; asserts pointer file is written and contents match.

### A4 — Real end-to-end test

- New `agent-brain-cli/tests/integration/test_cli_start_uds_e2e.py` (or `agent-brain-server/tests/integration/...`): spawns `agent-brain start --uds` as a subprocess against a tmp `--project-dir`, waits for readiness, probes:
  - `GET http://host:port/health/` returns 200
  - `GET --unix-socket <sock> http://localhost/health/` returns 200
  - `os.lstat(sock).st_mode & 0o777 == 0o600`
  - `os.lstat(sock.parent).st_mode & 0o777 == 0o700`
- Marked `slow` / opt-in; runs in `task e2e` or similar opt-in target.

## 4. Scope — SHOULD-FIX (cheap, ship with A)

### B1 (#4) — Probe UDS before writing `socket_path` to `runtime.json`

- `agent-brain-cli/agent_brain_cli/commands/start.py:425-435` — after the HTTP readiness probe, also probe the UDS socket via `httpx.HTTPTransport(uds=socket_path)`. If it fails, log warning, override `runtime_state["socket_path"] = None`, re-write runtime.json.

### B2 (#5) — Rename `INVALID_REQUEST` → `BACKEND_CONFLICT`

- `agent-brain-mcp/agent_brain_mcp/errors.py` — rename the constant (value stays -32000). Add a code comment "// NB: -32000 is the app-defined range; this is NOT JSON-RPC's standard -32600 InvalidRequest."
- Update `test_error_mapping.py` parameterization to use the new name.

### B3 (#6) — Tighten import-linter MCP contract

- `.importlinter` — expand `mcp never calls server internals` forbidden_modules to include `agent_brain_server.config`, `.providers`, `.runtime`, `.storage_paths`, `.job_queue`. Keep `.models` allowed per plan §3 invariant 3.

### B4 (#7) — MCP `_open_uds_client` reads `runtime.json::socket_path`

- `agent-brain-mcp/agent_brain_mcp/config.py:82-92` — before `resolve_socket_path(state_dir)`, check `<state_dir>/runtime.json` for `socket_path` and use it if set. Mirror `_resolve_http_url`'s pattern.

## 5. Scope — CONSIDER quick wins (defensive)

- **C1 (#9)** — `agent-brain-mcp/agent_brain_mcp/tools/jobs.py::_decode_cursor`: raise `McpError(INVALID_PARAMS, "cursor: malformed")` instead of silently restarting from offset 0.
- **C2 (#10)** — Apply `.expanduser()` to all `AGENT_BRAIN_UDS_PATH` reads (3 sites: `agent-brain-uds/client.py`, `agent-brain-mcp/config.py`, `agent-brain-cli/config.py`).
- **C3 (#12)** — `agent-brain-mcp/agent_brain_mcp/errors.py:50-51` — truncate `response.text` to 2048 bytes before stashing in `data.cause`.

## 6. Validation (mandatory — fail any → fix, re-run)

```bash
task uds:pr-qa-gate        # UDS package — must stay green
task mcp:pr-qa-gate        # MCP package — must stay green (BACKEND_CONFLICT rename)
task mcp:e2e               # 4 official-SDK e2e — must stay green
task check:layering        # 3 contracts kept, 0 broken (tighter MCP forbidden set still passes)
task before-push           # root gate — must stay green (CLI tests still pass)
# Plus new test:
pytest <new-e2e-test> -v   # CLI start --uds drives the full wire
```

If any fails: fix, re-run, repeat. **Do not push on a yellow gate.**

## 7. Out-of-tree (after Phase 7 commit + gates green)

Authorization-gated, listed for clarity:

1. `git push -u origin feat/mcp-uds-transport`
2. `gh pr create --base main` against `main`
3. Wait for CI green; address any review
4. Merge PR (squash or rebase per repo convention)
5. **Manual:** edit `.claude/commands/ag-brain-release.md` to match `release_agent.md` if not already done (auto-mode blocked me earlier; user applied)
6. `/ag-brain-release minor` → lockstep 10.0.7 → 10.1.0, build wheels, PyPI publish
7. `gh issue create --body-file docs/roadmaps/mcp/v2-subscriptions-and-resources.md` (title from §15.1)
8. Same for v3, v4
9. Meta-issue from `docs/roadmaps/mcp/README.md` (title from §15.4)
10. Update `docs/roadmaps/mcp/README.md` checkbox lines with the assigned `#NNN` issue numbers

## 8. Risks / unknowns

- **Switching CLI's server_cmd from `python -m uvicorn` to `agent-brain-serve`** is the only behavioural change for HTTP-only users. Both end up calling `uvicorn.run(...)` with the same args, so this should be a no-op — but worth a smoke test of the HTTP-only daemonize path before claiming Phase 7 done.
- **Reading runtime.json then re-writing it** (B1) introduces a small race: a parallel process reading the file between our two writes sees an intermediate state. Low impact (the only consumer is `agent-brain list`); acceptable.
- **`asyncio.gather(server_tcp.serve(), server_uds.serve(), chmod_task)`** — gather doesn't terminate when the chmod task completes, so the servers continue. Verify by inspection; the existing `serve_dual` test (which currently has only 2 tasks) will need a small update if the chmod task raises an exception (gather cancels everything in that case).
- **Daemonized mode** writes a different runtime.json (start.py:408-420) than the foreground path (start.py:355-367). Both currently include `socket_path`. B1's UDS-probe needs to run in both branches.
