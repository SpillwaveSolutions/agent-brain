"""Folder-related tools: ``list_folders`` (TOOL-05).

Phase 54 Plan 02 lands ``handle_list_folders``. Plan 03 will EXTEND
this module with ``handle_remove_folder`` (TOOL-06) — do not pre-empt
that work here.

``list_folders`` is a thin wrapper over the existing v1
:meth:`ApiClient.list_folders` (no new HTTP method needed; the route
was already exercised by the ``corpus://folders`` resource handler).
The server-side response carries an explicit ``total`` count alongside
the folder list; we project both into :class:`ListFoldersOutput`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..schemas import (
    FolderInfoMcp,
    ListFoldersInput,
    ListFoldersOutput,
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
