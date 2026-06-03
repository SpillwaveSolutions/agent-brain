"""``inject_documents`` tool (TOOL-03, Phase 54 Plan 03).

Wraps :meth:`ApiClient.inject_documents` (``POST /index/``) with
``injector_script`` and/or ``folder_metadata_file`` always populated.

Path expansion: the CLI ``inject`` command (see
``agent-brain-cli/agent_brain_cli/commands/inject.py``) resolves
``--script`` and ``--folder-metadata`` to absolute canonical paths via
``Path(value).resolve()`` before sending to the server. This handler
matches that behavior with ``Path(...).expanduser().resolve()`` so MCP
clients can pass ``~/scripts/enrich.py`` and get the same UX as
``agent-brain inject --script ~/scripts/enrich.py``. The
``.expanduser()`` step is the only additive — the CLI's
``click.Path(exists=True)`` already exists-checks before the call, so
``~`` survives the click validation; we expand here defensively.

Pre-validation: the :class:`InjectDocumentsInput` ``@model_validator``
(Plan 01) already rejects the both-None case at Pydantic construction.
The defensive re-check below covers direct callers that bypass the
schema (e.g., future async wrappers) and the rare race where a Pydantic
model is constructed with private attribute mutation.

Server-side allowlist (issue #181): unallowlisted scripts surface as
403 → ``McpError`` via the existing :func:`errors.raise_for_status`
pipeline. No per-handler error mapping needed.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from mcp import McpError
from mcp.types import ErrorData

from ..errors import INVALID_PARAMS
from ..schemas import InjectDocumentsInput, InjectDocumentsOutput

if TYPE_CHECKING:
    from ..client import ApiClient


def handle_inject_documents(
    client: ApiClient, args: InjectDocumentsInput
) -> InjectDocumentsOutput:
    """Index a folder with content injection.

    At least one of ``injector_script`` or ``folder_metadata_file`` is
    required. Pydantic's ``@model_validator`` rejects construction with
    both None; the defensive re-check below covers direct callers that
    bypass schema validation.

    Args:
        client: Authenticated :class:`ApiClient`.
        args: Validated :class:`InjectDocumentsInput`.

    Returns:
        :class:`InjectDocumentsOutput` mirroring ``IndexResponse``.
        Dry-run returns ``job_id='dry_run'`` and ``status='completed'``.

    Raises:
        McpError: If both ``injector_script`` and ``folder_metadata_file``
            are None (defensive INVALID_PARAMS). Or if the server returns
            403 (script not in hash allowlist per #181) — surfaced
            uniformly via :func:`errors.raise_for_status`.
    """
    # Defensive re-check (Pydantic root validator should already reject).
    if not args.injector_script and not args.folder_metadata_file:
        raise McpError(
            ErrorData(
                code=INVALID_PARAMS,
                message=(
                    "At least one of injector_script or folder_metadata_file "
                    "is required"
                ),
            )
        )

    # NOTE: do NOT add an ``allow_external`` field to ``body``. Issue #180
    # removed the server-side parameter on POST /index/ as well as
    # POST /index/add (Phase 54 Plan 01 SUMMARY deviation §1). Exposing
    # it MCP-side would be a silent no-op + security drift signal.
    body: dict[str, object] = {
        "folder_path": args.folder_path,
        "dry_run": args.dry_run,
        "include_code": args.include_code,
    }
    if args.injector_script:
        # Mirror the CLI's Path(...).resolve() pattern in
        # agent-brain-cli/agent_brain_cli/commands/inject.py line 158;
        # add .expanduser() defensively so ``~/scripts/enrich.py``
        # works through the MCP boundary (the CLI's click.Path layer
        # already expands ~ before reaching the handler).
        body["injector_script"] = str(Path(args.injector_script).expanduser().resolve())
    if args.folder_metadata_file:
        body["folder_metadata_file"] = str(
            Path(args.folder_metadata_file).expanduser().resolve()
        )
    if args.chunk_size is not None:
        body["chunk_size"] = args.chunk_size
    if args.chunk_overlap is not None:
        body["chunk_overlap"] = args.chunk_overlap

    raw = client.inject_documents(body, force=args.force)
    return InjectDocumentsOutput(
        job_id=str(raw.get("job_id", "")),
        status=str(raw.get("status", "queued")),
        message=raw.get("message"),
    )
