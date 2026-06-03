"""Index-related tools.

v1 ``index_folder`` (``POST /index/?force=&allow_external=``) plus the
Phase 54 Plan 03 addition ``add_documents`` (``POST /index/add?force=``).

Phase 54 Plan 03 EXTENDS this module with :func:`handle_add_documents`.
The v1 :func:`handle_index_folder` is left untouched — its
``allow_external`` argument predates issue #180 and stays as a v1 bug
to track separately (see Phase 54 CONTEXT specifics §3). The new
``add_documents`` tool is the modern, post-#180 entry point that does
NOT expose ``allow_external``; the server-side
``AGENT_BRAIN_ALLOW_EXTERNAL_PATHS`` setting is the sole containment
control going forward.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..schemas import (
    AddDocumentsInput,
    AddDocumentsOutput,
    IndexFolderInput,
    IndexFolderOutput,
)

if TYPE_CHECKING:
    from ..client import ApiClient


def handle_index_folder(client: ApiClient, args: IndexFolderInput) -> IndexFolderOutput:
    body: dict[str, object] = {
        "folder_path": args.folder_path,
        "include_code": args.include_code,
    }
    if args.chunk_size is not None:
        body["chunk_size"] = args.chunk_size
    if args.chunk_overlap is not None:
        body["chunk_overlap"] = args.chunk_overlap

    raw = client.index_folder(
        body, force=args.force, allow_external=args.allow_external
    )
    return IndexFolderOutput(
        job_id=str(raw.get("job_id", "")),
        status=str(raw.get("status", "queued")),
        message=raw.get("message"),
        folder_path=args.folder_path,
    )


def handle_add_documents(
    client: ApiClient, args: AddDocumentsInput
) -> AddDocumentsOutput:
    """Add a list of document paths to the existing index.

    Wraps :meth:`ApiClient.add_documents` (``POST /index/add``). The
    ``allow_external`` parameter was removed from the server route by
    issue #180; this handler intentionally does NOT include
    ``allow_external`` in the request body. Server-side containment is
    enforced exclusively by ``AGENT_BRAIN_ALLOW_EXTERNAL_PATHS``.

    Args:
        client: Authenticated :class:`ApiClient`.
        args: Validated :class:`AddDocumentsInput` carrying a
            non-empty ``paths`` list and the ``force`` flag.

    Returns:
        :class:`AddDocumentsOutput` mirroring ``IndexResponse``
        (``job_id`` / ``status`` / optional ``message``).
    """
    # NOTE: do NOT add an ``allow_external`` field to ``body``. Issue #180
    # removed the server-side parameter; exposing it MCP-side would be a
    # silent no-op and a security drift signal.
    body: dict[str, object] = {"paths": list(args.paths)}
    raw = client.add_documents(body, force=args.force)
    return AddDocumentsOutput(
        job_id=str(raw.get("job_id", "")),
        status=str(raw.get("status", "queued")),
        message=raw.get("message"),
    )
