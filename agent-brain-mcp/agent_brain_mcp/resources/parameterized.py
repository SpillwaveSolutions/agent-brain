"""Parameterized URI schemes — Phase 51 (URI-03).

Sister module to :mod:`agent_brain_mcp.resources.corpus`. Where ``corpus``
holds the 5 static ``corpus://*`` resources keyed by exact URI string,
this module holds the *parameterized* schemes whose URIs carry per-read
arguments and therefore can't live in a string-keyed registry:

- ``chunk://<chunk_id>`` (Plan 51-02)
- ``graph-entity://<type>/<id>`` (Plan 51-02)
- ``job://<job_id>`` (Plan 51-01 — this plan)
- ``file://<abs-path>`` (Plan 51-03)

Plan 51-01 lands the dispatcher infrastructure plus the ``job://``
handler as the exemplar. The three other handler slots are reserved
with ``NotImplementedError``-raising placeholders so Plans 02 and 03
can swap them in without touching the dispatcher or the registry shape.

Error-payload contract (Phase 51 CONTEXT decision C/D):

- **Malformed URI** (recognized scheme, missing required segment):
  ``McpError(INVALID_PARAMS)`` with
  ``data = {"uri": <input>, "reason": "missing_<segment>"}``
- **Backend 404/422/etc** for a well-formed URI: the existing
  :func:`agent_brain_mcp.errors.raise_for_status` already raises
  ``McpError(INVALID_PARAMS)`` with
  ``data = {"httpStatus": 404, "cause": ...}``; we wrap that to add
  the scheme-specific id (``data["scheme"]``, ``data["job_id"]``)
  so MCP clients can distinguish scheme-level failures from transport
  failures.

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
        # urlsplit puts <type> in netloc and "/<id>" in path.
        entity_type = netloc
        entity_id = raw_path.lstrip("/").rstrip("/")
        if not entity_type:
            raise _invalid_uri(uri, "missing_type")
        if not entity_id:
            raise _invalid_uri(uri, "missing_id")
        return ParsedURI(
            scheme=scheme, entity_type=entity_type, entity_id=entity_id
        )

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


async def _handle_not_implemented(client: ApiClient, params: ParsedURI) -> str:
    """Placeholder for schemes wired in later Plan 51 plans.

    Plans 51-02 (chunk, graph-entity) and 51-03 (file) replace this
    with real handlers by overwriting the matching entry in
    :data:`PARAMETERIZED_HANDLERS`. Keeping a callable here (rather
    than leaving the dict key absent) lets the dispatcher in
    :mod:`server` stay scheme-agnostic and lets contract tests assert
    "all four schemes are registered" before Plans 02/03 ship.
    """
    raise NotImplementedError(
        f"Handler for scheme '{params.scheme}' is not implemented yet "
        f"(landed in a later Phase 51 plan)."
    )


# Async handler signature: ``Callable[[ApiClient, ParsedURI], Awaitable[str]]``
ParameterizedHandler = Callable[["ApiClient", ParsedURI], Awaitable[str]]


PARAMETERIZED_HANDLERS: dict[str, ParameterizedHandler] = {
    "job": _handle_job_uri,
    # Reserved slots — Plans 51-02 and 51-03 swap these placeholders
    # in with real implementations. Do NOT remove these keys; the
    # dispatcher in ``server.py`` keys off the registry, and contract
    # tests assert the four parameterized schemes are all registered.
    "chunk": _handle_not_implemented,
    "graph-entity": _handle_not_implemented,
    "file": _handle_not_implemented,
}


__all__ = [
    "PARAMETERIZED_HANDLERS",
    "PARAMETERIZED_SCHEMES",
    "ParameterizedHandler",
    "ParsedURI",
    "parse_uri",
]
