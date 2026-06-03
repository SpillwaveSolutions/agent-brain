"""Subscription-specific MCP error types.

Phase 52 CONTEXT decision G: subscribable URIs are an explicit
allowlist — ``job://<id>``, ``corpus://status``, ``corpus://folders``.
Any other URI (including ``chunk://`` and ``graph-entity://``, which are
content-addressed and therefore static-by-hash) is rejected at the
wire handler in Plan 02 by raising :class:`SubscribableUriRejected`.

Plan 02's ``@server.subscribe_resource()`` handler is the only place
that *raises* this error; Plan 01 only *defines* it so Plan 02 can
import the symbol without forward references.
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
