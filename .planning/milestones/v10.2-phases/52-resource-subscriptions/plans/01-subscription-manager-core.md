# Plan 01: Subscription manager core (greenfield package)

**Phase:** 52 — Resource subscriptions
**Requirements covered:** SUB-04 (payload shape foundations), SUB-05 (per-session registry); foundation for SUB-01, SUB-02, SUB-03
**Depends on:** none — first plan
**Parallel-safe with:** none (all subsequent plans import from this module)
**Status:** Not started

## Goal

Land the greenfield `agent_brain_mcp.subscriptions` subpackage that owns per-session subscription bookkeeping and the polling primitive. This plan ships **no MCP wire integration** — no decorators registered on `server.py`, no capability flip, no per-URI polling policy implementations. Just the data structures, the `start_polling(...)` primitive, the canonical payload hashing helper, and unit tests proving each in isolation. Plans 02–04 build on this foundation.

The public surface this plan establishes is the contract Phase 54's `wait_for_job` tool will also consume.

## Acceptance Criteria

- [ ] `agent-brain-mcp/agent_brain_mcp/subscriptions/__init__.py` exists and re-exports `SubscriptionManager`, `canonical_hash`, `SubscribableUriRejected`
- [ ] `agent-brain-mcp/agent_brain_mcp/subscriptions/manager.py` defines `SubscriptionManager` with the following public methods, each unit-tested:
  - `start_polling(session, uri: str, interval_s: float, fetcher: Callable[[], Awaitable[dict]], on_change: Callable[[str, dict], Awaitable[None]], drop_keys: set[str] | None = None) -> None`
  - `unsubscribe(session, uri: str) -> bool` (returns True if a task was cancelled)
  - `cleanup_session(session) -> int` (returns count of tasks cancelled)
  - `cleanup_all() -> int` (cancels every registered task across every session — used by `run_stdio` finally)
  - `is_subscribed(session, uri: str) -> bool`
  - `active_count() -> int` (for debug/log lines)
- [ ] Registry uses `dict[tuple[int, str], asyncio.Task]` keyed by `(id(session), uri)`; **session held by weakref where possible to avoid holding a closed session alive**
- [ ] `start_polling` registers the entry in the dict **synchronously** before calling `asyncio.create_task(...)` — guarantees `unsubscribe()` is safe even immediately after subscribe
- [ ] Each polling task body wraps in `try/finally`: on `CancelledError` or any exit it removes its own `(session_id, uri)` entry from the registry — defense-in-depth against partial cleanup
- [ ] Each poll iteration:
  1. Calls `fetcher()` (await)
  2. Computes `canonical_hash(payload, drop=drop_keys or DEFAULT_DROP_KEYS)`
  3. If hash differs from last seen for this `(session_id, uri)`, calls `on_change(uri, payload)` and updates last-seen
  4. `await asyncio.sleep(interval_s)`
- [ ] `agent-brain-mcp/agent_brain_mcp/subscriptions/payloads.py` defines `canonical_hash(payload: dict, drop: set[str]) -> str`:
  - Recursively drops keys in `drop` at every nesting depth
  - Serializes with `json.dumps(..., sort_keys=True, separators=(",", ":"))`
  - Returns SHA-256 hex digest (64 chars)
- [ ] `DEFAULT_DROP_KEYS = frozenset({"timestamp", "updated_at", "elapsed_ms", "polled_at", "now"})`
- [ ] `agent-brain-mcp/agent_brain_mcp/subscriptions/errors.py` defines `SubscribableUriRejected(McpError)` for unknown / not-subscribable URI — Plan 02 raises this from the wire handler
- [ ] Unit tests cover: subscribe→cancel→re-subscribe round trip; diff-suppression (same payload → no on_change call); diff trigger (different non-volatile field → on_change fires); volatile-only diff (only `timestamp` changed → no on_change); `cleanup_session` cancels all of one session's tasks but leaves another session's intact; `cleanup_all` cancels everything; race: synchronous `subscribe()` immediately followed by `unsubscribe()` cancels the task before its first poll
- [ ] Module-level docstrings cite the contract that Phase 54 TOOL-04 will reuse `start_polling` (cross-phase link)
- [ ] `task mcp:pr-qa-gate` exits 0 (Black, Ruff, mypy strict, pytest)
- [ ] No changes outside `agent-brain-mcp/agent_brain_mcp/subscriptions/` and `agent-brain-mcp/tests/subscriptions/`

## Files to Touch

| File | Action | Notes |
|------|--------|-------|
| `agent-brain-mcp/agent_brain_mcp/subscriptions/__init__.py` | create | re-export public API |
| `agent-brain-mcp/agent_brain_mcp/subscriptions/manager.py` | create | `SubscriptionManager` class (~120 LOC) |
| `agent-brain-mcp/agent_brain_mcp/subscriptions/payloads.py` | create | `canonical_hash()` + `DEFAULT_DROP_KEYS` (~40 LOC) |
| `agent-brain-mcp/agent_brain_mcp/subscriptions/errors.py` | create | `SubscribableUriRejected` (~15 LOC) |
| `agent-brain-mcp/tests/subscriptions/__init__.py` | create | empty |
| `agent-brain-mcp/tests/subscriptions/test_manager.py` | create | unit tests for manager (~150 LOC) |
| `agent-brain-mcp/tests/subscriptions/test_payloads.py` | create | unit tests for `canonical_hash` (~60 LOC) |

## Implementation Steps

1. Read `agent-brain-mcp/.venv/lib/python3.12/site-packages/mcp/server/session.py:226` to confirm `ServerSession.send_resource_updated(uri)` signature and confirm it is async.
2. Read `mcp/server/lowlevel/server.py:240` to confirm how `request_context.session` is exposed. Polling tasks do **not** call `request_context` — they hold the session ref captured by the handler at subscribe time.
3. Create `agent_brain_mcp/subscriptions/payloads.py`:
   - `_strip(obj, drop)` recursive helper handling dict / list / scalar
   - `canonical_hash(payload, drop)` returns `hashlib.sha256(json.dumps(_strip(payload, drop), sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()`
   - Export `DEFAULT_DROP_KEYS`.
4. Create `agent_brain_mcp/subscriptions/errors.py`: `class SubscribableUriRejected(McpError)` with `INVALID_PARAMS` code and `data.reason` field for `"unknown_uri"` vs `"not_subscribable"`. Reuse `mcp.shared.exceptions.McpError` and `mcp.types.ErrorData`.
5. Create `agent_brain_mcp/subscriptions/manager.py`:
   - `class SubscriptionManager:`
     - `__init__(self) -> None:` initializes `self._tasks: dict[tuple[int, str], asyncio.Task[None]] = {}` and `self._last_hash: dict[tuple[int, str], str] = {}`
     - `def _key(self, session: Any, uri: str) -> tuple[int, str]: return (id(session), uri)`
     - `def start_polling(self, session, uri, interval_s, fetcher, on_change, drop_keys=None) -> None:`
       - key = `self._key(session, uri)`
       - if key already in `self._tasks`: raise `RuntimeError("already subscribed")` (Plan 02 handler converts to MCP InvalidParams before calling)
       - Synchronously register a placeholder: `self._tasks[key] = asyncio.create_task(self._poll_loop(session, uri, interval_s, fetcher, on_change, drop_keys or DEFAULT_DROP_KEYS, key))`
     - `async def _poll_loop(self, session, uri, interval_s, fetcher, on_change, drop, key) -> None:`
       - Body wrapped in `try / finally`
       - In `finally`: `self._tasks.pop(key, None); self._last_hash.pop(key, None)`
       - Body: loop forever until cancelled — `payload = await fetcher(); h = canonical_hash(payload, drop); if h != self._last_hash.get(key): self._last_hash[key] = h; await on_change(uri, payload); await asyncio.sleep(interval_s)`
     - `def unsubscribe(self, session, uri) -> bool:` cancel the task, return True if found
     - `def cleanup_session(self, session) -> int:` cancel every task whose key starts with `id(session)`; return count
     - `def cleanup_all(self) -> int:` cancel every task; return count
     - `def is_subscribed(self, session, uri) -> bool:` membership test
     - `def active_count(self) -> int:` `len(self._tasks)`
6. Wire `__init__.py` to re-export `SubscriptionManager`, `canonical_hash`, `DEFAULT_DROP_KEYS`, `SubscribableUriRejected`.
7. Write unit tests under `tests/subscriptions/`:
   - `test_payloads.py`: `canonical_hash` strips at every depth; same payload modulo drop keys → same hash; different scalar at depth 3 → different hash; non-serializable values raise.
   - `test_manager.py`: use real `asyncio` loop via `pytest-asyncio` (already a dep — confirm in `pyproject.toml`). Use a fake `session = object()` and assertable async fetchers/on_change collectors. Cover: subscribe→on_change called→cancel; subscribe with constant fetcher→on_change called exactly once (first poll, since last_hash is unset); subscribe with constant fetcher whose hash matches a seeded last_hash→on_change never called; multi-session isolation; `cleanup_session` race against in-flight poll iteration; subscribe + immediate unsubscribe — task is cancelled before first fetcher call (use `asyncio.Event` to gate the fetcher).
8. Run `task mcp:pr-qa-gate` and fix until 0 exit. Run `task before-push` from repo root for full system check.

## Verification

```bash
# From repo root
cd agent-brain-mcp
poetry run pytest tests/subscriptions/ -v
poetry run mypy agent_brain_mcp/subscriptions/
poetry run ruff check agent_brain_mcp/subscriptions/ tests/subscriptions/
poetry run black --check agent_brain_mcp/subscriptions/ tests/subscriptions/

# From repo root
task before-push    # MUST exit 0
```

Manual sanity check (no MCP server needed — this is a library-level plan):

```bash
cd agent-brain-mcp
poetry run python -c "
import asyncio
from agent_brain_mcp.subscriptions import SubscriptionManager, canonical_hash, DEFAULT_DROP_KEYS

async def main():
    mgr = SubscriptionManager()
    session = object()
    events = []

    async def fetcher():
        return {'value': 42, 'timestamp': '2026-06-02'}
    async def on_change(uri, payload):
        events.append((uri, payload['value']))

    mgr.start_polling(session, 'test://x', 0.1, fetcher, on_change)
    await asyncio.sleep(0.35)  # ~3 polls
    cancelled = mgr.unsubscribe(session, 'test://x')
    print(f'events={events}, cancelled={cancelled}, active={mgr.active_count()}')

asyncio.run(main())
# Expect: events=[('test://x', 42)], cancelled=True, active=0
"
```

Expected behavior: exactly **one** on_change event despite ~3 poll iterations (diff suppression on identical payload after dropping `timestamp`); subscription cleanly cancelled.

## Risk Notes

- **`asyncio.create_task` lifecycle**: Python warns if a task is GC'd before completion. We hold every task in `self._tasks` for its full lifetime, so this is safe — verify with `pytest -W error::ResourceWarning`.
- **mypy strict and `Callable` types**: Use `Awaitable[None]` / `Awaitable[dict[str, Any]]` for callback types. May need `from typing import Awaitable, Callable, Any`. mypy may complain about `dict[str, Any]` vs `Mapping`; pick `dict[str, Any]` for variance simplicity and document.
- **Session weakref**: `id(session)` as the key part lets us avoid a hard reference to the session object in `self._tasks` keys, but the closure captured by `_poll_loop` holds a strong ref to the session. That's intentional — the polling task needs the session alive to call `on_change` (which Plan 02 wires to `session.send_resource_updated`). When `cleanup_session` is called, the task is cancelled and the closure released.
- **`McpError` import path**: Confirm `from mcp.shared.exceptions import McpError` works in the installed SDK version. If it moved, adjust `errors.py` import path.

---
*Plan 01 of Phase 52*
