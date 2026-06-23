---
phase: 69-mcphttpbackend-client-side-oauth-dance
status: passed
verified: 2026-06-17
verifier: inline (gsd-verifier unavailable — transient API 529; orchestrator performed goal-backward verification with full evidence)
requirement_ids: [OAUTH-07]
must_haves_verified: 4
must_haves_total: 4
---

# Phase 69 Verification — McpHttpBackend Client-Side OAuth Dance

**Goal:** McpHttpBackend handles the full OAuth dance transparently — the CLI user
authenticates once, tokens persist across Pattern A per-call invocations via
FileTokenStorage, and subsequent calls reuse the cached token without re-triggering
the browser redirect.

**Result: PASSED** — all 4 ROADMAP success criteria are delivered by code + tests in the
actual codebase (goal-backward verified, not task-completion-only). `task before-push`
exits 0 (974 MCP + 577 CLI + 1388 server + 32 UDS tests; `agent_brain_mcp/oauth/`
coverage ~91%, already exceeding the Phase 70 ≥90% DoD target).

## Success Criteria

### SC#1 — 401 → transparent dance → retry with Bearer (browser once, then silent)
**VERIFIED.** `agent_brain_mcp/oauth/oauth_client.py::build_oauth_client_provider(server_url, state_dir)`
assembles the SDK `OAuthClientProvider` (which drives PRM→OASM discovery → PKCE → auth-code
flow → token refresh internally) wired to `FileTokenStorage`, `build_redirect_handler`, and
`build_callback_handler`, with `timeout=300.0` and the DCR path (no `client_metadata_url`).
`client.py::_http_session()` injects it via `streamablehttp_client(self.url, auth=self._get_auth())`.
Test: `test_oauth_client_dance_e2e.py::TestSC1DanceAndRetry::test_dance_fires_redirect_spy_once_and_persists_token`.

### SC#2 — tokens persisted to state_dir/mcp-oauth-tokens.json (0o600), reused without re-dance
**VERIFIED.** `token_storage.py::FileTokenStorage` implements all 4 `TokenStorage` protocol
methods (`get_tokens`, `set_tokens`, `get_client_info`, `set_client_info`), writes to
`state_dir/mcp-oauth-tokens.json`, and calls `os.chmod(path, 0o600)` unconditionally after
every write. Tests: `test_oauth_file_token_storage.py` (round-trip, coexistence,
`(st_mode & 0o077) == 0` not-world-readable assertion, corrupt-file graceful) +
`test_oauth_client_dance_e2e.py::TestSC2PersistReuseWithoutRedance` (cached token loads, the
`redirect_handler` spy is NOT called again).

### SC#3 — expired access + valid refresh → silent refresh, no interaction
**VERIFIED.** The SDK `OAuthClientProvider` performs the `grant_type=refresh_token` exchange;
the persisted refresh token is loaded from `FileTokenStorage`. Tests:
`test_oauth_client_dance_e2e.py::TestSC3SilentRefresh::test_silent_refresh_no_redirect_no_interaction`
and `test_storage_reflects_refreshed_token`.

### SC#4 — MCP→REST keeps X-API-Key; OAuth token NEVER forwarded upstream (OAUTH-08 confused-deputy)
**VERIFIED.** Dedicated test `test_oauth_confused_deputy.py` targeting the real seam
(`config.py::_open_http_client` / `open_backend_client`):
- `TestXApiKeyPresentOAuthAbsent::test_x_api_key_and_no_authorization_together` — X-API-Key
  present AND Authorization absent simultaneously (the combined assertion).
- `TestOAuthTokenDoesNotLeakUpstream` — asserts `all(oauth_access_token not in v for v in
  client.headers.values())` even when an OAuth token exists in storage.

## Additional Invariants (from CONTEXT locked decisions)

| Invariant | Evidence | Status |
|-----------|----------|--------|
| Opt-in default OFF (byte-identical auth=None path) | `client.py::_get_auth` returns None unless `AGENT_BRAIN_MCP_AUTH=oauth`; `test_mcp_http_backend_oauth.py` asserts default-OFF + non-oauth-value paths | PASS |
| 17 connection sites centralized | `grep -c "streamablehttp_client(" client.py` == 1; `_http_session` referenced 19× | PASS |
| McpStdioBackend untouched (no OAuth on stdio) | `stdio_client(` count unchanged in client.py | PASS |
| Provider lazy, once per instance | `_auth_provider` cache; test asserts same object on 2nd call | PASS |
| DCR (no CIMD) | factory builds without `client_metadata_url` | PASS |
| transport.py threads state_dir | `McpHttpBackend(url=..., timeout=..., state_dir=state_dir)` | PASS |

## Requirement Traceability

| REQ-ID | Plans | Status |
|--------|-------|--------|
| OAUTH-07 | 69-01, 69-02, 69-03, 69-04 | Complete (marked `[x]` in REQUIREMENTS.md) |

## Quality Gate

`task before-push` exits 0 — 974 MCP + 577 CLI + 1388 server + 32 UDS tests pass; Black/Ruff/mypy
clean; `agent_brain_mcp/oauth/` module coverage ~91%.

## Notes

- `gsd-verifier` subagent was unavailable due to a transient Anthropic API 529 (Overloaded).
  Verification was performed inline by the orchestrator with full grep/test evidence as recorded
  above. Recommend a confirmatory `/gsd:verify-work 69` (conversational UAT) when convenient — the
  browser-open UX (SC#1 first-invocation) is the one path best confirmed by a human against a live AS.
