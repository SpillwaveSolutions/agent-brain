# Plan: Issue #179 — REST API Key Authentication (server + CLI + MCP)

**Branch:** `security/issue-179-api-key-auth`
**Target milestone:** v10.3-prep (hotfix-class security work; can ship as v10.2.1 patch)
**Issue:** [#179 server exposes all endpoints with no authentication (critical)](https://github.com/SpillwaveSolutions/agent-brain/issues/179)

---

## Context

`agent-brain-server`'s FastAPI app currently has **zero authentication** on all data endpoints. `127.0.0.1` binding is not an authorization control — any local process can read or wipe the index. This is the only open issue marked **critical** in its title and was explicitly deferred during v10.2 ("Bearer-token API auth mid-flight", surfaced in Phase 50 design doc).

The fix introduces an optional `AGENT_BRAIN_API_KEY` with an `X-API-Key` header enforcement, default-no-auth on loopback to preserve the single-user dev UX, and a strict fail-fast when bound non-loopback without a key. CLI and MCP clients are updated in lockstep so enabling auth doesn't silently break the MCP layer.

**Locked decisions:**

1. **Default mode (strict-on-non-loopback):** No-auth on `127.0.0.1` if `AGENT_BRAIN_API_KEY` is empty. Refuse to start (`exit_code=2`) if `API_HOST != 127.0.0.1` and key unset. Loud warn-and-continue if loopback + no key.
2. **Scope:** server + CLI + MCP in this PR. CORS wildcard (`allow_origins=["*"]`) tightening filed as separate follow-up issue.
3. **Docs gating:** `/docs`, `/redoc`, `/openapi.json` gated when `AGENT_BRAIN_API_KEY` set AND `DEBUG=false`. Stays open in DEBUG.

---

## Files Affected

### `agent-brain-server` — enforcement side

| File | Change |
|---|---|
| `agent_brain_server/config/settings.py` (lines 14–154) | Add `AGENT_BRAIN_API_KEY: str = ""` field next to OPENAI/ANTHROPIC keys. Pydantic v2 style, no prefix, matching existing convention. |
| `agent_brain_server/api/security.py` (**new**, ~50 LOC) | Implements `verify_api_key` FastAPI dependency reading `X-API-Key` header. Returns no-op when settings key empty; raises `HTTPException(401)` on missing/mismatched when key is set. Uses `secrets.compare_digest` for constant-time compare. |
| `agent_brain_server/api/routers/{index,cache,folders,jobs,query,graph}.py` (6 files) | Add module-level `router = APIRouter(dependencies=[Depends(verify_api_key)])` so every endpoint inherits the dependency. **Health router is intentionally exempt.** |
| `agent_brain_server/api/main.py` (lines 672–702 + lifespan ~766–779) | Startup gate: in lifespan, if `settings.API_HOST != "127.0.0.1"` and `settings.AGENT_BRAIN_API_KEY == ""` → log critical + `sys.exit(2)` with message. Else if loopback + no key → loud warning via logger. Gate `/docs`, `/redoc`, `/openapi.json` by passing `docs_url=None, redoc_url=None, openapi_url=None` to `FastAPI()` when key set + DEBUG false; re-mount under `Depends(verify_api_key)` in that case. |
| `agent_brain_server/runtime.py` (lines 16–34, 37–47) | Extend `RuntimeState` with `api_key: str \| None = None`. `write_runtime()` writes the file with `Path.chmod(0o600)` after write (defense-in-depth — state_dir is already user-owned). |
| `.env.example` | Document `AGENT_BRAIN_API_KEY=` with a one-line comment. |

### `agent-brain-cli` — client side

| File | Change |
|---|---|
| `agent_brain_cli/client/api_client.py` (line 155–265, `DocServeClient`) | Add `api_key: str \| None = None` to `__init__`. When set, pass `headers={"X-API-Key": api_key}` to `httpx.Client(...)`. `from_httpx` honors a separate `api_key` kwarg for UDS path. |
| `agent_brain_cli/client/transport.py` (lines 24–54, `open_client`) | After resolving base_url/socket_path, resolve API key via: `AGENT_BRAIN_API_KEY` env → `runtime.json::api_key` (via existing `read_runtime`) → `None`. Pass to `DocServeClient` constructor. |
| `agent_brain_cli/commands/init.py` (lines 1–79) | On `agent-brain init`: generate `secrets.token_urlsafe(32)` → write to `runtime.json::api_key` (or staged config if runtime.json doesn't exist yet, since `init` precedes `start`). Print a one-line note: "API key generated and stored in `.agent-brain/runtime.json` (mode 600)." Add `--no-api-key` flag for opt-out (single-user devs who want the legacy no-auth behavior). |
| `agent_brain_cli/config.py` (~line 245–251) | If extending env resolution, mirror server-side env var name to keep ops simple. |

### `agent-brain-mcp` — client side (the gap the issue missed)

| File | Change |
|---|---|
| `agent_brain_mcp/client.py` (`ApiClient`, lines 22–79) | No internal change — `ApiClient` already accepts a pre-configured `httpx.Client`. Caller must inject the header. |
| `agent_brain_mcp/config.py` (lines 1–24, backend URL resolution + `MCPSubscriptionSettings`) | Extend backend resolution order with API key lookup parallel to URL: `AGENT_BRAIN_MCP_API_KEY` env → `AGENT_BRAIN_API_KEY` env → `runtime.json::api_key` → `None`. Surface as `backend_api_key` on the resolved config dataclass/model. |
| The MCP entrypoint that constructs the httpx.Client for `ApiClient` (find via grep `ApiClient(`) | When `backend_api_key` is set, build `httpx.Client(headers={"X-API-Key": ...})`. |

---

## Test Strategy

Tests live in their respective packages; coverage gate is ≥80% per package (matches v10.2 floors).

### `agent-brain-server/tests/`

- **New fixture** in `tests/conftest.py`: `app_with_api_key(monkeypatch)` — sets `AGENT_BRAIN_API_KEY="test-key-123"` via `monkeypatch.setenv`, clears `get_settings` lru_cache, returns `TestClient`. Also returns the key so tests can header-inject.
- **Per-router test class** in `tests/unit/api/test_auth_enforcement.py` (new) — for each of the 6 gated routers, parametrized over one representative endpoint: `(no header → 401)`, `(wrong key → 401)`, `(correct key → 200)`. Plus a `health` parametrization confirming health stays open even with key set.
- **Existing tests stay green** via the empty-key default — verify by running unchanged.
- **Startup-gate test** in `tests/unit/test_api_main_startup.py` (likely new): subtest 1 — `API_HOST=0.0.0.0` + no key → process exits with code 2. Subtest 2 — `API_HOST=127.0.0.1` + no key → warning logged, app starts. Subtest 3 — `API_HOST=0.0.0.0` + key set → app starts cleanly.
- **/docs gating tests**: when `AGENT_BRAIN_API_KEY` set AND `DEBUG=false` → `GET /docs` returns 401 without header, 200 with. With `DEBUG=true` → `/docs` always 200.

### `agent-brain-cli/tests/`

- **`api_client` header injection test**: instantiate `DocServeClient(base_url="http://test", api_key="k")` → check `self._client.headers["X-API-Key"] == "k"`.
- **`transport.open_client` resolution test**: monkeypatch env + runtime.json → verify resolution order.
- **`init` command test**: invoke via `CliRunner`, assert generated `runtime.json` contains `api_key` field of 32-byte urlsafe length; assert `--no-api-key` skips generation.

### `agent-brain-mcp/tests/`

- **Layer 1 contract** (`tests/contract/test_layer1_*.py`): the existing `fake_httpx_client` fixture must accept and pass through `X-API-Key`; one new test confirms a tool round-trip with the header set.
- **Layer 2 SDK contract** (`tests/contract/test_layer2_*.py`): one smoke test that starts the MCP subprocess with `AGENT_BRAIN_API_KEY` env and confirms it propagates to the backend httpx client.
- **Config resolution test**: env precedence and runtime.json fallback for `backend_api_key`.

### Reference test files (for style matching)
- `agent-brain-server/tests/unit/api/test_health_config.py` (lines 22–50) — router-level mock pattern with `_create_app()` helper + `TestClient`.
- `agent-brain-server/tests/conftest.py` (lines 78–112) — `isolate_provider_settings` autouse pattern + how `get_settings` cache is cleared.

---

## Implementation Sequence

1. **Branch:** `git checkout -b security/issue-179-api-key-auth` (clean from `main`).
2. **Server settings + security module:** add `AGENT_BRAIN_API_KEY` field + `api/security.py` + unit tests for `verify_api_key` dependency in isolation (mock settings).
3. **Server router wiring:** add `dependencies=[Depends(verify_api_key)]` to the 6 non-health routers + per-router auth tests. Existing tests stay green.
4. **Startup gate + /docs gating** in `api/main.py` + tests for the 3 startup matrix cases and the /docs DEBUG behavior.
5. **Runtime schema bump:** `RuntimeState.api_key` field + `write_runtime` chmod 0o600 + tests.
6. **CLI client header propagation:** `DocServeClient` + `transport.open_client` + tests.
7. **CLI init key generation:** `commands/init.py` + `--no-api-key` flag + tests.
8. **MCP config + client header injection:** `config.py` resolution + entrypoint httpx headers + contract tests for both layers.
9. **Docs:** update `.env.example`, README quickstart blurb ("for shared hosts, set `AGENT_BRAIN_API_KEY`"), CHANGELOG entry.
10. **Self-review:** run the auth path end-to-end manually against a local server (start without key on loopback → succeeds with warning; set key + start → all CLI calls work; unset CLI key → 401).

---

## Verification (mandatory before push, per CLAUDE.md)

1. `task before-push` from repo root — **must exit 0**. This runs format/lint/typecheck/test across all packages including the DR-5 monorepo integration (agent-brain-mcp + agent-brain-uds). Per memory: this catches silent regressions cross-package.
2. `task pr-qa-gate` from repo root — must exit 0.
3. Per-package coverage gate: agent-brain-server ≥80%, agent-brain-cli ≥80%, agent-brain-mcp ≥80% (matches v10.2 floors).
4. Manual smoke (recorded in PR description):
   - `agent-brain-serve` on default loopback, no key → starts with warning, `curl http://127.0.0.1:8000/health` → 200, `curl http://127.0.0.1:8000/query` POST → 200 (no auth required).
   - Set `AGENT_BRAIN_API_KEY=xxx`, restart → `curl /query` without header → 401, with `-H "X-API-Key: xxx"` → 200, `/health` → 200 either way.
   - `API_HOST=0.0.0.0 agent-brain-serve` without key → exits 2 with clear log line.
   - `agent-brain query "test"` end-to-end via CLI with `runtime.json::api_key` present → 200 (CLI injects header).
   - `agent-brain-mcp --transport stdio` with `AGENT_BRAIN_API_KEY` env set → search_documents tool succeeds against authed backend.

---

## Out of Scope (file as follow-up issues)

- **CORS wildcard tightening** — `agent_brain_server/api/main.py:687-693` uses `allow_origins=["*"]` with `allow_credentials=True`. Tracked separately per the issue's own carve-out.
- **Authorization: Bearer / OAuth 2.1** — covered by future MCP v4 (#188). `X-API-Key` is the API-key idiom; `Bearer` semantics are for OAuth tokens.
- **/mcp/subscriptions debug endpoint (#194)** — orthogonal v3-labeled improvement.

---

## Risks & Mitigations

- **Risk:** Enabling `AGENT_BRAIN_API_KEY` on an existing deployment breaks every running CLI/MCP that lacks the new key.
  **Mitigation:** Default-no-auth on loopback means existing single-user dev installs keep working unchanged. Multi-user/shared hosts must set the key and rotate clients together — surfaced in CHANGELOG `BREAKING (if you bind non-loopback)` section.

- **Risk:** Layer 2 SDK contract test for MCP starts a subprocess; passing the key via env is straightforward but the existing harness may need a small addition to set env before spawn.
  **Mitigation:** Implement env passthrough in the existing subprocess fixture; add the fixture extension as the first MCP commit.

- **Risk:** `get_settings()` is `@lru_cache`-decorated; tests changing env via `monkeypatch.setenv` won't see the new value unless cache is cleared.
  **Mitigation:** Test fixture explicitly calls `get_settings.cache_clear()` (pattern already used elsewhere in conftest — verify and reuse).

- **Risk:** Phase 51's `MIN_BACKEND_VERSION` check in MCP — bumping server to a new version may force MCP to bump too.
  **Mitigation:** This is an auth feature, not a protocol change. Server version bumps to 10.2.1 (patch); `MIN_BACKEND_VERSION` stays at 10.2.0 unless we want to require auth-capable backend (we don't, since default is no-auth). No version-pin change needed.
