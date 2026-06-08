"""Tests for ``agent-brain resources list/read`` (Phase 59 Plan 03).

Covers the 12+ must-have behaviors from the Plan 59-03 test plan:

  1. ``resources list`` without ``--transport mcp`` → exit 2 with
     UsageError citing ``--transport mcp``.
  2. ``resources list`` happy path: backend.list_resources() returning
     5 dicts + list_resource_templates() returning 4 dicts → table
     output with all 9 URIs.
  3. ``resources list --json`` → pretty JSON with "resources" +
     "templates" keys.
  4. ``resources list`` default table is sorted alphabetically by URI.
  5. ``resources read`` without ``--transport mcp`` → exit 2.
  6. ``resources read corpus://status`` with JSON content →
     pretty-printed JSON to stdout.
  7. ``resources read file:///x.txt`` with text content → passthrough.
  8. ``resources read file:///x.png`` (binary) WITHOUT --output-file →
     exit 2 with "Resource is binary".
  9. ``resources read file:///x.png --output-file PATH`` → file
     written with decoded bytes + "wrote N bytes to" confirmation.
  10. ``resources read file:///x.txt --output-file PATH`` (text) → file
      written with UTF-8 bytes + confirmation.
  11. ``resources read file:///bad`` with McpError(outside_indexed_roots
      reason) → exit 2; stderr contains "outside_indexed_roots".
  12. Empty contents list → exit 1 with "returned no contents".
  13. (Bonus) Malformed blob (base64 decode fails) → exit 3 with
      "Failed to decode blob".

Scope: UNIT. ``open_mcp_backend`` is patched at the command module's
import site so no real subprocess is ever spawned. Real-MCP coverage
is the end-to-end integration test in
``tests/integration/test_resources_e2e.py`` using the Plan 57 corpus
seeder.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner
from mcp import McpError
from mcp.types import ErrorData

from agent_brain_cli.cli import cli

# ---------------------------------------------------------------------------
# Fake backend factory — context-manager-aware MagicMock
# ---------------------------------------------------------------------------


def _make_fake_backend(
    *,
    list_resources_result: list[dict[str, Any]] | None = None,
    list_resource_templates_result: list[dict[str, Any]] | None = None,
    list_resources_side_effect: BaseException | None = None,
    read_resource_result: dict[str, Any] | None = None,
    read_resource_side_effect: BaseException | None = None,
) -> MagicMock:
    """Build a MagicMock that satisfies the McpBackend Protocol surface."""
    backend = MagicMock()

    if list_resources_side_effect is not None:
        backend.list_resources = MagicMock(side_effect=list_resources_side_effect)
    else:
        backend.list_resources = MagicMock(
            return_value=list_resources_result
            or [
                {"uri": "corpus://config", "mimeType": "application/json"},
                {"uri": "corpus://status", "mimeType": "application/json"},
                {"uri": "corpus://health", "mimeType": "application/json"},
                {"uri": "corpus://providers", "mimeType": "application/json"},
                {"uri": "corpus://folders", "mimeType": "application/json"},
            ]
        )

    backend.list_resource_templates = MagicMock(
        return_value=list_resource_templates_result
        or [
            {"uriTemplate": "chunk://{chunk_id}", "mimeType": "application/json"},
            {
                "uriTemplate": "graph-entity://{type}/{id}",
                "mimeType": "application/json",
            },
            {"uriTemplate": "job://{job_id}", "mimeType": "application/json"},
            {"uriTemplate": "file://{+path}", "mimeType": "application/octet-stream"},
        ]
    )

    if read_resource_side_effect is not None:
        backend.read_resource = MagicMock(side_effect=read_resource_side_effect)
    else:
        backend.read_resource = MagicMock(
            return_value=read_resource_result
            or {
                "contents": [
                    {
                        "uri": "corpus://status",
                        "mimeType": "application/json",
                        "text": json.dumps({"total_documents": 5}),
                    }
                ]
            }
        )

    # Context-manager surface — defensive in case any code path uses it.
    backend.__enter__ = MagicMock(return_value=backend)
    backend.__exit__ = MagicMock(return_value=None)
    backend.close = MagicMock(return_value=None)
    return backend


# ---------------------------------------------------------------------------
# Tests — list subcommand
# ---------------------------------------------------------------------------


def test_resources_list_requires_transport_mcp() -> None:
    """Without --transport mcp, exit 2 with --transport mcp wording."""
    runner = CliRunner()
    result = runner.invoke(cli, ["resources", "list"])

    assert result.exit_code == 2, (
        f"Expected exit 2, got {result.exit_code}\n"
        f"stdout: {result.output}\nexception: {result.exception!r}"
    )
    assert "--transport mcp" in result.output


def test_resources_list_default_table_output() -> None:
    """Happy path: 5 static + 4 templates → table contains all 9 URIs."""
    backend = _make_fake_backend()
    with patch(
        "agent_brain_cli.commands.resources.open_mcp_backend",
        return_value=backend,
    ):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--transport",
                "mcp",
                "--mcp-transport",
                "stdio",
                "resources",
                "list",
            ],
        )

    assert result.exit_code == 0, (
        f"Expected exit 0, got {result.exit_code}\n"
        f"stdout: {result.output}\nexception: {result.exception!r}"
    )
    # All 5 static URIs visible.
    assert "corpus://config" in result.output
    assert "corpus://status" in result.output
    assert "corpus://health" in result.output
    assert "corpus://providers" in result.output
    assert "corpus://folders" in result.output
    # All 4 templated schemes visible.
    assert "chunk" in result.output
    assert "graph-entity" in result.output
    assert "job" in result.output
    assert "file" in result.output


def test_resources_list_json_flag() -> None:
    """--json flag → pretty JSON dict with 'resources' + 'templates' keys."""
    backend = _make_fake_backend()
    with patch(
        "agent_brain_cli.commands.resources.open_mcp_backend",
        return_value=backend,
    ):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--transport",
                "mcp",
                "--mcp-transport",
                "stdio",
                "resources",
                "list",
                "--json",
            ],
        )

    assert (
        result.exit_code == 0
    ), f"Expected exit 0, got {result.exit_code}\nstdout: {result.output}"
    parsed = json.loads(result.output)
    assert "resources" in parsed
    assert "templates" in parsed
    assert len(parsed["resources"]) == 5
    assert len(parsed["templates"]) == 4
    # Pretty-printed (more than one line).
    assert result.output.count("\n") >= 2


def test_resources_list_sorted_alphabetically() -> None:
    """Default table output is sorted alphabetically by URI."""
    backend = _make_fake_backend()
    with patch(
        "agent_brain_cli.commands.resources.open_mcp_backend",
        return_value=backend,
    ):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--transport",
                "mcp",
                "--mcp-transport",
                "stdio",
                "resources",
                "list",
            ],
        )

    assert result.exit_code == 0
    # chunk:// < corpus:// < file:// < graph-entity:// < job:// alphabetically
    # Find positions of each URI in the output.
    chunk_pos = result.output.find("chunk:")
    corpus_config_pos = result.output.find("corpus://config")
    file_pos = result.output.find("file:")
    graph_pos = result.output.find("graph-entity:")
    job_pos = result.output.find("job:")

    assert chunk_pos != -1 and corpus_config_pos != -1
    assert file_pos != -1 and graph_pos != -1 and job_pos != -1
    # Alphabetical: chunk < corpus < file < graph-entity < job
    assert chunk_pos < corpus_config_pos
    assert corpus_config_pos < file_pos
    assert file_pos < graph_pos
    assert graph_pos < job_pos


# ---------------------------------------------------------------------------
# Tests — read subcommand
# ---------------------------------------------------------------------------


def test_resources_read_requires_transport_mcp() -> None:
    """Without --transport mcp, read exits 2."""
    runner = CliRunner()
    result = runner.invoke(cli, ["resources", "read", "corpus://status"])

    assert result.exit_code == 2
    assert "--transport mcp" in result.output


def test_resources_read_json_content_pretty_printed() -> None:
    """JSON content (application/json mime) → pretty-printed via json.dumps."""
    canned = {
        "contents": [
            {
                "uri": "corpus://status",
                "mimeType": "application/json",
                "text": json.dumps({"total": 5, "nested": {"k": "v"}}),
            }
        ]
    }
    backend = _make_fake_backend(read_resource_result=canned)
    with patch(
        "agent_brain_cli.commands.resources.open_mcp_backend",
        return_value=backend,
    ):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--transport",
                "mcp",
                "--mcp-transport",
                "stdio",
                "resources",
                "read",
                "corpus://status",
            ],
        )

    assert (
        result.exit_code == 0
    ), f"Expected exit 0, got {result.exit_code}\nstdout: {result.output}"
    # Pretty-printed: indented form has '"total": 5' (with space after colon).
    assert '"total": 5' in result.output
    # Multi-line (pretty-printed).
    assert result.output.count("\n") >= 4


def test_resources_read_text_passthrough() -> None:
    """Text content (text/plain mime) → passthrough to stdout."""
    canned = {
        "contents": [
            {
                "uri": "file:///x.txt",
                "mimeType": "text/plain",
                "text": "hello\nworld",
            }
        ]
    }
    backend = _make_fake_backend(read_resource_result=canned)
    with patch(
        "agent_brain_cli.commands.resources.open_mcp_backend",
        return_value=backend,
    ):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--transport",
                "mcp",
                "--mcp-transport",
                "stdio",
                "resources",
                "read",
                "file:///x.txt",
            ],
        )

    assert result.exit_code == 0
    # click.echo adds a trailing newline; the body is "hello\nworld".
    assert result.output == "hello\nworld\n"


def test_resources_read_binary_without_output_file_rejected() -> None:
    """Binary content (blob present) without --output-file → exit 2 + msg."""
    raw_bytes = b"\x89PNG\r\n\x1a\n"  # 8 bytes
    canned = {
        "contents": [
            {
                "uri": "file:///x.png",
                "mimeType": "image/png",
                "blob": base64.b64encode(raw_bytes).decode(),
            }
        ]
    }
    backend = _make_fake_backend(read_resource_result=canned)
    with patch(
        "agent_brain_cli.commands.resources.open_mcp_backend",
        return_value=backend,
    ):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--transport",
                "mcp",
                "--mcp-transport",
                "stdio",
                "resources",
                "read",
                "file:///x.png",
            ],
        )

    assert result.exit_code == 2
    assert "Resource is binary" in result.output
    assert "image/png" in result.output
    assert "--output-file" in result.output


def test_resources_read_binary_with_output_file_writes_bytes(
    tmp_path: Path,
) -> None:
    """Binary content + --output-file → file written; confirmation echoed."""
    raw_bytes = b"\x89PNG\r\n\x1a\n"  # 8 bytes
    out_path = tmp_path / "out.png"
    canned = {
        "contents": [
            {
                "uri": "file:///x.png",
                "mimeType": "image/png",
                "blob": base64.b64encode(raw_bytes).decode(),
            }
        ]
    }
    backend = _make_fake_backend(read_resource_result=canned)
    with patch(
        "agent_brain_cli.commands.resources.open_mcp_backend",
        return_value=backend,
    ):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--transport",
                "mcp",
                "--mcp-transport",
                "stdio",
                "resources",
                "read",
                "file:///x.png",
                "--output-file",
                str(out_path),
            ],
        )

    assert result.exit_code == 0, (
        f"Expected exit 0, got {result.exit_code}\n"
        f"stdout: {result.output}\nexception: {result.exception!r}"
    )
    assert out_path.exists()
    assert out_path.read_bytes() == raw_bytes
    assert f"wrote {len(raw_bytes)} bytes to" in result.output


def test_resources_read_text_with_output_file_writes_bytes(
    tmp_path: Path,
) -> None:
    """Text content + --output-file → file written with UTF-8 bytes."""
    body = "hello world\nutf-8 üñîçødé\n"
    out_path = tmp_path / "out.txt"
    canned = {
        "contents": [
            {
                "uri": "file:///x.txt",
                "mimeType": "text/plain",
                "text": body,
            }
        ]
    }
    backend = _make_fake_backend(read_resource_result=canned)
    with patch(
        "agent_brain_cli.commands.resources.open_mcp_backend",
        return_value=backend,
    ):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--transport",
                "mcp",
                "--mcp-transport",
                "stdio",
                "resources",
                "read",
                "file:///x.txt",
                "--output-file",
                str(out_path),
            ],
        )

    assert result.exit_code == 0
    assert out_path.exists()
    expected_bytes = body.encode("utf-8")
    assert out_path.read_bytes() == expected_bytes
    assert f"wrote {len(expected_bytes)} bytes to" in result.output


def test_resources_read_outside_indexed_roots_surfaces_server_verdict() -> None:
    """McpError with outside_indexed_roots reason → exit 2, stderr verbatim."""
    err = McpError(
        ErrorData(
            code=-32602,
            message="file outside_indexed_roots: /disallowed/path",
            data={"reason": "outside_indexed_roots", "uri": "file:///disallowed/path"},
        )
    )
    backend = _make_fake_backend(read_resource_side_effect=err)
    with patch(
        "agent_brain_cli.commands.resources.open_mcp_backend",
        return_value=backend,
    ):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--transport",
                "mcp",
                "--mcp-transport",
                "stdio",
                "resources",
                "read",
                "file:///disallowed/path",
            ],
        )

    assert result.exit_code == 2
    # The literal reason from the server is surfaced verbatim.
    assert "outside_indexed_roots" in result.output.lower()


def test_resources_read_empty_contents_exits_1() -> None:
    """Empty contents list → exit 1 with 'returned no contents'."""
    canned: dict[str, Any] = {"contents": []}
    backend = _make_fake_backend(read_resource_result=canned)
    with patch(
        "agent_brain_cli.commands.resources.open_mcp_backend",
        return_value=backend,
    ):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--transport",
                "mcp",
                "--mcp-transport",
                "stdio",
                "resources",
                "read",
                "corpus://status",
            ],
        )

    assert result.exit_code == 1
    assert "returned no contents" in result.output


def test_resources_read_malformed_blob_exits_3(tmp_path: Path) -> None:
    """Malformed blob + --output-file → exit 3 with 'Failed to decode blob'."""
    canned = {
        "contents": [
            {
                "uri": "file:///x.png",
                "mimeType": "image/png",
                # Not valid base64 — the '!' character is outside the alphabet
                # AND the length is not a multiple of 4 → raises binascii.Error.
                "blob": "not-valid-base64!@#$",
            }
        ]
    }
    out_path = tmp_path / "out.png"
    backend = _make_fake_backend(read_resource_result=canned)
    with patch(
        "agent_brain_cli.commands.resources.open_mcp_backend",
        return_value=backend,
    ):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--transport",
                "mcp",
                "--mcp-transport",
                "stdio",
                "resources",
                "read",
                "file:///x.png",
                "--output-file",
                str(out_path),
            ],
        )

    assert (
        result.exit_code == 3
    ), f"Expected exit 3, got {result.exit_code}\nstdout: {result.output}"
    assert "Failed to decode blob" in result.output


# ---------------------------------------------------------------------------
# Help — confirms --json / --output-file surface
# ---------------------------------------------------------------------------


def test_resources_group_help_lists_list_and_read() -> None:
    """`agent-brain resources --help` lists both subcommands."""
    runner = CliRunner()
    result = runner.invoke(cli, ["resources", "--help"])

    assert result.exit_code == 0
    assert "list" in result.output
    assert "read" in result.output


def test_resources_list_help_shows_json_flag() -> None:
    """`agent-brain resources list --help` documents --json flag."""
    runner = CliRunner()
    result = runner.invoke(cli, ["resources", "list", "--help"])

    assert result.exit_code == 0
    assert "--json" in result.output


def test_resources_read_help_shows_options() -> None:
    """`agent-brain resources read --help` documents --output-file and --json."""
    runner = CliRunner()
    result = runner.invoke(cli, ["resources", "read", "--help"])

    assert result.exit_code == 0
    assert "--output-file" in result.output
    assert "--json" in result.output
    assert "URI" in result.output


# ---------------------------------------------------------------------------
# Parametrized matrix for mime-type dispatch behavior
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "mime,text,expected_substring,expect_pretty",
    [
        # JSON mime → parsed and pretty-printed.
        ("application/json", '{"key": "value"}', '"key": "value"', True),
        # text/plain → passthrough.
        ("text/plain", "raw text content", "raw text content", False),
        # text/markdown → passthrough.
        ("text/markdown", "# Heading\nbody", "# Heading", False),
        # application/text (legacy literal) → passthrough.
        ("application/text", "legacy text body", "legacy text body", False),
    ],
)
def test_resources_read_mime_dispatch_matrix(
    mime: str, text: str, expected_substring: str, expect_pretty: bool
) -> None:
    """Mime-type dispatch matrix: JSON pretty / text passthrough."""
    canned = {
        "contents": [
            {"uri": "corpus://x", "mimeType": mime, "text": text},
        ]
    }
    backend = _make_fake_backend(read_resource_result=canned)
    with patch(
        "agent_brain_cli.commands.resources.open_mcp_backend",
        return_value=backend,
    ):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--transport",
                "mcp",
                "--mcp-transport",
                "stdio",
                "resources",
                "read",
                "corpus://x",
            ],
        )

    assert result.exit_code == 0
    assert expected_substring in result.output
