"""Folder-related tools: ``list_folders`` (TOOL-05) + ``remove_folder`` (TOOL-06).

Plan 02 landed :func:`handle_list_folders`. Plan 03 EXTENDS this module
with :func:`handle_remove_folder` — the destructive counterpart guarded
by ``confirm: Literal[True]`` at the Pydantic layer.

``list_folders`` is a thin wrapper over the existing v1
:meth:`ApiClient.list_folders` (no new HTTP method needed; the route
was already exercised by the ``corpus://folders`` resource handler).
The server-side response carries an explicit ``total`` count alongside
the folder list; we project both into :class:`ListFoldersOutput`.

``remove_folder`` wraps :meth:`ApiClient.delete_folder`
(``DELETE /index/folders/`` with body, not query). The 409 returned
when an indexing job is active for the folder (FOLD-07) surfaces via
the existing :func:`errors.raise_for_status` pipeline — see Phase 54
CONTEXT decision G.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..schemas import (
    FolderInfoMcp,
    ListFoldersInput,
    ListFoldersOutput,
    RemoveFolderInput,
    RemoveFolderOutput,
)

if TYPE_CHECKING:
    from ..client import ApiClient


def handle_list_folders(
    client: ApiClient,
    args: ListFoldersInput,  # noqa: ARG001 — uniform ToolSpec handler signature
) -> ListFoldersOutput:
    """Return all indexed folders + total count via ``GET /index/folders/``.

    Args:
        client: Authenticated ``ApiClient``.
        args: Empty input model (kept for ToolSpec signature uniformity).

    Returns:
        :class:`ListFoldersOutput` projecting the server's
        ``FolderListResponse`` (folder list + total). When the corpus is
        empty, the server returns ``{"folders": [], "total": 0}`` — the
        same shape is preserved on the MCP side.
    """
    raw = client.list_folders()
    folders_raw: list[dict[str, Any]] = list(raw.get("folders") or [])
    folders = [
        FolderInfoMcp(
            folder_path=str(f.get("folder_path", "")),
            chunk_count=int(f.get("chunk_count", 0)),
            last_indexed=str(f.get("last_indexed", "")),
            watch_mode=str(f.get("watch_mode", "off")),
            watch_debounce_seconds=f.get("watch_debounce_seconds"),
        )
        for f in folders_raw
    ]
    # The server's FolderListResponse always populates ``total``; fall
    # back to ``len(folders)`` for defense-in-depth against future
    # response-shape shrinkage.
    total = int(raw.get("total", len(folders)))
    return ListFoldersOutput(folders=folders, total=total)


def handle_remove_folder(
    client: ApiClient, args: RemoveFolderInput
) -> RemoveFolderOutput:
    """Remove an indexed folder from the corpus.

    Pydantic's ``Literal[True]`` ``confirm`` field guards the destructive
    operation — invocations without ``confirm=True`` are rejected before
    this handler runs. The handler then forwards the ``folder_path`` to
    :meth:`ApiClient.delete_folder` (``DELETE /index/folders/`` with the
    folder path in the request body).

    409-when-job-active behavior (FOLD-07): when an indexing job is
    running for the same folder, the server returns 409 with a detail
    message; :func:`errors.raise_for_status` surfaces it as an
    :class:`McpError` with code ``BACKEND_CONFLICT`` (Phase 54 CONTEXT
    decision G — uniform error mapping, no per-handler translation).
    The tool description names the operator-visible behavior so MCP
    clients can render a helpful "cancel the active job first" hint.

    Args:
        client: Authenticated :class:`ApiClient`.
        args: Validated :class:`RemoveFolderInput` carrying
            ``folder_path`` and ``confirm: Literal[True]``.

    Returns:
        :class:`RemoveFolderOutput` mirroring ``FolderDeleteResponse``
        (``folder_path`` / ``chunks_deleted`` / ``message``).
    """
    # ``confirm: Literal[True]`` is enforced by Pydantic at construction;
    # a defensive re-check here would be redundant (the value is either
    # True or the schema rejected). We still send the folder path as a
    # request body — the server's DELETE /index/folders/ route declares
    # FolderDeleteRequest as the body, NOT a query/path param.
    body: dict[str, Any] = {"folder_path": args.folder_path}
    raw = client.delete_folder(body)
    return RemoveFolderOutput(
        folder_path=str(raw.get("folder_path", args.folder_path)),
        chunks_deleted=int(raw.get("chunks_deleted", 0)),
        message=str(raw.get("message", "")),
    )
