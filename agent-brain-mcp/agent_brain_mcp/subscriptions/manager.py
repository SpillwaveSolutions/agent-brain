"""Per-session subscription bookkeeping and polling primitive.

This module ships the ``SubscriptionManager`` class. It owns:

1. A registry of active per-session subscriptions keyed by
   ``(id(session), uri)``.
2. The polling-task lifecycle: spawn, diff-suppress, cancel, cleanup.

Phase 52 CONTEXT decision A (per-session, not per-URI): subscriptions
are session-scoped. Two MCP clients subscribing to ``corpus://status``
each get their own polling task; disconnect of one does not affect the
other.

Phase 52 CONTEXT decision F: polling tasks run on the same asyncio
loop as the MCP server; sync HTTP calls inside ``fetcher`` are the
caller's responsibility to wrap with ``asyncio.to_thread`` (Plan 02
follows that pattern explicitly).

Public surface — Plans 02/03/04 import these symbols verbatim:

* :class:`SubscriptionManager`
* :func:`SubscriptionManager.start_polling`
* :func:`SubscriptionManager.unsubscribe`
* :func:`SubscriptionManager.cleanup_session`
* :func:`SubscriptionManager.cleanup_all`
* :func:`SubscriptionManager.is_subscribed`
* :func:`SubscriptionManager.active_count`

Phase 54 TOOL-04 (``wait_for_job``) reuse contract: the
``start_polling()`` signature defined here is consumed by the Phase 54
progress-notification implementation. Changing the signature is a
cross-phase breaking change — touch this surface only with
deliberate cross-phase planning.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from .errors import SubscriptionTerminated
from .payloads import DEFAULT_DROP_KEYS, canonical_hash

logger = logging.getLogger(__name__)


# Callback type aliases — declared at module level so Phase 54 can import
# them when wiring ``wait_for_job``.
Fetcher = Callable[[], Awaitable[dict[str, Any]]]
"""Async callable that returns the freshly-polled resource payload.

Plan 02 will close over the MCP ``ApiClient`` and the URI to back
``job://<id>``, ``corpus://status``, and ``corpus://folders``.
"""

OnChange = Callable[[str, dict[str, Any]], Awaitable[None]]
"""Async callable invoked when the canonical-hash of the payload changes.

Signature: ``(uri, payload) -> None``. Plan 02 wires this to
``ServerSession.send_resource_updated(uri)``.
"""


class SubscriptionManager:
    """Owns the registry of active subscriptions and their polling tasks.

    Thread safety: this class is intended to run entirely on a single
    asyncio event loop. All mutations to ``_tasks`` / ``_last_hash``
    happen from that loop — no locks are needed. The MCP SDK's
    ``run_stdio`` runs one server per process; Phase 53's Streamable
    HTTP transport allocates one event loop per worker, still
    single-threaded per ``SubscriptionManager`` instance.

    Lifecycle: one instance per running MCP server, constructed in
    ``build_server()`` (Plan 02). ``cleanup_all()`` is called from
    ``run_stdio``'s ``finally`` block (Plan 04) to guarantee no
    orphan polling tasks survive a process exit.
    """

    def __init__(self) -> None:
        """Construct an empty manager. No tasks are spawned here."""
        # Registry of active polling tasks keyed by ``(id(session), uri)``.
        # ``id(session)`` is the integer cpython object identity — it
        # remains valid only as long as the session object is alive.
        # The closure captured by ``_poll_loop`` holds a strong ref to
        # the session, so the id stays meaningful for the task's
        # entire lifetime. CONTEXT risk note: the closure is
        # released when the task is cancelled.
        self._tasks: dict[tuple[int, str], asyncio.Task[None]] = {}
        # Last hash of the payload that was actually emitted as
        # ``on_change``. A miss in this dict on the first poll means
        # "no prior payload" and ``on_change`` fires unconditionally
        # for the first polled value (so subscribers see the initial
        # state — they don't have to wait for a *change* to arrive).
        self._last_hash: dict[tuple[int, str], str] = {}

    @staticmethod
    def _key(session: Any, uri: str) -> tuple[int, str]:
        """Compute the registry key for a given session + URI."""
        return (id(session), uri)

    def start_polling(
        self,
        session: Any,
        uri: str,
        interval_s: float,
        fetcher: Fetcher,
        on_change: OnChange,
        drop_keys: set[str] | frozenset[str] | None = None,
    ) -> None:
        """Spawn a polling task for ``(session, uri)``.

        The registry entry is written **synchronously** before
        ``asyncio.create_task(...)`` is called. This ordering matters:
        it lets a caller invoke ``unsubscribe()`` on the very next
        line and still cancel the task before its first ``fetcher()``
        runs (proved by ``test_subscribe_then_immediate_unsubscribe``
        in ``tests/subscriptions/test_manager.py``).

        Args:
            session: The owning MCP session object. Held by closure
                inside the polling task; identity (``id(session)``)
                is the registry key.
            uri: Resource URI being polled (e.g.,
                ``"corpus://status"``).
            interval_s: Seconds between successive ``fetcher()`` calls.
            fetcher: Async callable that returns the polled payload.
            on_change: Async callable invoked with ``(uri, payload)``
                only when the canonical hash differs from the prior
                call (or on the very first poll).
            drop_keys: Volatile keys to strip before hashing. Defaults
                to :data:`payloads.DEFAULT_DROP_KEYS` when ``None``.

        Raises:
            RuntimeError: If a subscription is already active for the
                same ``(session, uri)``. Plan 02's wire handler is
                expected to convert this into an MCP InvalidParams
                error before calling — the manager raises a plain
                Python exception so it can be unit-tested without
                going through the MCP error layer.
        """
        key = self._key(session, uri)
        if key in self._tasks:
            raise RuntimeError(f"Already subscribed: session={id(session)} uri={uri!r}")

        effective_drop = drop_keys if drop_keys is not None else DEFAULT_DROP_KEYS

        # Synchronously create the task and register it BEFORE returning
        # to the caller. ``asyncio.create_task`` schedules the coroutine
        # but does not yield control to it — the coro's body does not
        # run until the next await point in the calling code. That
        # guarantees ``unsubscribe()`` immediately after this method
        # returns can find the task in ``self._tasks`` and cancel it.
        #
        # NB on cancellation timing (CONTEXT decision D, layer-2 belt
        # and-suspenders): when ``unsubscribe()`` is called before the
        # asyncio scheduler has even given the new task a chance to
        # start, asyncio skips the coroutine body entirely on
        # cancellation — the ``try/finally`` does NOT run in that
        # case. So ``unsubscribe`` / ``cleanup_*`` pop the registry
        # entry SYNCHRONOUSLY as the primary path, and the
        # ``_poll_loop.finally`` is the defense-in-depth path for the
        # case where the loop crashes mid-iteration after it actually
        # started running.
        task = asyncio.create_task(
            self._poll_loop(
                session=session,
                uri=uri,
                interval_s=interval_s,
                fetcher=fetcher,
                on_change=on_change,
                drop=effective_drop,
                key=key,
            ),
            name=f"agent-brain-mcp-poll:{uri}:{id(session)}",
        )
        self._tasks[key] = task
        logger.info(
            "subscribe session=%s uri=%s interval=%.1fs (active=%d)",
            self._truncate_session_id(session),
            uri,
            interval_s,
            len(self._tasks),
        )

    async def _poll_loop(
        self,
        *,
        session: Any,
        uri: str,
        interval_s: float,
        fetcher: Fetcher,
        on_change: OnChange,
        drop: set[str] | frozenset[str],
        key: tuple[int, str],
    ) -> None:
        """Internal polling loop body for one subscription.

        Body wrapped in ``try / finally``. The ``finally`` removes the
        registry entries for this ``key`` — defense-in-depth so that
        even if the task exits via an unhandled exception (not just
        ``CancelledError`` from a normal ``unsubscribe()``), the
        registry stays clean. Phase 52 CONTEXT decision D, layer 2
        ("Per-task guard").

        ``session`` is captured by closure so the task holds a strong
        ref to it for the task's lifetime. When the manager cancels
        the task, the closure is released and the session ref drops.
        """
        # Reference session inside the closure so static analyzers see
        # the strong-ref contract documented in CONTEXT decision A.
        # The fetcher/on_change callables already close over whatever
        # session-derived state they need (e.g., the
        # ``ServerSession.send_resource_updated`` method); this local
        # binding is what keeps the session alive as long as the task
        # is alive.
        _session_ref = session  # noqa: F841 — intentional strong ref
        try:
            while True:
                try:
                    payload = await fetcher()
                except asyncio.CancelledError:
                    # Plan 04 defense-in-depth: an explicit catch with a
                    # DEBUG log makes Plan 04's leaked-task assertion
                    # test diagnosable in CI without ratcheting the
                    # logger to DEBUG for every test. We MUST re-raise
                    # so cancellation semantics propagate (the finally
                    # block scrubs the registry slot; the manager's
                    # primary synchronous cleanup paths already popped
                    # the slot before sending the cancel).
                    logger.debug(
                        "poll_loop cancelled session=%s uri=%s",
                        self._truncate_session_id(session),
                        uri,
                    )
                    raise
                except SubscriptionTerminated as terminated:
                    # Plan 03 sentinel: the policy fetcher signalled
                    # that the polled resource has reached a terminal
                    # state (e.g., job://<id> with status=completed).
                    # Emit one final on_change with the terminal
                    # payload (if provided) so the subscriber sees
                    # the end-state, then return cleanly. The finally
                    # block below + Plan 01's synchronous-cleanup
                    # paths both scrub the registry slot.
                    final = terminated.final_payload
                    if final is not None:
                        try:
                            await on_change(uri, final)
                        except asyncio.CancelledError:
                            raise
                        except Exception:
                            # A failing on_change on the terminal poke
                            # must not stop us exiting — the loop is
                            # ending either way. Log and proceed.
                            logger.exception(
                                "on_change failed during terminal "
                                "emission for uri=%s",
                                uri,
                            )
                    logger.info(
                        "subscription terminated by policy " "session=%s uri=%s",
                        self._truncate_session_id(session),
                        uri,
                    )
                    return
                except Exception:
                    # Don't let a transient fetcher failure tear down
                    # the polling loop. Log and back off one interval.
                    # Plan 03's policies are expected to convert HTTP
                    # 5xx into a structured error and let it propagate
                    # here; we still want the loop to live to retry.
                    logger.exception(
                        "fetcher failed for uri=%s; backing off %.1fs",
                        uri,
                        interval_s,
                    )
                    await asyncio.sleep(interval_s)
                    continue

                try:
                    h = canonical_hash(payload, drop)
                except (TypeError, ValueError):
                    # Non-serializable payload — log and treat as
                    # "changed" so the subscriber still gets poked.
                    # Better to over-emit than swallow a real change.
                    logger.warning(
                        "non-hashable payload for uri=%s; emitting anyway",
                        uri,
                    )
                    h = ""  # empty string forces a diff vs any prior digest

                prior = self._last_hash.get(key)
                if h != prior:
                    self._last_hash[key] = h
                    await on_change(uri, payload)

                await asyncio.sleep(interval_s)
        finally:
            # Defense-in-depth (CONTEXT decision D, layer 2): regardless
            # of HOW we exit (cancellation, unhandled exception, normal
            # return — though a polling loop never normally returns),
            # purge our entries from the registry so the manager state
            # stays consistent. Pop ONLY if the slot still holds OUR
            # task — if a caller already unsubscribed then re-
            # subscribed to the same (session, uri), the slot now
            # holds the NEW task and we must not evict it.
            current = self._tasks.get(key)
            if current is None or current is asyncio.current_task():
                self._tasks.pop(key, None)
                self._last_hash.pop(key, None)
            logger.info(
                "poll_loop exit session=%s uri=%s (active=%d)",
                self._truncate_session_id(session),
                uri,
                len(self._tasks),
            )

    def unsubscribe(self, session: Any, uri: str) -> bool:
        """Cancel the polling task for ``(session, uri)``.

        Args:
            session: The owning MCP session (identity-matched).
            uri: Resource URI to unsubscribe from.

        Returns:
            ``True`` if a task was found and cancelled; ``False`` if
            no subscription existed for that pair. The manager
            tolerates extra ``unsubscribe`` calls gracefully — the
            MCP spec lets clients send ``resources/unsubscribe`` for
            URIs they never subscribed to.
        """
        key = self._key(session, uri)
        task = self._tasks.pop(key, None)
        if task is None:
            return False
        # Also drop the last-hash so a future re-subscribe starts
        # clean (first poll emits as if no prior payload existed).
        self._last_hash.pop(key, None)
        task.cancel()
        logger.info(
            "unsubscribe session=%s uri=%s (active=%d)",
            self._truncate_session_id(session),
            uri,
            len(self._tasks),
        )
        return True

    def cleanup_session(self, session: Any) -> int:
        """Cancel every polling task owned by ``session``.

        Called by the disconnect-cleanup hook in Plan 04 when an MCP
        session closes (stdio EOF or HTTP transport disconnect).

        Args:
            session: The owning MCP session. Identity (``id(session)``)
                is matched against the first element of every
                registry key.

        Returns:
            Count of tasks cancelled.
        """
        sid = id(session)
        # Snapshot keys first — we are about to mutate ``self._tasks``.
        victims = [k for k in self._tasks if k[0] == sid]
        for key in victims:
            task = self._tasks.pop(key, None)
            self._last_hash.pop(key, None)
            if task is not None:
                task.cancel()
        if victims:
            logger.info(
                "cleanup_session session=%s count=%d",
                self._truncate_session_id(session),
                len(victims),
            )
        return len(victims)

    def cleanup_all(self) -> int:
        """Cancel every polling task across every session.

        Called from ``run_stdio``'s ``finally`` block in Plan 04 to
        guarantee no orphan polling tasks survive a process exit.

        Returns:
            Count of tasks cancelled.
        """
        count = len(self._tasks)
        # Snapshot then drain. Pop the registry SYNCHRONOUSLY so
        # ``active_count()`` immediately reflects zero — a task
        # cancelled before its coro started never runs its finally
        # block, so we cannot rely on the loop's own cleanup here.
        tasks = list(self._tasks.values())
        self._tasks.clear()
        self._last_hash.clear()
        for task in tasks:
            task.cancel()
        if count:
            logger.info("cleanup_all count=%d", count)
        return count

    def is_subscribed(self, session: Any, uri: str) -> bool:
        """Return whether ``(session, uri)`` currently has an active task."""
        return self._key(session, uri) in self._tasks

    def active_count(self) -> int:
        """Return the total number of active polling tasks across all sessions.

        Used by debug log lines and the Phase 55 e2e test that asserts
        ``active_count() == 0`` after a clean disconnect.
        """
        return len(self._tasks)

    @staticmethod
    def _truncate_session_id(session: Any) -> str:
        """Return an 8-char hex-ish slug for log lines (CONTEXT Discretion)."""
        sid = id(session)
        return f"{sid:x}"[-8:]
