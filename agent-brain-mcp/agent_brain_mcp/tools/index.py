"""``index_folder`` tool — POST /index/?force=&allow_external=."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..schemas import IndexFolderInput, IndexFolderOutput

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
