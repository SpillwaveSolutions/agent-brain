"""Subscription-specific MCP error types.

Phase 52 CONTEXT decision G: subscribable URIs are an explicit
allowlist — ``job://<id>``, ``corpus://status``, ``corpus://folders``.
Any other URI (including ``chunk://`` and ``graph-entity://``, which are
content-addressed and therefore static-by-hash) is rejected at the
wire handler in Plan 02 by raising :class:`SubscribableUriRejected`.

Plan 02's ``@server.subscribe_resource()`` handler is the only place
that *raises* :class:`SubscribableUriRejected`; Plan 01 only *defines*
it so Plan 02 can import the symbol without forward references.

Plan 03 adds :class:`SubscriptionTerminated` — a control-flow sentinel
(NOT a real error) that a per-URI policy fetcher raises when the polled
resource has reached a terminal state and the polling loop should exit
cleanly. The canonical use case is ``job://<id>`` reaching
``status in {completed, failed, cancelled}``: the fetcher raises
``SubscriptionTerminated(final_payload)``, Plan 01's ``_poll_loop``
catches the sentinel, emits one final ``on_change(uri, payload)`` with
the terminal payload, then returns. Plan 01's synchronous-cleanup
contract (registry pop done in the caller of ``cleanup_*`` /
``unsubscribe``) is unchanged — ``SubscriptionTerminated`` only adds a
clean-exit branch to the polling loop and relies on the loop's own
``finally`` block (defense-in-depth) to scrub the registry slot.
"""

from __future__ import annotations

from typing import Any

from mcp.shared.exceptions import McpError
from mcp.types import ErrorData

from ..errors import INVALID_PARAMS


class SubscribableUriRejected(McpError):  # noqa: N818  # name pinned by Plan 01
    """Raised when a subscribe request targets an unknown or non-subscribable URI.

    Carries a structured ``data`` payload so MCP clients can route on
    the reason without parsing the error message:

    * ``reason="unknown_uri"`` — the URI does not match any known
      resource scheme/registry entry.
    * ``reason="not_subscribable"`` — the URI is a valid resource but
      its scheme is not in the subscribable allowlist (e.g.
      ``chunk://``, ``graph-entity://``, ``file://``).

    The MCP wire code is ``-32602 InvalidParams`` — the JSON-RPC
    standard "Invalid params" code, reused via
    :data:`agent_brain_mcp.errors.INVALID_PARAMS` to stay consistent
    with the rest of the MCP package's error mapping (Plan §6.3).
    """

    def __init__(self, uri: str, *, reason: str) -> None:
        """Build a structured InvalidParams error for a rejected URI.

        Args:
            uri: The offending URI, surfaced verbatim in ``data.uri``
                so clients can correlate.
            reason: One of ``"unknown_uri"`` or ``"not_subscribable"``.
                Surfaced in ``data.reason``.
        """
        message = f"URI not subscribable: {uri} (reason={reason})"
        data: dict[str, Any] = {"uri": uri, "reason": reason}
        super().__init__(ErrorData(code=INVALID_PARAMS, message=message, data=data))


# noqa anchor: ruff N818 wants an "Error" suffix, but the symbol is a
# control-flow sentinel (not an error) consumed by SubscriptionManager
# only — naming it ...Error would mislead Plan 03 readers into thinking
# the fetcher hit a fault. Suppress the rule for this one class.
class SubscriptionTerminated(Exception):  # noqa: N818  # see note above
    """Sentinel raised by a policy fetcher to signal "polling is done."

    This is **NOT** an error — it is a clean-exit control-flow signal
    consumed exclusively by :meth:`SubscriptionManager._poll_loop`. The
    polling loop:

    1. Catches :class:`SubscriptionTerminated` in the per-iteration
       ``try/except`` around ``await fetcher()``.
    2. Pulls the final payload from ``exc.final_payload`` (or the
       single positional arg).
    3. Calls ``on_change(uri, final_payload)`` one last time so the
       subscriber receives the terminal state.
    4. Returns from the loop, releasing the closure references. The
       loop's ``finally`` block + Plan 01's synchronous-cleanup paths
       both scrub the registry entry — the ``(session, uri)`` slot
       becomes available again, ``manager.is_subscribed`` flips to
       ``False``, and ``manager.active_count`` decrements.

    Canonical use case: ``JobPolicy.fetcher`` polls
    ``GET /index/jobs/{id}``; when the payload reports
    ``status in {"completed", "failed", "cancelled"}`` the fetcher
    raises ``SubscriptionTerminated(payload)``. The subscriber gets a
    final ``notifications/resources/updated`` poke describing the
    terminal state, then no further polls fire.

    Why a custom exception and not ``StopAsyncIteration`` or a magic
    return value: the polling loop's signature already returns
    ``None`` and uses ``await fetcher()`` directly; a sentinel
    exception threads cleanly through that path without changing the
    public ``Fetcher`` type alias or every existing fetcher's
    return-type contract.

    Args:
        final_payload: The terminal-state payload to emit via
            ``on_change`` before the loop exits. ``None`` means
            "don't emit a final change" (the loop just returns).
    """

    def __init__(self, final_payload: dict[str, Any] | None = None) -> None:
        """Construct the sentinel with an optional final payload.

        Args:
            final_payload: The terminal-state payload. The polling
                loop emits this via ``on_change(uri, final_payload)``
                before returning. Pass ``None`` to exit silently
                without a final emission.
        """
        super().__init__("subscription terminated")
        self.final_payload = final_payload
