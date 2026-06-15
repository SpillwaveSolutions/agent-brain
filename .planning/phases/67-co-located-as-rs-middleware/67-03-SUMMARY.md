---
phase: 67-co-located-as-rs-middleware
plan: 03
subsystem: auth
tags: [mcp, oauth, cimd, ssrf, dns-rebinding, client-registration, security]

# Dependency graph
requires:
  - phase: 67-co-located-as-rs-middleware
    plan: 02
    provides: "AgentBrainAuthServerProvider (register_client), config.resolve_client_id_allowlist()"

provides:
  - "agent_brain_mcp/oauth/registration.py: CIMD fetch with full SSRF control stack"
  - "is_blocked_ip(): RFC-1918/loopback/link-local IP block (unconditional)"
  - "validate_client_id_host(): allowlist gate + unconditional IP literal block"
  - "fetch_client_metadata(): allowlist + DNS pre-resolution + post-resolution IP check + 5s timeout"
  - "RegistrationError400: 400-class rejection error for CIMD SSRF controls"
  - "AgentBrainAuthServerProvider.register_client: URL-shaped client_ids routed through CIMD fetch"
  - "33 tests in test_oauth_cimd_ssrf.py (SSRF + DNS-rebinding mandatory test)"

affects:
  - 67-04-plan  # provider.register_client now SSRF-guarded; Plan 04 mounts create_auth_routes()
  - phase-69-client-dance  # client_id CIMD flow fully guarded; McpHttpBackend dances this AS

# Tech tracking
tech-stack:
  added:
    - "agent_brain_mcp/oauth/registration.py (new module)"
    - "ipaddress stdlib: IPv4Network/IPv6Network/ip_address for CIDR membership checks"
    - "socket.getaddrinfo: synchronous DNS resolution for pre-fetch IP validation"
  patterns:
    - "TDD RED/GREEN: test file written first, ImportError confirmed, then implementation"
    - "Fake async context manager classes (not MagicMock) for httpx.AsyncClient stubs"
    - "socket.getaddrinfo monkeypatching for DNS-rebinding test isolation"
    - "noqa: N818 for RegistrationError400 (HTTP status suffix, not exception type suffix)"
    - "str(sockaddr[0]) cast to satisfy mypy strict on socket.getaddrinfo addr_info tuple"

key-files:
  created:
    - "agent-brain-mcp/agent_brain_mcp/oauth/registration.py"
    - "agent-brain-mcp/tests/test_oauth_cimd_ssrf.py"
  modified:
    - "agent-brain-mcp/agent_brain_mcp/oauth/provider.py (register_client CIMD dispatch)"

key-decisions:
  - "resolve-then-validate DNS-rebinding approach (not custom httpx transport): socket.getaddrinfo BEFORE fetch; run is_blocked_ip over all resolved IPs; raise RegistrationError400 on any blocked IP — cleanest testable form per design doc"
  - "TOCTOU window documented: DNS cache may be flushed between getaddrinfo and TCP connect; acceptable for Shape A single-user co-located deployment"
  - "URL-shaped dispatch in register_client: urllib.parse.urlparse checks scheme+netloc; non-URL opaque client_ids skip fetch entirely (static pre-registration preserved)"
  - "RegistrationError400 with noqa:N818 rather than RegistrationClientMetadataError — the 400 suffix is the RFC 7591 status code signal, more readable for operators"
  - "Fake class stubs for httpx.AsyncClient tests (not MagicMock): avoids infinite recursion from side_effect patching and TypeError from non-awaitable MagicMock.get() return"

requirements-completed: [OAUTH-10]

# Metrics
duration: 9min
completed: 2026-06-15
---

# Phase 67 Plan 03: CIMD Registration + SSRF Stack Summary

**CIMD fetch with allowlist gate + unconditional private-IP block + DNS-rebinding
post-resolution re-validation + 5s timeout; register_client routes URL-shaped client_ids
through the guarded fetch; static pre-registration preserved; 33 tests green**

## Performance

- **Duration:** 9 min
- **Started:** 2026-06-15T01:17:26Z
- **Completed:** 2026-06-15T01:26:26Z
- **Tasks:** 2
- **Files created:** 2 (1 source, 1 test)
- **Files modified:** 1 (provider.py)
- **Tests added:** 33

## Accomplishments

### Task 1: CIMD allowlist + private-IP block + 5s timeout (`ff5b8da`)

Created `agent_brain_mcp/oauth/registration.py`:

- `_BLOCKED_NETWORKS`: explicit CIDR list covering RFC-1918 (10/172.16/192.168),
  loopback (127/::1), link-local (169.254/fe80::), unique-local (fc00::/7)
- `is_blocked_ip(ip)`: True for any address in `_BLOCKED_NETWORKS` OR with
  `is_private`/`is_loopback`/`is_link_local` set (belt-and-suspenders)
- `validate_client_id_host(url, allowlist)`: parses URL, rejects empty/no-scheme/no-host;
  unconditionally blocks IP literals in private ranges BEFORE allowlist check;
  rejects non-allowlisted hostnames — returns validated hostname
- `RegistrationError400`: 400-class exception (noqa:N818 for HTTP status suffix)
- `fetch_client_metadata(url, *, allowlist, timeout_s=5.0)`: calls validate_client_id_host
  first (no network on rejection); then DNS resolution; then post-resolution IP check;
  then `httpx.AsyncClient(timeout=httpx.Timeout(timeout_s)).get(url)`

Tests (partial, Task 1 set): 28 tests — `is_blocked_ip` parametrized (13 blocked +
4 public), `validate_client_id_host` (allowlist gate, IP literal unconditional block,
missing scheme, empty URL), `fetch_client_metadata` timeout capture, no-network-on-rejection

### Task 2: DNS-rebinding mitigation + provider.register_client wiring (`e49811e`)

Extended `registration.py`:

- DNS resolution via `socket.getaddrinfo(hostname, None)` BEFORE the HTTP fetch
- Post-resolution loop: `str(sockaddr[0])` → `is_blocked_ip()` → `RegistrationError400`
  if any resolved IP is blocked (covers DNS-rebinding: allowlisted hostname resolving
  to 169.254.169.254 is still rejected)

Extended `provider.py`:

- `register_client` now imports `fetch_client_metadata` + `resolve_client_id_allowlist`
- URL-shaped client_id detection: `urllib.parse.urlparse` checks `scheme + netloc`
- URL-shaped → `await fetch_client_metadata(client_id, allowlist=resolve_client_id_allowlist())`
- Non-URL/opaque → direct store (static pre-registration path preserved)

Additional tests (Task 2 set, 5 more tests):
- **MANDATORY DNS-rebinding test**: `mcp-client.example.com` (in allowlist) whose
  `getaddrinfo` returns `10.1.2.3` → `RegistrationError400`, no fetch
- IMDS variant: allowlisted host resolving to `169.254.169.254` → rejected
- Loopback variant: allowlisted host resolving to `127.0.0.1` → rejected
- Happy path: allowlisted host resolving to `93.184.216.34` (public) → fetch + metadata
- `register_client` provider tests: URL-shaped delegates to `fetch_client_metadata`,
  non-URL skips fetch, SSRF rejection propagates from `register_client`

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | CIMD allowlist + IP block + 5s timeout | `ff5b8da` | registration.py, test_oauth_cimd_ssrf.py |
| 2 | DNS-rebinding mitigation + provider wiring | `e49811e` | registration.py, provider.py, test_oauth_cimd_ssrf.py |

## SSRF Control Stack (all 5 controls implemented)

| Control | Where | Test |
|---------|-------|------|
| #1 Parse client_id URL, extract hostname | `validate_client_id_host` | empty/no-scheme/no-host tests |
| #2 Allowlist gate (AGENT_BRAIN_OAUTH_CLIENT_ID_ALLOWLIST) | `validate_client_id_host` | `test_non_allowlisted_hostname_raises_400` |
| #3 Unconditional block for IP literals in private ranges | `validate_client_id_host` | `test_ip_literal_private_unconditionally_blocked_even_if_allowlisted` |
| #4 ~5s HTTP timeout | `fetch_client_metadata` (httpx.Timeout) | `test_fetch_uses_5s_timeout` |
| #5 DNS-rebinding: post-resolution IP re-validation | `fetch_client_metadata` (getaddrinfo loop) | `test_allowlisted_hostname_rfc1918_dns_rejected` (MANDATORY) |

## DNS-Rebinding Mitigation Approach

**Approach chosen: resolve-then-validate** (not custom httpx transport)

1. Call `socket.getaddrinfo(hostname, None)` synchronously before the HTTP fetch
2. For each `addr_info` in the result, extract `str(sockaddr[0])` (the resolved IP)
3. Run `is_blocked_ip()` on it — raise `RegistrationError400` on any blocked address
4. Proceed to `httpx.AsyncClient.get()` only after all resolved IPs pass

**Why not a custom httpx transport:** The transport approach intercepts at TCP-connect
time but is significantly harder to unit-test (requires mocking low-level socket
primitives). The resolve-then-validate approach monkeypatches `socket.getaddrinfo`
cleanly for test isolation.

**TOCTOU window:** The DNS cache may be invalidated between `getaddrinfo` and the
TCP connection. For Phase 67 Shape A (single-user co-located, non-adversarial internal
network), this window is acceptable and consistent with the design doc's guidance.
Phase 70 may tighten this further with a custom transport if needed.

## provider.register_client Dispatch Logic

```
register_client(client_info):
  if client_info.client_id is None → ValueError
  parsed = urlparse(client_id)
  if parsed.scheme and parsed.netloc:
    # URL-shaped → CIMD path
    allowlist = resolve_client_id_allowlist()
    await fetch_client_metadata(client_id, allowlist=allowlist)  # may raise RegistrationError400
  # else: opaque/static → no fetch
  self._clients[client_id] = client_info
```

Static pre-registration (client_id = "claude-desktop") still works:
`urlparse("claude-desktop")` → scheme="" netloc="" → not URL-shaped → direct store.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] httpx.AsyncClient mock using MagicMock caused TypeError**
- **Found during:** Task 1 (first test run, GREEN phase)
- **Issue:** `mock_client.return_value.__aenter__ = AsyncMock(return_value=real_client)` but then `real_client.get()` returned a `MagicMock` which can't be awaited
- **Fix:** Replaced with inline fake class (`_CapturingClient`, `_FakeClient`) that are proper async context managers with `async def get()` returning `httpx.Response(200, json=..., request=httpx.Request(...))`
- **Files modified:** `tests/test_oauth_cimd_ssrf.py`
- **Commit:** `ff5b8da`

**2. [Rule 1 - Bug] side_effect=lambda patch on httpx.AsyncClient caused infinite recursion**
- **Found during:** Task 1 (happy-path test fix attempt)
- **Issue:** `patch(..., side_effect=lambda **kwargs: httpx.AsyncClient(...))` — the lambda called the patched class, causing infinite recursion
- **Fix:** Switched to `patch(..., _FakeClient)` (replacement class, not side_effect)
- **Files modified:** `tests/test_oauth_cimd_ssrf.py`
- **Commit:** `ff5b8da`

**3. [Rule 1 - Bug] httpx.Response.raise_for_status requires request to be set**
- **Found during:** Task 1 (second test run)
- **Issue:** `httpx.Response(200, json=...)` without a `request` argument causes `raise_for_status()` to raise `RuntimeError("Cannot call raise_for_status as the request instance has not been set")`
- **Fix:** All fake transport `get()` methods now create `req = httpx.Request("GET", url)` and pass `request=req` to `httpx.Response`
- **Files modified:** `tests/test_oauth_cimd_ssrf.py`
- **Commit:** `ff5b8da`

**4. [Rule 1 - Type] socket.getaddrinfo addr_info tuple typing**
- **Found during:** Task 2 (mypy strict check)
- **Issue:** `addr_info[4][0]` typed as `str | int` by mypy (sockaddr union) — incompatible with `is_blocked_ip(ip: str | IPv4Address | IPv6Address)`
- **Fix:** `sockaddr = addr_info[4]; resolved_ip = str(sockaddr[0])` — explicit str cast
- **Files modified:** `agent_brain_mcp/oauth/registration.py`
- **Commit:** `e49811e`

**5. [Rule 1 - Lint] Ruff E501/N818/F401/I001/UP037 on new files**
- **Found during:** Task 2 (ruff check after implementation)
- **Issues:** `ipaddress` unused import (F401 auto-fixed), `RegistrationError400` N818
  (added `# noqa: N818` with explanation), E501 long lines in docstrings/error messages
  (shortened), I001 import sort (auto-fixed), UP037 quoted annotations (auto-fixed),
  F401 unused `AsyncMock`/`MagicMock` imports in test (auto-fixed)
- **Files modified:** both new files
- **Commit:** `e49811e`

## Self-Check

### Created files exist:
- `agent-brain-mcp/agent_brain_mcp/oauth/registration.py` — FOUND
  (contains `def fetch_client_metadata`, `def is_blocked_ip`, `def validate_client_id_host`)
- `agent-brain-mcp/tests/test_oauth_cimd_ssrf.py` — FOUND (33 tests)

### Key invariants verified:
- `is_blocked_ip("169.254.169.254")` is True — CONFIRMED (parametrized test)
- `is_blocked_ip("93.184.216.34")` is False — CONFIRMED (parametrized test)
- Non-allowlisted hostname raises before network call — CONFIRMED (`test_non_allowlisted_host_raises_before_network`)
- Allowlisted hostname + RFC-1918 DNS → rejected (mandatory DNS-rebinding test) — CONFIRMED
- `provider.register_client` with URL client_id calls `fetch_client_metadata` — CONFIRMED
- Static pre-registration still works without fetch — CONFIRMED

### Commits exist:
- `ff5b8da` (Task 1) — FOUND
- `e49811e` (Task 2) — FOUND

### QA gate:
- `task before-push` exits 0 (778 passed, 0 failures, 0 lint errors, 0 mypy errors)

## Self-Check: PASSED

---
*Phase: 67-co-located-as-rs-middleware*
*Completed: 2026-06-15*
