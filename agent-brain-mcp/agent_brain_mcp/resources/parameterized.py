"""Parameterized URI schemes — Phase 51 (URI-01 / URI-02 / URI-03).

Sister module to :mod:`agent_brain_mcp.resources.corpus`. Where ``corpus``
holds the 5 static ``corpus://*`` resources keyed by exact URI string,
this module holds the *parameterized* schemes whose URIs carry per-read
arguments and therefore can't live in a string-keyed registry:

- ``chunk://<chunk_id>`` (Plan 51-02 — URI-01)
- ``graph-entity://<type>/<id>`` (Plan 51-02 — URI-02)
- ``job://<job_id>`` (Plan 51-01 — URI-03)
- ``file://<abs-path>`` (Plan 51-03 — URI-04)

Plan 51-01 lands the dispatcher infrastructure plus the ``job://``
handler as the exemplar. Plan 51-02 (this plan) swaps in real handlers
for ``chunk://`` and ``graph-entity://``. Plan 51-03 swaps in
``file://``. The dispatcher and registry shape stay untouched across
all three plans.

Error-payload contract (Phase 51 CONTEXT decision C/D):

- **Malformed URI** (recognized scheme, missing required segment):
  ``McpError(INVALID_PARAMS)`` with
  ``data = {"uri": <input>, "reason": "missing_<segment>"}``
- **Backend 404/422/etc** for a well-formed URI: the existing
  :func:`agent_brain_mcp.errors.raise_for_status` already raises
  ``McpError(INVALID_PARAMS)`` (or ``SERVICE_INDEXING`` for 503) with
  ``data = {"httpStatus": <n>, "cause": ...}``; we wrap that to add
  the scheme-specific id (``data["scheme"]``, ``data["chunk_id"]``,
  ``data["entity_type"]``, ``data["entity_id"]``, ``data["job_id"]``)
  so MCP clients can distinguish scheme-level failures from transport
  failures. For ``graph-entity://`` we also attempt to extract a
  ``reason`` value (``graphrag_disabled`` or ``kuzu_unavailable``) from
  the Phase 50 503 detail body so operators can route on it.

The two shapes are intentionally different — one signals "you gave us
a URI we can't parse," the other signals "we parsed it but the backend
doesn't know that id." Reviewers should not collapse them.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from mcp import McpError
from mcp.types import ErrorData

from ..errors import INVALID_PARAMS

if TYPE_CHECKING:
    from ..client import ApiClient


# Schemes this module owns. Anything outside this set is left to the
# legacy :data:`RESOURCE_REGISTRY` fall-through (``corpus://*``) or to
# the final "Unknown resource" error.
PARAMETERIZED_SCHEMES: frozenset[str] = frozenset(
    {"chunk", "graph-entity", "job", "file"}
)


@dataclass(frozen=True)
class ParsedURI:
    """Parsed form of a parameterized resource URI.

    Only the fields relevant to the scheme are populated; the rest stay
    ``None``. Keeping one type (instead of four scheme-specific result
    types) keeps the dispatcher in :mod:`server` simple and lets future
    schemes extend the dataclass without rewiring callers.
    """

    scheme: str
    chunk_id: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    job_id: str | None = None
    path: str | None = None


def _invalid_uri(uri: str, reason: str) -> McpError:
    """Build the malformed-URI ``McpError`` (decision C)."""
    return McpError(
        ErrorData(
            code=INVALID_PARAMS,
            message=f"Invalid resource URI '{uri}': {reason}",
            data={"uri": uri, "reason": reason},
        )
    )


def parse_uri(uri: str) -> ParsedURI | None:
    """Parse a parameterized resource URI.

    Returns ``None`` for any scheme not in :data:`PARAMETERIZED_SCHEMES`
    (including ``corpus://``) so callers can fall through to the
    string-keyed :data:`RESOURCE_REGISTRY`. Returns a populated
    :class:`ParsedURI` for recognized, well-formed URIs.

    Raises :class:`McpError(INVALID_PARAMS)` with a structured ``data``
    blob when a recognized scheme is present but a required segment is
    missing. The ``data`` shape is ``{"uri": <input>, "reason": ...}``
    where ``reason`` is one of ``missing_chunk_id``, ``missing_type``,
    ``missing_id``, ``missing_job_id``, ``missing_path``.

    Notes on parsing non-hierarchical schemes:
        ``urlsplit('job://abc')`` puts ``abc`` in ``netloc``;
        ``urlsplit('job:abc')`` (RFC-correct no-slashes form) puts
        ``abc`` in ``path``. We accept both forms uniformly by reading
        ``netloc`` first and falling back to ``path.lstrip('/')``. A
        trailing slash (``job://abc/``) is treated as identical to no
        trailing slash. This matches user expectations from the v1
        ``corpus://config`` style.
    """
    parts = urlsplit(uri)
    scheme = parts.scheme

    if scheme not in PARAMETERIZED_SCHEMES:
        return None

    # Canonical "identifier or path" extraction. For schemes that take
    # a single opaque id, netloc is the id (or the first path segment
    # if the user wrote ``scheme:id`` without slashes). For schemes
    # with structure (``graph-entity://<type>/<id>``, ``file://<path>``)
    # we layer extra parsing on top.
    netloc = parts.netloc
    raw_path = parts.path

    if scheme == "job":
        job_id = netloc or raw_path.lstrip("/").rstrip("/")
        if not job_id:
            raise _invalid_uri(uri, "missing_job_id")
        return ParsedURI(scheme=scheme, job_id=job_id)

    if scheme == "chunk":
        chunk_id = netloc or raw_path.lstrip("/").rstrip("/")
        if not chunk_id:
            raise _invalid_uri(uri, "missing_chunk_id")
        return ParsedURI(scheme=scheme, chunk_id=chunk_id)

    if scheme == "graph-entity":
        # Expected form: graph-entity://<type>/<id>
        # urlsplit puts <type> in netloc and "/<id>" in path. Entity ids
        # may legally contain ``/`` (Phase 50 decision B — the server's
        # FastAPI route uses a path-style ``{entity_id}`` segment that
        # accepts embedded slashes). So we treat ``raw_path.lstrip("/")``
        # as the FULL id, including any inner ``/`` segments. Only the
        # trailing slash is stripped — that's the "empty id with
        # trailing slash" case (``graph-entity://Function/``).
        entity_type = netloc
        entity_id = raw_path.lstrip("/").rstrip("/")
        if not entity_type:
            raise _invalid_uri(uri, "missing_type")
        if not entity_id:
            raise _invalid_uri(uri, "missing_id")
        return ParsedURI(scheme=scheme, entity_type=entity_type, entity_id=entity_id)

    if scheme == "file":
        # ``file://<abs-path>`` — urlsplit puts the host portion in
        # netloc (usually empty for ``file:///foo/bar``) and the path
        # in ``path``. For an absolute UNIX path ``/foo/bar``, the
        # canonical URI form is ``file:///foo/bar`` (three slashes).
        # We do NOT enforce absoluteness here — that is the sandbox
        # helper's job in Plan 51-03. We only check that *some* path
        # is present.
        path = raw_path
        if not path:
            raise _invalid_uri(uri, "missing_path")
        return ParsedURI(scheme=scheme, path=path)

    # Defensive: PARAMETERIZED_SCHEMES is checked above, so this is
    # unreachable. Keep it for type-checker exhaustiveness.
    return None  # pragma: no cover


# --- Handler implementations ---------------------------------------------


async def _handle_job_uri(client: ApiClient, params: ParsedURI) -> str:
    """Read ``job://<job_id>`` → JSON body of ``GET /index/jobs/<id>``.

    Phase 51 CONTEXT decision F: the read shape mirrors the existing
    ``JobDetailResponse`` verbatim — no transformation. MCP clients
    reading ``job://abc`` get the same JSON as ``agent-brain jobs abc``.

    HTTP errors from the backend (404 for unknown id, 503 for indexing,
    etc.) flow through :func:`errors.raise_for_status` already wired
    inside :meth:`ApiClient.get_job`. We catch the resulting
    :class:`McpError` and re-raise with a refined ``data`` blob so MCP
    clients can tell *which* scheme failed and on *which* id.
    """
    assert params.job_id is not None  # parse_uri guarantees this
    try:
        response = await asyncio.to_thread(client.get_job, params.job_id)
    except McpError as exc:
        # Refine the data payload per decision D so clients can route
        # scheme-level failures. Preserve the original error code (404
        # → INVALID_PARAMS, 503 → SERVICE_INDEXING, etc.) and merge.
        original = exc.error
        refined_data: dict[str, object] = {
            "scheme": "job",
            "job_id": params.job_id,
        }
        if isinstance(original.data, dict):
            refined_data.update(original.data)
        raise McpError(
            ErrorData(
                code=original.code,
                message=original.message,
                data=refined_data,
            )
        ) from exc

    return json.dumps(response, indent=2, default=str)


async def _handle_chunk_uri(client: ApiClient, params: ParsedURI) -> str:
    """Read ``chunk://<chunk_id>`` → JSON body of ``GET /query/chunk/<id>``.

    Phase 50 Plan 02 ships the backing endpoint; its response is the
    locked :class:`ChunkRecord` shape (content + metadata, no
    embedding). Phase 51 (URI-01) pipes that shape through MCP unchanged.

    HTTP errors flow through :func:`errors.raise_for_status` inside
    :meth:`ApiClient.get_chunk`. 404 → ``INVALID_PARAMS`` per the
    standard table. We catch the resulting :class:`McpError` and
    re-raise with ``data["scheme"]`` and ``data["chunk_id"]`` populated
    (Phase 51 CONTEXT decision D) so MCP clients can route on the
    scheme as well as the underlying transport status.
    """
    assert params.chunk_id is not None  # parse_uri guarantees this
    try:
        response = await asyncio.to_thread(client.get_chunk, params.chunk_id)
    except McpError as exc:
        original = exc.error
        refined_data: dict[str, object] = {
            "scheme": "chunk",
            "chunk_id": params.chunk_id,
        }
        if isinstance(original.data, dict):
            refined_data.update(original.data)
        raise McpError(
            ErrorData(
                code=original.code,
                message=original.message,
                data=refined_data,
            )
        ) from exc

    return json.dumps(response, indent=2, default=str)


# Phase 50 503 ``detail.error`` values we promote to ``data["reason"]``
# on the way out so MCP clients (and ops dashboards) can tell whether
# graph addressing is *turned off* (operator-configurable) vs the Kuzu
# backend went bad mid-flight (#178; operator workaround is to switch
# ``graphrag.store_type=simple``). See ``agent-brain-server/api/routers/
# graph.py`` for the source of these strings.
_GRAPH_ENTITY_503_REASONS: frozenset[str] = frozenset(
    {"graphrag_disabled", "kuzu_unavailable"}
)


def _extract_graph_entity_reason(original_data: dict[str, object] | None) -> str | None:
    """Pull the Phase 50 503 ``error`` slug out of ``raise_for_status`` data.

    The server returns either a JSON-string detail (``{"detail": {"error":
    "graphrag_disabled", ...}}``) or a plain string. ``raise_for_status``
    in :mod:`agent_brain_mcp.errors` stores the string form (or
    ``str(dict)``) in ``data["cause"]``. We do a forgiving substring scan
    against the known reason set so a future formatting tweak on the
    server side doesn't silently drop the routing hint.
    """
    if not isinstance(original_data, dict):
        return None
    cause = original_data.get("cause")
    if not isinstance(cause, str):
        return None
    for reason in _GRAPH_ENTITY_503_REASONS:
        if reason in cause:
            return reason
    return None


async def _handle_graph_entity_uri(
    client: ApiClient, params: ParsedURI
) -> str:
    """Read ``graph-entity://<type>/<id>`` → ``GET /graph/entity/<t>/<i>`` body.

    Phase 50 Plan 03 ships the backing endpoint. Response is the locked
    :class:`GraphEntityRecord` shape (target entity + 1-hop incoming
    and outgoing neighbors). Phase 51 (URI-02) pipes it through MCP
    unchanged.

    HTTP errors flow through :func:`errors.raise_for_status` inside
    :meth:`ApiClient.get_graph_entity`:

    - 400 / 404 / 422 → ``INVALID_PARAMS`` — refined with ``data
      ["scheme"]``, ``["entity_type"]``, ``["entity_id"]``.
    - 503 → ``SERVICE_INDEXING`` — refined with the same fields PLUS a
      ``data["reason"]`` slug (``graphrag_disabled`` or
      ``kuzu_unavailable``) extracted from the Phase 50 503 detail
      body so MCP clients can distinguish "graphrag is turned off" from
      "Kuzu just crashed" without re-parsing the cause string.

    The 503 ``data["reason"]`` propagation is the #178 SIGSEGV-mitigation
    hand-off — Phase 50 Plan 03 documented the contract; this handler
    honors it verbatim.
    """
    assert params.entity_type is not None  # parse_uri guarantees this
    assert params.entity_id is not None
    try:
        response = await asyncio.to_thread(
            client.get_graph_entity, params.entity_type, params.entity_id
        )
    except McpError as exc:
        original = exc.error
        refined_data: dict[str, object] = {
            "scheme": "graph-entity",
            "entity_type": params.entity_type,
            "entity_id": params.entity_id,
        }
        original_data = original.data if isinstance(original.data, dict) else None
        if original_data is not None:
            refined_data.update(original_data)
        reason = _extract_graph_entity_reason(original_data)
        if reason is not None:
            refined_data["reason"] = reason
        raise McpError(
            ErrorData(
                code=original.code,
                message=original.message,
                data=refined_data,
            )
        ) from exc

    return json.dumps(response, indent=2, default=str)


async def _handle_not_implemented(client: ApiClient, params: ParsedURI) -> str:
    """Placeholder for schemes wired in later Plan 51 plans.

    Plan 51-03 (file) replaces this with a real handler by overwriting
    the matching entry in :data:`PARAMETERIZED_HANDLERS`. Plans 51-01
    and 51-02 have already swapped their placeholders out. Keeping a
    callable here (rather than leaving the dict key absent) lets the
    dispatcher in :mod:`server` stay scheme-agnostic and lets contract
    tests assert "all four schemes are registered" before Plan 03
    ships.
    """
    raise NotImplementedError(
        f"Handler for scheme '{params.scheme}' is not implemented yet "
        f"(landed in a later Phase 51 plan)."
    )


# Async handler signature: ``Callable[[ApiClient, ParsedURI], Awaitable[str]]``
ParameterizedHandler = Callable[["ApiClient", ParsedURI], Awaitable[str]]


PARAMETERIZED_HANDLERS: dict[str, ParameterizedHandler] = {
    "job": _handle_job_uri,
    "chunk": _handle_chunk_uri,
    "graph-entity": _handle_graph_entity_uri,
    # Reserved slot — Plan 51-03 swaps this placeholder in with the
    # real file:// handler. Do NOT remove this key; the dispatcher in
    # ``server.py`` keys off the registry, and contract tests assert
    # the four parameterized schemes are all registered.
    "file": _handle_not_implemented,
}


__all__ = [
    "PARAMETERIZED_HANDLERS",
    "PARAMETERIZED_SCHEMES",
    "ParameterizedHandler",
    "ParsedURI",
    "parse_uri",
]
