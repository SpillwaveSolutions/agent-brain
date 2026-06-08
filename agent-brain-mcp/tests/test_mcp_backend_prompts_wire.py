"""Phase 59 Plan 02 — wire-level tests for the 5 McpBackend methods
on both ``McpStdioBackend`` and ``McpHttpBackend``.

Plan 59-01 shipped the 10 method bodies as skeletons (5 methods × 2
backends) raising ``NotImplementedError("Wired in Phase 59 Plan 02")``.
This plan replaces those bodies with real ``asyncio.run``-internal
sync-facade implementations that drive the MCP SDK's ``stdio_client``
/ ``streamablehttp_client`` against the
``prompts/get`` + ``prompts/list`` + ``resources/list`` +
``resources/templates/list`` + ``resources/read`` MCP surface.

These tests mock the MCP SDK call layer (``stdio_client`` /
``streamablehttp_client`` + ``ClientSession``) so the wire code can be
exercised without spawning a real subprocess or HTTP listener. Layer
2 integration coverage comes from the Plan 57 corpus seeder in
``agent-brain-cli/tests/integration/_corpus.py`` (out of scope here).

Patterns:
  - ``stdio_client`` is patched at the call site
    (``agent_brain_mcp.client.stdio_client``)... but the wire-body
    late-imports the SDK inside each helper, so we patch the SDK module
    directly: ``mcp.client.stdio.stdio_client`` and
    ``mcp.client.streamable_http.streamablehttp_client``.
  - ``ClientSession`` is patched at ``mcp.ClientSession`` (the same
    late-import path).
  - We use ``AsyncMock``-backed async context managers because both
    ``stdio_client(...)`` and ``ClientSession(...)`` are entered with
    ``async with``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import mcp.types as types
import pytest
from pydantic import AnyUrl

from agent_brain_mcp.client import McpHttpBackend, McpStdioBackend


# ---------------------------------------------------------------------------
# Canned SDK return values — Pydantic models shaped like real SDK results.
# ---------------------------------------------------------------------------


def _make_get_prompt_result() -> types.GetPromptResult:
    """A non-empty GetPromptResult with one user-role text message."""
    return types.GetPromptResult(
        description="Find callers of a symbol.",
        messages=[
            types.PromptMessage(
                role="user",
                content=types.TextContent(type="text", text="Find callers of foo."),
            )
        ],
    )


def _make_list_prompts_result() -> types.ListPromptsResult:
    return types.ListPromptsResult(
        prompts=[
            types.Prompt(name="find-callers", description="Find symbol callers."),
            types.Prompt(name="explain-architecture", description="Explain it."),
        ]
    )


def _make_list_resources_result() -> types.ListResourcesResult:
    return types.ListResourcesResult(
        resources=[
            types.Resource(
                uri=AnyUrl("corpus://status"),
                name="status",
                mimeType="application/json",
            )
        ]
    )


def _make_list_resource_templates_result() -> types.ListResourceTemplatesResult:
    return types.ListResourceTemplatesResult(
        resourceTemplates=[
            types.ResourceTemplate(
                uriTemplate="chunk://{chunk_id}",
                name="chunk",
                mimeType="application/json",
            )
        ]
    )


def _make_read_resource_result() -> types.ReadResourceResult:
    return types.ReadResourceResult(
        contents=[
            types.TextResourceContents(
                uri=AnyUrl("corpus://status"),
                mimeType="application/json",
                text='{"healthy": true}',
            )
        ]
    )


# ---------------------------------------------------------------------------
# Mock session builder — returns the AsyncMock the test can assert against.
# ---------------------------------------------------------------------------


def _make_mock_session(
    *,
    get_prompt_result: types.GetPromptResult | None = None,
    list_prompts_result: types.ListPromptsResult | None = None,
    list_resources_result: types.ListResourcesResult | None = None,
    list_resource_templates_result: types.ListResourceTemplatesResult | None = None,
    read_resource_result: types.ReadResourceResult | None = None,
) -> MagicMock:
    """Build a ClientSession-shaped MagicMock with the 5 SDK methods
    pre-wired to return the canned Pydantic results.

    Each method is an AsyncMock returning the corresponding canned
    result (or a default empty one).
    """
    session = MagicMock()
    session.initialize = AsyncMock(return_value=None)
    session.get_prompt = AsyncMock(
        return_value=get_prompt_result or _make_get_prompt_result()
    )
    session.list_prompts = AsyncMock(
        return_value=list_prompts_result or _make_list_prompts_result()
    )
    session.list_resources = AsyncMock(
        return_value=list_resources_result or _make_list_resources_result()
    )
    session.list_resource_templates = AsyncMock(
        return_value=list_resource_templates_result
        or _make_list_resource_templates_result()
    )
    session.read_resource = AsyncMock(
        return_value=read_resource_result or _make_read_resource_result()
    )
    return session


def _stdio_patch_targets(session: MagicMock) -> tuple[Any, Any]:
    """Build patches for ``stdio_client`` and ``ClientSession`` (stdio leg).

    ``stdio_client(params)`` is used as an async context manager that
    yields ``(read, write)``; ``ClientSession(read, write)`` is used as
    an async context manager that yields the session.
    """
    # stdio_client(...) returns an async context manager yielding (r, w)
    stdio_acm = MagicMock()
    stdio_acm.__aenter__ = AsyncMock(return_value=(MagicMock(), MagicMock()))
    stdio_acm.__aexit__ = AsyncMock(return_value=None)
    stdio_client_mock = MagicMock(return_value=stdio_acm)

    # ClientSession(r, w) returns an async context manager yielding session
    session_acm = MagicMock()
    session_acm.__aenter__ = AsyncMock(return_value=session)
    session_acm.__aexit__ = AsyncMock(return_value=None)
    client_session_mock = MagicMock(return_value=session_acm)

    return stdio_client_mock, client_session_mock


def _http_patch_targets(session: MagicMock) -> tuple[Any, Any]:
    """Build patches for ``streamablehttp_client`` and ``ClientSession``.

    ``streamablehttp_client(url)`` returns an async context manager
    yielding ``(read, write, session_id_factory)``.
    """
    http_acm = MagicMock()
    http_acm.__aenter__ = AsyncMock(
        return_value=(MagicMock(), MagicMock(), MagicMock())
    )
    http_acm.__aexit__ = AsyncMock(return_value=None)
    http_client_mock = MagicMock(return_value=http_acm)

    session_acm = MagicMock()
    session_acm.__aenter__ = AsyncMock(return_value=session)
    session_acm.__aexit__ = AsyncMock(return_value=None)
    client_session_mock = MagicMock(return_value=session_acm)

    return http_client_mock, client_session_mock


# ---------------------------------------------------------------------------
# Stdio backend fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def stdio_backend() -> McpStdioBackend:
    """A McpStdioBackend pointed at a dummy command — never actually run."""
    return McpStdioBackend(command="agent-brain-mcp")


# ---------------------------------------------------------------------------
# Stdio backend — 5 methods
# ---------------------------------------------------------------------------


def test_get_prompt_stdio_returns_messages_dict(
    stdio_backend: McpStdioBackend,
) -> None:
    """get_prompt('find-callers', {'symbol': 'foo'}) returns a dict with
    a non-empty messages list."""
    session = _make_mock_session()
    stdio_client_mock, client_session_mock = _stdio_patch_targets(session)

    with (
        patch("mcp.client.stdio.stdio_client", stdio_client_mock),
        patch("mcp.ClientSession", client_session_mock),
    ):
        result = stdio_backend.get_prompt("find-callers", {"symbol": "foo"})

    assert isinstance(result, dict)
    assert "messages" in result
    assert isinstance(result["messages"], list)
    assert len(result["messages"]) >= 1


def test_get_prompt_stdio_passes_arguments_to_sdk(
    stdio_backend: McpStdioBackend,
) -> None:
    """get_prompt forwards (name, arguments) verbatim to session.get_prompt."""
    session = _make_mock_session()
    stdio_client_mock, client_session_mock = _stdio_patch_targets(session)

    with (
        patch("mcp.client.stdio.stdio_client", stdio_client_mock),
        patch("mcp.ClientSession", client_session_mock),
    ):
        stdio_backend.get_prompt("find-callers", {"symbol": "foo"})

    session.get_prompt.assert_awaited_once_with("find-callers", {"symbol": "foo"})


def test_get_prompt_stdio_passes_none_arguments_when_unspecified(
    stdio_backend: McpStdioBackend,
) -> None:
    """get_prompt(name) (no arguments) forwards ``None`` to the SDK.

    Per CONTEXT.md decision: ``None`` is preserved end-to-end (the MCP
    server treats ``None`` vs ``{}`` as semantically different).
    """
    session = _make_mock_session()
    stdio_client_mock, client_session_mock = _stdio_patch_targets(session)

    with (
        patch("mcp.client.stdio.stdio_client", stdio_client_mock),
        patch("mcp.ClientSession", client_session_mock),
    ):
        stdio_backend.get_prompt("audit-indexed-folders")

    session.get_prompt.assert_awaited_once_with("audit-indexed-folders", None)


def test_list_prompts_stdio_returns_list_of_dicts(
    stdio_backend: McpStdioBackend,
) -> None:
    """list_prompts() returns list[dict] of length matching the SDK result."""
    session = _make_mock_session()
    stdio_client_mock, client_session_mock = _stdio_patch_targets(session)

    with (
        patch("mcp.client.stdio.stdio_client", stdio_client_mock),
        patch("mcp.ClientSession", client_session_mock),
    ):
        result = stdio_backend.list_prompts()

    assert isinstance(result, list)
    assert len(result) == 2
    assert all(isinstance(p, dict) for p in result)
    assert {p["name"] for p in result} == {"find-callers", "explain-architecture"}


def test_list_resources_stdio_returns_list_of_dicts(
    stdio_backend: McpStdioBackend,
) -> None:
    """list_resources() returns list[dict] with a 'uri' key on each entry."""
    session = _make_mock_session()
    stdio_client_mock, client_session_mock = _stdio_patch_targets(session)

    with (
        patch("mcp.client.stdio.stdio_client", stdio_client_mock),
        patch("mcp.ClientSession", client_session_mock),
    ):
        result = stdio_backend.list_resources()

    assert isinstance(result, list)
    assert len(result) >= 1
    assert all(isinstance(r, dict) for r in result)
    assert "uri" in result[0]


def test_list_resource_templates_stdio_returns_list_of_dicts(
    stdio_backend: McpStdioBackend,
) -> None:
    """list_resource_templates() returns list[dict] from the
    resourceTemplates field (camelCase from MCP spec).
    """
    session = _make_mock_session()
    stdio_client_mock, client_session_mock = _stdio_patch_targets(session)

    with (
        patch("mcp.client.stdio.stdio_client", stdio_client_mock),
        patch("mcp.ClientSession", client_session_mock),
    ):
        result = stdio_backend.list_resource_templates()

    assert isinstance(result, list)
    assert len(result) >= 1
    assert all(isinstance(t, dict) for t in result)
    # mode='json' serializes camelCase keys
    assert "uriTemplate" in result[0]


def test_read_resource_stdio_returns_contents_dict(
    stdio_backend: McpStdioBackend,
) -> None:
    """read_resource(uri) returns a dict with a 'contents' list."""
    session = _make_mock_session()
    stdio_client_mock, client_session_mock = _stdio_patch_targets(session)

    with (
        patch("mcp.client.stdio.stdio_client", stdio_client_mock),
        patch("mcp.ClientSession", client_session_mock),
    ):
        result = stdio_backend.read_resource("corpus://status")

    assert isinstance(result, dict)
    assert "contents" in result
    assert isinstance(result["contents"], list)
    assert len(result["contents"]) >= 1


# ---------------------------------------------------------------------------
# HTTP backend fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def http_backend() -> McpHttpBackend:
    """A McpHttpBackend pointed at a fake URL — never actually contacted."""
    return McpHttpBackend(url="http://127.0.0.1:9999/mcp")


# ---------------------------------------------------------------------------
# HTTP backend — 5 methods (mirror stdio coverage)
# ---------------------------------------------------------------------------


def test_get_prompt_http_returns_messages_dict(
    http_backend: McpHttpBackend,
) -> None:
    session = _make_mock_session()
    http_client_mock, client_session_mock = _http_patch_targets(session)

    with (
        patch("mcp.client.streamable_http.streamablehttp_client", http_client_mock),
        patch("mcp.ClientSession", client_session_mock),
    ):
        result = http_backend.get_prompt("find-callers", {"symbol": "foo"})

    assert isinstance(result, dict)
    assert "messages" in result
    assert len(result["messages"]) >= 1


def test_list_prompts_http_returns_list_of_dicts(
    http_backend: McpHttpBackend,
) -> None:
    session = _make_mock_session()
    http_client_mock, client_session_mock = _http_patch_targets(session)

    with (
        patch("mcp.client.streamable_http.streamablehttp_client", http_client_mock),
        patch("mcp.ClientSession", client_session_mock),
    ):
        result = http_backend.list_prompts()

    assert isinstance(result, list)
    assert len(result) == 2
    assert {p["name"] for p in result} == {"find-callers", "explain-architecture"}


def test_list_resources_http_returns_list_of_dicts(
    http_backend: McpHttpBackend,
) -> None:
    session = _make_mock_session()
    http_client_mock, client_session_mock = _http_patch_targets(session)

    with (
        patch("mcp.client.streamable_http.streamablehttp_client", http_client_mock),
        patch("mcp.ClientSession", client_session_mock),
    ):
        result = http_backend.list_resources()

    assert isinstance(result, list)
    assert all(isinstance(r, dict) for r in result)


def test_list_resource_templates_http_returns_list_of_dicts(
    http_backend: McpHttpBackend,
) -> None:
    session = _make_mock_session()
    http_client_mock, client_session_mock = _http_patch_targets(session)

    with (
        patch("mcp.client.streamable_http.streamablehttp_client", http_client_mock),
        patch("mcp.ClientSession", client_session_mock),
    ):
        result = http_backend.list_resource_templates()

    assert isinstance(result, list)
    assert all(isinstance(t, dict) for t in result)


def test_read_resource_http_returns_contents_dict(
    http_backend: McpHttpBackend,
) -> None:
    session = _make_mock_session()
    http_client_mock, client_session_mock = _http_patch_targets(session)

    with (
        patch("mcp.client.streamable_http.streamablehttp_client", http_client_mock),
        patch("mcp.ClientSession", client_session_mock),
    ):
        result = http_backend.read_resource("corpus://status")

    assert isinstance(result, dict)
    assert "contents" in result


# ---------------------------------------------------------------------------
# Sentinel removal pin
# ---------------------------------------------------------------------------


def test_no_skeleton_sentinel_remains_in_phase_59_methods() -> None:
    """The Plan 59-01 sentinel ``"Wired in Phase 59 Plan 02"`` MUST NOT
    appear within ±5 lines of any of the 5 Phase 59 method ``def`` sites.

    Plan 02 removes the sentinel and replaces each body with a real
    wire. Allows the literal to remain ANYWHERE else in the file
    (e.g., a comment referring to the lift) — but pins removal at the
    method bodies.
    """
    client_py = (
        Path(__file__).resolve().parent.parent
        / "agent_brain_mcp"
        / "client.py"
    )
    src = client_py.read_text()
    lines = src.splitlines()

    sentinel = "Wired in Phase 59 Plan 02"
    method_def_pattern = re.compile(
        r"^\s*def\s+("
        r"get_prompt|list_prompts|list_resources|"
        r"list_resource_templates|read_resource)\s*\("
    )

    method_def_lines = [
        i for i, line in enumerate(lines) if method_def_pattern.match(line)
    ]
    # 5 methods × 2 backends → exactly 10 def sites for the public API.
    assert len(method_def_lines) == 10, (
        f"Expected 10 public method def sites (5 × 2 backends); "
        f"found {len(method_def_lines)}."
    )

    for line_idx in method_def_lines:
        lo = max(0, line_idx - 5)
        hi = min(len(lines), line_idx + 6)
        window = "\n".join(lines[lo:hi])
        assert sentinel not in window, (
            f"Plan 59-01 sentinel still appears near method def at "
            f"line {line_idx + 1}; expected Plan 02 to have replaced "
            f"each body with a real wire."
        )
