"""Parameterized URI schemes — Phase 51 (URI-01 / URI-02 / URI-03 / URI-04).

Sister module to :mod:`agent_brain_mcp.resources.corpus`. Where ``corpus``
holds the 5 static ``corpus://*`` resources keyed by exact URI string,
this module holds the *parameterized* schemes whose URIs carry per-read
arguments and therefore can't live in a string-keyed registry:

- ``chunk://<chunk_id>`` (Plan 51-02 — URI-01)
- ``graph-entity://<type>/<id>`` (Plan 51-02 — URI-02)
- ``job://<job_id>`` (Plan 51-01 — URI-03)
- ``file://<abs-path>`` (Plan 51-03 — URI-04)

Plan 51-01 lands the dispatcher infrastructure plus the ``job://``
handler as the exemplar. Plan 51-02 swaps in real handlers for
``chunk://`` and ``graph-entity://``. Plan 51-03 (this completes the
parameterized layer) swaps in ``file://`` — the only scheme that
does NOT hit the FastAPI server. It reads bytes off disk after the
path is validated against the dynamically-fetched list of indexed
roots from ``corpus://folders``, gated by the Phase 50 sandbox helper
re-exported through :mod:`agent_brain_mcp.security`.

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
import mimetypes
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

import mcp.types as types
from mcp import McpError
from mcp.server.lowlevel.helper_types import ReadResourceContents
from mcp.types import ErrorData

from ..errors import INVALID_PARAMS
from ..security import (
    DEFAULT_MAX_READ_BYTES,
    canonicalize_path,
    is_path_allowed,
)

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
        # ``file://<abs-path>`` — RFC 3986 requires three slashes for an
        # absolute path with empty authority: ``file:///abs/path``. In
        # that canonical form, ``urlsplit(...)`` returns ``netloc=""``
        # and ``path="/abs/path"`` (path starts with ``/``).
        #
        # The two-slash form ``file://abs/path`` is non-canonical for
        # absolute paths: urlsplit reads ``abs`` as the netloc (host)
        # and ``/path`` as the path. We reject this so callers cannot
        # accidentally smuggle relative paths past the sandbox check by
        # writing ``file://relative/secret`` — they MUST use the three-
        # slash form, which forces an absolute path.
        #
        # We do NOT enforce existence or "is regular file" here — the
        # sandbox helper and ``handle_file_uri`` body do that.
        if netloc:
            raise _invalid_uri(uri, "missing_path")
        path = raw_path
        if not path or not path.startswith("/"):
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


async def _handle_graph_entity_uri(client: ApiClient, params: ParsedURI) -> str:
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


async def _handle_file_uri(
    client: ApiClient, params: ParsedURI
) -> ReadResourceContents:
    """Read ``file:///<abs-path>`` → raw file contents from disk (URI-04).

    The only parameterized scheme that does NOT hit the FastAPI server.
    The path is sandboxed against the dynamically-fetched list of
    indexed folder roots from :meth:`ApiClient.list_folders` and read
    directly off disk inside the MCP process.

    Plan 51-03 / Phase 51 CONTEXT decision E pipeline:

    1. **Refresh roots** from ``GET /index/folders/`` on EVERY read
       (no cache — folders can be added/removed during a session,
       and stale roots would silently widen the sandbox).
    2. **Canonicalize** the URI path via :func:`canonicalize_path`,
       which calls ``Path.resolve(strict=False)`` and so resolves
       symlinks plus collapses ``..`` segments.
    3. **Sandbox check** via :func:`is_path_allowed` — returns
       ``(allowed, reason)`` where ``reason`` is one of the Phase 50
       literals: ``outside_indexed_roots`` | ``hidden_file`` |
       ``symlink_escape`` | ``size_limit``. We re-emit the reason
       verbatim in the ``data["reason"]`` blob so MCP clients can
       route on it without re-parsing.
    4. **Pre-flight size check** via ``Path.stat().st_size`` so we
       refuse oversized files BEFORE loading them into memory.
       :func:`is_path_allowed` also does this check, but we repeat it
       here so a misconfigured operator who raised the sandbox cap
       still gets a clean error if the file truly does exceed
       :data:`DEFAULT_MAX_READ_BYTES`.
    5. **Read bytes** via ``asyncio.to_thread(Path.read_bytes)`` —
       no ``aiofiles`` dependency added; the standard library is
       enough and keeps the MCP package's footprint lean.
    6. **MIME sniff + text/binary dispatch** via
       :func:`mimetypes.guess_type`. ``text/*`` MIMEs are decoded as
       UTF-8 and returned via ``ReadResourceContents(content=str)``;
       any non-text MIME (or a UTF-8 decode failure on a mis-typed
       text file) falls through to bytes content, which the MCP SDK
       auto-encodes as ``BlobResourceContents`` with base64.

    Error contract (Phase 51 CONTEXT decision E):

    - Sandbox denial → ``McpError(INVALID_PARAMS, data={"scheme":
      "file", "path": <input>, "reason": <Phase 50 literal>})``.
    - Size cap → same shape, ``reason == "size_limit"``, plus
      ``data["size"]`` and ``data["limit"]`` for ops visibility.
    - Missing file or stat error inside an allowed root → propagates
      as an OSError-wrapped INVALID_PARAMS.

    TOCTOU note: the pre-flight ``stat`` and the subsequent
    ``read_bytes`` are not atomic. For the agent-brain threat model
    (local-first, single-user) this is acceptable; a malicious local
    actor with write access to an indexed folder is already trusted.
    """
    assert params.path is not None  # parse_uri guarantees this
    input_path = params.path

    # Step 1: refresh allowed roots from the server (no cache).
    folders_response = await asyncio.to_thread(client.list_folders)
    folders_list = folders_response.get("folders", [])
    roots = [f["folder_path"] for f in folders_list if "folder_path" in f]

    # Step 2: canonicalize the input path.
    canonical = canonicalize_path(input_path)

    # Step 3: sandbox decision. is_path_allowed expects (str|Path,
    # Sequence[str|Path], max_bytes). We pass the *canonical* path so
    # the symlink-escape rule, which inspects the literal path's
    # ``.is_symlink()`` against the unresolved input, sees the right
    # node — but the literal input may itself BE a symlink, so we
    # pass it via a side check too.
    #
    # The Phase 50 module already handles symlink resolution inside
    # is_path_allowed; we forward the original *input* so the literal
    # symlink check uses the unresolved form. Callers must NOT do
    # their own resolution before this call.
    allowed, reason = is_path_allowed(input_path, roots)
    if not allowed:
        raise McpError(
            ErrorData(
                code=INVALID_PARAMS,
                message=f"file:// access denied: {reason}",
                data={
                    "scheme": "file",
                    "path": input_path,
                    "reason": reason,
                },
            )
        )

    # Step 4: pre-flight size check — refuse oversized files BEFORE
    # loading them into memory. is_path_allowed already checks this
    # against the configured cap, but we double-check here against
    # DEFAULT_MAX_READ_BYTES so a future caller that bypasses the
    # sandbox helper still gets a sane upper bound.
    try:
        st = await asyncio.to_thread(canonical.stat)
    except OSError as exc:
        raise McpError(
            ErrorData(
                code=INVALID_PARAMS,
                message=f"file:// stat failed: {exc}",
                data={
                    "scheme": "file",
                    "path": input_path,
                    "reason": "not_found",
                    "cause": str(exc),
                },
            )
        ) from exc

    if st.st_size > DEFAULT_MAX_READ_BYTES:
        raise McpError(
            ErrorData(
                code=INVALID_PARAMS,
                message=(
                    f"file:// too large: {st.st_size} bytes > "
                    f"{DEFAULT_MAX_READ_BYTES} byte limit"
                ),
                data={
                    "scheme": "file",
                    "path": input_path,
                    "reason": "size_limit",
                    "size": st.st_size,
                    "limit": DEFAULT_MAX_READ_BYTES,
                },
            )
        )

    # Step 5: read bytes off disk.
    raw = await asyncio.to_thread(canonical.read_bytes)

    # Step 6: MIME sniff + text/binary dispatch.
    mime, _ = mimetypes.guess_type(str(canonical))
    if mime and mime.startswith("text/"):
        try:
            return ReadResourceContents(
                content=raw.decode("utf-8"),
                mime_type=mime,
            )
        except UnicodeDecodeError:
            # Mis-typed as text (e.g., latin-1 .txt) — fall through
            # to blob with the originally-guessed MIME so the client
            # can still attempt its own decode.
            return ReadResourceContents(
                content=raw,
                mime_type=mime,
            )

    # Binary or unknown — return bytes. The MCP SDK's read_resource
    # decorator auto-wraps bytes as BlobResourceContents (base64).
    return ReadResourceContents(
        content=raw,
        mime_type=mime or "application/octet-stream",
    )


async def _handle_not_implemented(client: ApiClient, params: ParsedURI) -> str:
    """Placeholder for schemes wired in later Plan 51 plans.

    All three previously-reserved slots (``chunk``, ``graph-entity``,
    ``file``) now have real handlers landed by Plans 51-02 and 51-03.
    This callable is retained for two reasons:

    1. **Future schemes** added to :data:`PARAMETERIZED_SCHEMES` can
       use it as a temporary placeholder while their real handler is
       being planned — same pattern Plans 51-02 and 51-03 followed.
    2. **Defensive registry coverage** — :data:`PARAMETERIZED_HANDLERS`
       must have an entry for every key in
       :data:`PARAMETERIZED_SCHEMES`. Contract tests assert this; a
       missing key would silently misroute a valid URI to the
       ``Unknown resource`` fallback instead of failing loud.
    """
    raise NotImplementedError(
        f"Handler for scheme '{params.scheme}' is not implemented yet "
        f"(landed in a later Phase 51 plan)."
    )


# Async handler signature. JSON-backed schemes (``job``, ``chunk``,
# ``graph-entity``) return ``str`` which the server dispatcher wraps
# as ``application/json``. The ``file://`` handler returns a
# :class:`ReadResourceContents` directly so it can carry a per-file
# mime_type plus optional ``bytes`` payload (auto-base64-encoded into
# a ``BlobResourceContents`` by the MCP SDK at the wire boundary).
# The server dispatcher in ``server.py`` checks ``isinstance(content,
# ReadResourceContents)`` and uses it verbatim or wraps the str.
ParameterizedHandler = Callable[
    ["ApiClient", ParsedURI], Awaitable[str | ReadResourceContents]
]


PARAMETERIZED_HANDLERS: dict[str, ParameterizedHandler] = {
    "job": _handle_job_uri,
    "chunk": _handle_chunk_uri,
    "graph-entity": _handle_graph_entity_uri,
    "file": _handle_file_uri,
}


# --- RFC 6570 URI templates for ``resources/templates/list`` -------------
#
# Phase 51 CONTEXT decision B locks the four ``uriTemplate`` strings the
# MCP server advertises. These are a **forward-compatibility commitment**:
# once published in ``resources/templates/list``, MCP client libraries
# (including future Agent Brain CLI v3 work) lock onto them. Changing a
# template string after release is a breaking change.
#
# Notable choices:
#
# - ``chunk://{chunk_id}`` — single opaque id (per Phase 50 ``ChunkRecord``).
# - ``graph-entity://{type}/{id}`` — short names (NOT ``{entity_type}/
#   {entity_id}``) per CONTEXT decision B. Mirrors the HTTP route shape
#   ``GET /graph/entity/{type}/{id}``.
# - ``job://{job_id}`` — single opaque id, matches CLI conventions.
# - ``file://{+path}`` — RFC 6570 *reserved expansion* (operator ``+``).
#   The default expansion percent-encodes ``/`` (the very character
#   filesystem paths require); the ``+`` operator preserves reserved
#   characters so clients can expand a path like ``/tmp/foo.py`` without
#   encoding the slashes.
#
# ``mimeType`` is set for the three JSON-backed schemes; ``file://``
# leaves it unset (``None``) because the MIME type is sniffed per-read
# (CONTEXT decision E). The MCP SDK serializes the field as absent when
# the model value is ``None``, which matches the spec form.
TEMPLATE_REGISTRY: list[types.ResourceTemplate] = [
    types.ResourceTemplate(
        uriTemplate="chunk://{chunk_id}",
        name="chunk",
        description=(
            "Retrieve a single indexed chunk by id. Returns the chunk's "
            "content, summary, source path, language, token count, and "
            "parent-doc id. The embedding vector is intentionally "
            "excluded — use POST /query/ if you need vectors."
        ),
        mimeType="application/json",
    ),
    types.ResourceTemplate(
        uriTemplate="graph-entity://{type}/{id}",
        name="graph-entity",
        description=(
            "Retrieve a GraphRAG entity by type and id. Returns the "
            "entity plus its 1-hop incoming and outgoing neighbors. "
            "Returns SERVICE_INDEXING if GraphRAG is disabled or the "
            "Kuzu backend is unavailable; multi-hop traversal is not "
            "supported in this scheme."
        ),
        mimeType="application/json",
    ),
    types.ResourceTemplate(
        uriTemplate="job://{job_id}",
        name="job",
        description=(
            "Retrieve the current state of an indexing job by id "
            "(status, progress percent, file counts, started/updated "
            "timestamps). Phase 51 exposes this as a one-shot read; "
            "live subscriptions (notifications/resources/updated at 1s "
            "cadence) ship in Phase 52."
        ),
        mimeType="application/json",
    ),
    types.ResourceTemplate(
        uriTemplate="file://{+path}",
        name="file",
        description=(
            "Read a file by absolute path. Access is gated by the "
            "indexed-folder sandbox (canonicalize_path + "
            "is_path_allowed); reads outside indexed roots, symlinks "
            "that escape roots, hidden files outside roots, and files "
            "above the 10 MiB read cap are denied. MIME type is sniffed "
            "per-read via mimetypes.guess_type, so it is not advertised "
            "statically on the template."
        ),
        # mimeType intentionally omitted — per-read sniff.
    ),
]


__all__ = [
    "PARAMETERIZED_HANDLERS",
    "PARAMETERIZED_SCHEMES",
    "ParameterizedHandler",
    "ParsedURI",
    "TEMPLATE_REGISTRY",
    "parse_uri",
]
