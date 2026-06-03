"""Phase 54 Plan 03 — handler tests for ``inject_documents`` (TOOL-03).

Coverage:
    * Happy path with ``injector_script``: request body carries the
      absolute resolved path (mirroring CLI ``inject`` behavior).
    * Happy path with ``folder_metadata_file``: same path-expansion
      contract on the metadata field.
    * Pydantic root validator rejects construction when both
      ``injector_script`` and ``folder_metadata_file`` are None
      (Phase 54 Plan 01 + CONTEXT decision D).
    * Dry-run path: server returns ``{job_id='dry_run', status='completed',
      message=<report>}``; the handler returns the same shape so MCP
      clients can branch on ``out.job_id == 'dry_run'``.
    * 403 from server (issue #181 — script not in hash allowlist)
      surfaces as :class:`McpError(INVALID_PARAMS)` via the existing
      :func:`errors.raise_for_status` pipeline.

Path expansion: the handler calls ``Path(...).expanduser().resolve()``
on every non-None script/metadata path. We use the test's own absolute
paths so ``.resolve()`` is a no-op and the assertion is stable across
machines.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx
import pytest
from mcp import McpError
from pydantic import ValidationError

from agent_brain_mcp.client import ApiClient
from agent_brain_mcp.errors import INVALID_PARAMS
from agent_brain_mcp.schemas import InjectDocumentsInput
from agent_brain_mcp.tools.inject import handle_inject_documents


def _make_capturing_client(
    response_body: dict[str, Any],
    response_status: int = 200,
) -> tuple[ApiClient, list[httpx.Request]]:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(response_status, json=response_body)

    transport = httpx.MockTransport(handler)
    return (
        ApiClient(
            httpx.Client(transport=transport, base_url="http://test-agent-brain")
        ),
        captured,
    )


class TestInjectDocumentsHappyPath:
    def test_with_injector_script_resolves_to_absolute_path(
        self, tmp_path: Path
    ) -> None:
        # Use a real on-disk script so Path.resolve() returns a stable
        # absolute path. ``tmp_path`` is itself absolute.
        script = tmp_path / "enrich.py"
        script.write_text("def process_chunk(c):\n    return c\n")

        api, captured = _make_capturing_client(
            {"job_id": "job-1", "status": "queued", "message": "queued"}
        )
        out = handle_inject_documents(
            api,
            InjectDocumentsInput(
                folder_path="/abs/repo",
                injector_script=str(script),
            ),
        )
        assert out.job_id == "job-1"
        assert out.status == "queued"

        req = captured[0]
        assert req.method == "POST"
        assert req.url.path == "/index/"
        body = json.loads(req.content)
        # Path was sent verbatim because it's already absolute & resolved.
        assert body["injector_script"] == str(script.resolve())
        assert body["folder_path"] == "/abs/repo"
        assert body["dry_run"] is False
        assert body["include_code"] is True
        # Defense-in-depth: allow_external MUST NOT appear (issue #180).
        assert "allow_external" not in body

    def test_with_folder_metadata_file_resolves_to_absolute_path(
        self, tmp_path: Path
    ) -> None:
        metadata = tmp_path / "meta.json"
        metadata.write_text('{"team": "platform"}')

        api, captured = _make_capturing_client({"job_id": "job-2", "status": "queued"})
        handle_inject_documents(
            api,
            InjectDocumentsInput(
                folder_path="/abs/repo",
                folder_metadata_file=str(metadata),
            ),
        )
        body = json.loads(captured[0].content)
        assert body["folder_metadata_file"] == str(metadata.resolve())
        # injector_script absent because the caller didn't provide one.
        assert "injector_script" not in body

    def test_expands_tilde_in_paths(self, tmp_path: Path, monkeypatch) -> None:
        """``~`` is expanded by the handler via ``Path.expanduser()`` so
        callers can pass ``~/scripts/enrich.py`` and the server receives
        an absolute path (matching CLI inject UX)."""
        # Set HOME to tmp_path so ~ expands to a deterministic absolute path.
        monkeypatch.setenv("HOME", str(tmp_path))
        script_in_home = tmp_path / "enrich.py"
        script_in_home.write_text("def process_chunk(c):\n    return c\n")

        api, captured = _make_capturing_client({"job_id": "j", "status": "queued"})
        handle_inject_documents(
            api,
            InjectDocumentsInput(
                folder_path="/abs/repo",
                injector_script="~/enrich.py",
            ),
        )
        body = json.loads(captured[0].content)
        # On macOS, /tmp -> /private/tmp via symlink resolution; assert
        # the path is absolute and points at the script (real path).
        sent = body["injector_script"]
        assert os.path.isabs(sent)
        assert sent == str(script_in_home.resolve())


class TestInjectDocumentsValidation:
    def test_both_none_rejected_by_pydantic(self) -> None:
        """The :class:`InjectDocumentsInput` ``@model_validator`` rejects
        construction when both injector_script and folder_metadata_file
        are None (Phase 54 Plan 01 / CONTEXT D)."""
        with pytest.raises(ValidationError) as excinfo:
            InjectDocumentsInput(folder_path="/x")
        msg = str(excinfo.value)
        assert "injector_script" in msg or "folder_metadata_file" in msg


class TestInjectDocumentsDryRun:
    def test_dry_run_returns_dry_run_job_id(self, tmp_path: Path) -> None:
        script = tmp_path / "e.py"
        script.write_text("def process_chunk(c):\n    return c\n")

        api, captured = _make_capturing_client(
            {
                "job_id": "dry_run",
                "status": "completed",
                "message": "validation ok: 3 chunks would be enriched",
            }
        )
        out = handle_inject_documents(
            api,
            InjectDocumentsInput(
                folder_path="/abs/repo",
                injector_script=str(script),
                dry_run=True,
            ),
        )
        assert out.job_id == "dry_run"
        assert out.status == "completed"
        assert out.message is not None and "validation ok" in out.message

        body = json.loads(captured[0].content)
        assert body["dry_run"] is True


class TestInjectDocuments403:
    def test_403_surfaces_as_invalid_params_with_server_detail(
        self, tmp_path: Path
    ) -> None:
        """Issue #181 — unallowlisted injector scripts return 403 from the
        server. The existing :func:`errors.raise_for_status` pipeline maps
        4xx-not-in-explicit-table → ``INVALID_PARAMS``.
        """
        script = tmp_path / "e.py"
        script.write_text("def process_chunk(c):\n    return c\n")

        api, _ = _make_capturing_client(
            {"detail": "Script not in hash allowlist"},
            response_status=403,
        )
        with pytest.raises(McpError) as excinfo:
            handle_inject_documents(
                api,
                InjectDocumentsInput(
                    folder_path="/abs/repo",
                    injector_script=str(script),
                ),
            )
        err = excinfo.value.error
        assert err.code == INVALID_PARAMS
        # The server's detail string surfaces in the error message so MCP
        # clients can render a helpful "add the script to the allowlist"
        # hint.
        assert "Script not in hash allowlist" in err.message
