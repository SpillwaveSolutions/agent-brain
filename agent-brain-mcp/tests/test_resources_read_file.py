"""Phase 51 Plan 03 (URI-04): ``file://`` URI handler tests.

Mirrors :mod:`tests.test_resources_read_parameterized` for the file
scheme. Kept in a sibling test module rather than appended to the
parameterized test file because the sandbox fixtures are filesystem-
heavy and would push the parent file past 400 LOC.

Coverage:

- Text success — ``file:///<tmp>/allowed.txt`` returns
  ``ReadResourceContents`` with text body + text MIME.
- Binary success — ``file:///<tmp>/allowed.bin`` returns bytes
  content (MCP SDK auto-encodes as base64 BlobResourceContents).
- Outside-root denial — ``file:///<denied>/secret.txt`` →
  INVALID_PARAMS with ``data["reason"] == "outside_indexed_roots"``.
- Symlink-to-outside denial — symlink inside allowed root pointing
  to denied file → ``data["reason"] == "symlink_escape"``.
- Hidden file OUTSIDE root denial — ``file:///<denied>/.env`` →
  ``data["reason"] == "hidden_file"``.
- Size cap denial — file larger than DEFAULT_MAX_READ_BYTES →
  ``data["reason"] == "size_limit"``.
- ``..`` traversal blocked — canonicalization collapses ``..`` and
  the result falls outside roots → ``outside_indexed_roots``.
- Hidden file INSIDE root is allowed — root policy wins per Phase
  50 module docstring.
- Missing path — ``file://`` (empty path) → ``missing_path``.
- Two-slash form rejected — ``file://relative/path`` →
  ``missing_path``.
- Roots-refresh-on-each-read regression — two consecutive
  ``resources/read`` calls result in TWO ``GET /index/folders/``
  calls (no cache).
- ``parse_uri`` unit tests for the ``file://`` cases that the
  end-to-end tests don't naturally cover.
"""

from __future__ import annotations

import base64

import mcp.types as types
import pytest
from mcp import McpError
from pydantic import AnyUrl

from agent_brain_mcp.errors import INVALID_PARAMS
from agent_brain_mcp.resources import parse_uri
from agent_brain_mcp.server import build_server
from tests.conftest import FileSandboxScenario, make_file_sandbox_httpx_client


async def _read(server, uri: str):
    """Invoke the low-level ``resources/read`` handler and return the
    raw ``ServerResult`` contents (wire-level types)."""
    handler = server.request_handlers[types.ReadResourceRequest]
    req = types.ReadResourceRequest(
        method="resources/read",
        params=types.ReadResourceRequestParams(uri=AnyUrl(uri)),
    )
    result = await handler(req)
    return result.root.contents


def _path_to_uri(p) -> str:
    """Render a Path as a ``file:///abs/path`` URI."""
    # Path.as_uri() handles encoding for us and produces the
    # canonical three-slash form for absolute paths.
    return p.as_uri()


# --- parse_uri unit tests for file:// -----------------------------------


class TestParseUriFile:
    """Pure ``parse_uri`` behavior for the ``file://`` scheme."""

    def test_file_uri_three_slash_extracts_path(self) -> None:
        parsed = parse_uri("file:///tmp/foo.py")
        assert parsed is not None
        assert parsed.scheme == "file"
        assert parsed.path == "/tmp/foo.py"

    def test_file_uri_three_slash_with_nested_dirs(self) -> None:
        parsed = parse_uri("file:///var/lib/agent-brain/index.json")
        assert parsed is not None
        assert parsed.path == "/var/lib/agent-brain/index.json"

    def test_file_uri_empty_raises_missing_path(self) -> None:
        with pytest.raises(McpError) as ei:
            parse_uri("file://")
        assert ei.value.error.code == INVALID_PARAMS
        assert ei.value.error.data == {
            "uri": "file://",
            "reason": "missing_path",
        }

    def test_file_uri_two_slash_form_rejected(self) -> None:
        # ``file://relative/path`` — urlsplit reads ``relative`` as
        # netloc/authority. Decision: reject so callers can't smuggle
        # relative paths past the sandbox.
        with pytest.raises(McpError) as ei:
            parse_uri("file://relative/path")
        assert ei.value.error.code == INVALID_PARAMS
        assert ei.value.error.data == {
            "uri": "file://relative/path",
            "reason": "missing_path",
        }

    def test_file_uri_host_form_rejected(self) -> None:
        # ``file://host/path`` — same shape, also rejected. Any non-
        # empty authority means the URI is not the canonical local-
        # path form we accept.
        with pytest.raises(McpError) as ei:
            parse_uri("file://some.host/path")
        assert ei.value.error.code == INVALID_PARAMS
        assert ei.value.error.data["reason"] == "missing_path"

    def test_file_uri_only_slash_path_accepted_by_parser(self) -> None:
        # ``file:///`` has path == "/" which is technically a valid
        # absolute path at the parser layer. The downstream sandbox
        # check rejects it because ``/`` is never an indexed root.
        # Parse layer just checks ``path.startswith("/")``.
        parsed = parse_uri("file:///")
        assert parsed is not None
        assert parsed.path == "/"


# --- end-to-end ``resources/read`` for ``file://`` -----------------------


class TestReadResourceFileUri:
    """End-to-end ``file://`` reads through the parameterized dispatcher."""

    @pytest.mark.asyncio
    async def test_read_file_uri_text_success(
        self, tmp_path_with_indexed_root: FileSandboxScenario
    ) -> None:
        client = make_file_sandbox_httpx_client(tmp_path_with_indexed_root)
        server, _ = build_server(client)
        uri = _path_to_uri(tmp_path_with_indexed_root.allowed_text)

        contents = await _read(server, uri)
        assert len(contents) == 1
        # The MCP SDK wraps text content as TextResourceContents at
        # the wire boundary.
        c = contents[0]
        assert isinstance(c, types.TextResourceContents)
        assert c.text == "hello from allowed root\n"
        # text/plain because the file extension is .txt
        assert c.mimeType == "text/plain"

    @pytest.mark.asyncio
    async def test_read_file_uri_binary_success(
        self, tmp_path_with_indexed_root: FileSandboxScenario
    ) -> None:
        client = make_file_sandbox_httpx_client(tmp_path_with_indexed_root)
        server, _ = build_server(client)
        uri = _path_to_uri(tmp_path_with_indexed_root.allowed_binary)

        contents = await _read(server, uri)
        assert len(contents) == 1
        c = contents[0]
        # Binary file -> BlobResourceContents (base64-encoded).
        assert isinstance(c, types.BlobResourceContents)
        decoded = base64.b64decode(c.blob)
        assert decoded == b"\x00\x01\x02\x03BINARYDATA\xff\xfe"
        # .bin sniffs as application/octet-stream (mimetypes.guess_type
        # returns None for .bin -> handler falls back to octet-stream).
        assert c.mimeType == "application/octet-stream"

    @pytest.mark.asyncio
    async def test_read_file_uri_outside_root_denied(
        self, tmp_path_with_indexed_root: FileSandboxScenario
    ) -> None:
        client = make_file_sandbox_httpx_client(tmp_path_with_indexed_root)
        server, _ = build_server(client)
        uri = _path_to_uri(tmp_path_with_indexed_root.denied_file)

        with pytest.raises(McpError) as ei:
            await _read(server, uri)
        err = ei.value.error
        assert err.code == INVALID_PARAMS
        assert isinstance(err.data, dict)
        assert err.data["scheme"] == "file"
        assert err.data["reason"] == "outside_indexed_roots"
        assert err.data["path"] == str(tmp_path_with_indexed_root.denied_file)

    @pytest.mark.asyncio
    async def test_read_file_uri_symlink_to_outside_blocked(
        self, tmp_path_with_indexed_root: FileSandboxScenario
    ) -> None:
        # Symlink LIVES inside the allowed root but points to a file
        # OUTSIDE every root. Phase 50: literal path is a symlink, so
        # the most-specific deny reason is ``symlink_escape``.
        client = make_file_sandbox_httpx_client(tmp_path_with_indexed_root)
        server, _ = build_server(client)
        # IMPORTANT: do NOT canonicalize the URI ourselves — the
        # handler does that. We want the wire URI to reference the
        # literal symlink so is_path_allowed sees it as a symlink.
        symlink = tmp_path_with_indexed_root.symlink_escape
        uri = f"file://{symlink}"

        with pytest.raises(McpError) as ei:
            await _read(server, uri)
        err = ei.value.error
        assert err.code == INVALID_PARAMS
        assert err.data["scheme"] == "file"
        assert err.data["reason"] == "symlink_escape"

    @pytest.mark.asyncio
    async def test_read_file_uri_hidden_file_outside_root_denied(
        self, tmp_path_with_indexed_root: FileSandboxScenario
    ) -> None:
        # `.env` inside ``denied/`` — outside every root AND
        # dot-prefixed. Most-specific reason: ``hidden_file``.
        client = make_file_sandbox_httpx_client(tmp_path_with_indexed_root)
        server, _ = build_server(client)
        uri = _path_to_uri(tmp_path_with_indexed_root.outside_hidden)

        with pytest.raises(McpError) as ei:
            await _read(server, uri)
        err = ei.value.error
        assert err.code == INVALID_PARAMS
        assert err.data["scheme"] == "file"
        assert err.data["reason"] == "hidden_file"

    @pytest.mark.asyncio
    async def test_read_file_uri_hidden_file_inside_root_allowed(
        self, tmp_path_with_indexed_root: FileSandboxScenario
    ) -> None:
        # Phase 50 explicit rule: dot-files INSIDE an indexed root
        # are allowed (root policy wins). Read should SUCCEED.
        client = make_file_sandbox_httpx_client(tmp_path_with_indexed_root)
        server, _ = build_server(client)
        uri = _path_to_uri(tmp_path_with_indexed_root.hidden_file)

        contents = await _read(server, uri)
        assert len(contents) == 1
        c = contents[0]
        # `.secret` has no extension -> mimetypes returns None ->
        # falls back to application/octet-stream blob.
        assert isinstance(c, types.BlobResourceContents)
        assert base64.b64decode(c.blob) == b"hidden but inside root\n"

    @pytest.mark.asyncio
    async def test_read_file_uri_size_limit_blocked(
        self, tmp_path_with_indexed_root: FileSandboxScenario
    ) -> None:
        # ``big.txt`` is DEFAULT_MAX_READ_BYTES + 1 — strict greater-
        # than triggers ``size_limit``.
        client = make_file_sandbox_httpx_client(tmp_path_with_indexed_root)
        server, _ = build_server(client)
        uri = _path_to_uri(tmp_path_with_indexed_root.big_text)

        with pytest.raises(McpError) as ei:
            await _read(server, uri)
        err = ei.value.error
        assert err.code == INVALID_PARAMS
        assert err.data["scheme"] == "file"
        assert err.data["reason"] == "size_limit"

    @pytest.mark.asyncio
    async def test_read_file_uri_traversal_blocked(
        self, tmp_path_with_indexed_root: FileSandboxScenario
    ) -> None:
        # Input path contains literal ``..`` segments resolving to a
        # file in the denied sibling dir. Canonicalization collapses
        # the ``..`` and the resolved path falls outside every root.
        client = make_file_sandbox_httpx_client(tmp_path_with_indexed_root)
        server, _ = build_server(client)
        uri = f"file://{tmp_path_with_indexed_root.traversal_attempt}"

        with pytest.raises(McpError) as ei:
            await _read(server, uri)
        err = ei.value.error
        assert err.code == INVALID_PARAMS
        assert err.data["scheme"] == "file"
        # The literal input path is NOT a symlink (it's a string with
        # ``..`` in it). So Phase 50's precedence falls to either
        # hidden_file or outside_indexed_roots. With no hidden
        # components on this path, the reason should be
        # outside_indexed_roots.
        assert err.data["reason"] == "outside_indexed_roots"

    @pytest.mark.asyncio
    async def test_read_file_uri_empty_path_resolves_to_root_and_denied(
        self, tmp_path_with_indexed_root: FileSandboxScenario
    ) -> None:
        # ``file://`` reaches the MCP server already normalized to
        # ``file:///`` (pydantic's AnyUrl always emits the canonical
        # three-slash form for a ``file:`` scheme with empty
        # authority). So end-to-end, this URI parses to path == "/"
        # and the sandbox denies it as outside every indexed root.
        # Verifies the AnyUrl normalization is transparent to the
        # dispatcher and that the deny path is consistent.
        #
        # The ``missing_path`` shape is still asserted at the
        # ``parse_uri`` unit level in
        # ``TestParseUriFile.test_file_uri_empty_raises_missing_path``
        # — there ``parse_uri("file://")`` is called directly, no
        # AnyUrl normalization.
        client = make_file_sandbox_httpx_client(tmp_path_with_indexed_root)
        server, _ = build_server(client)

        with pytest.raises(McpError) as ei:
            await _read(server, "file://")
        err = ei.value.error
        assert err.code == INVALID_PARAMS
        assert isinstance(err.data, dict)
        assert err.data["scheme"] == "file"
        assert err.data["reason"] == "outside_indexed_roots"

    @pytest.mark.asyncio
    async def test_read_file_uri_two_slash_form_rejected_at_read(
        self, tmp_path_with_indexed_root: FileSandboxScenario
    ) -> None:
        client = make_file_sandbox_httpx_client(tmp_path_with_indexed_root)
        server, _ = build_server(client)

        with pytest.raises(McpError) as ei:
            await _read(server, "file://relative/path")
        err = ei.value.error
        assert err.code == INVALID_PARAMS
        assert err.data["reason"] == "missing_path"

    @pytest.mark.asyncio
    async def test_read_file_uri_roots_refresh_on_each_read(
        self, tmp_path_with_indexed_root: FileSandboxScenario
    ) -> None:
        # Decision E load-bearing rule: NO cache on list_folders().
        # Two consecutive ``resources/read`` calls must result in TWO
        # ``GET /index/folders/`` requests — otherwise stale roots
        # could silently widen the sandbox after the operator
        # mutates the folder list.
        counter: list[int] = [0]
        client = make_file_sandbox_httpx_client(
            tmp_path_with_indexed_root,
            folders_call_counter=counter,
        )
        server, _ = build_server(client)
        uri = _path_to_uri(tmp_path_with_indexed_root.allowed_text)

        await _read(server, uri)
        assert counter[0] == 1, "first read should hit /index/folders/ once"
        await _read(server, uri)
        assert counter[0] == 2, (
            "second read must re-fetch /index/folders/ — caching the roots "
            "would defeat the sandbox correctness guarantee from CONTEXT "
            "decision E"
        )
