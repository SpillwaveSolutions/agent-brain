"""Unit tests for McpHttpBackend OAuth opt-in path (Phase 69 Plan 03).

These tests exercise the four properties of the auth-injection seam:

1. Default-OFF path (AGENT_BRAIN_MCP_AUTH unset or not "oauth") returns
   None from _get_auth() — byte-identical to the pre-Phase-69 behaviour.
2. With AGENT_BRAIN_MCP_AUTH=oauth and a state_dir, _get_auth() returns an
   instance of httpx.Auth (the OAuthClientProvider) — OAuth is wired.
3. The provider is constructed lazily ONCE per instance — the same object
   is returned on the second call (caching).
4. AGENT_BRAIN_MCP_AUTH=oauth without a state_dir raises RuntimeError —
   token storage cannot be keyed without a directory.
5. Structural guard: agent_brain_mcp.client module source contains exactly
   ONE call to streamablehttp_client() — all 17 former per-method sites now
   route through _http_session().

Context decision A (default OFF): AGENT_BRAIN_MCP_AUTH is unset or any
value other than "oauth" (case-insensitive) → auth=None → byte-identical to
the pre-Phase-69 path.

Context decision B (one helper): _http_session() is the sole seam that
calls streamablehttp_client().
"""

from __future__ import annotations

import inspect
import os
from pathlib import Path

import httpx
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_backend(
    url: str = "http://127.0.0.1:9999/mcp",
    state_dir: Path | None = None,
) -> object:
    """Construct a McpHttpBackend without importing at module level.

    Lazy import keeps the module-level import cost zero for tests that only
    use the McpHttpBackend class (not the full MCP SDK stack).
    """
    from agent_brain_mcp.client import McpHttpBackend  # noqa: PLC0415

    return McpHttpBackend(url=url, state_dir=state_dir)


# ---------------------------------------------------------------------------
# Test 1 — default OFF: unset env returns None (auth=None / byte-identical)
# ---------------------------------------------------------------------------


def test_get_auth_unset_env_returns_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When AGENT_BRAIN_MCP_AUTH is unset, _get_auth() returns None.

    This is the default-OFF path (Context decision A).  auth=None passed to
    streamablehttp_client() is byte-identical to the pre-Phase-69 behaviour.
    """
    monkeypatch.delenv("AGENT_BRAIN_MCP_AUTH", raising=False)

    backend = _make_backend(state_dir=tmp_path)
    assert backend._get_auth() is None  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Test 2 — non-"oauth" value also returns None
# ---------------------------------------------------------------------------


def test_get_auth_non_oauth_value_returns_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Any value other than "oauth" (case-insensitive) disables OAuth.

    "basic", empty string, and other strings must all produce None.
    """
    for value in ("basic", "", "none", "BASIC"):
        monkeypatch.setenv("AGENT_BRAIN_MCP_AUTH", value)

        backend = _make_backend(state_dir=tmp_path)
        result = backend._get_auth()  # type: ignore[union-attr]
        assert result is None, f"Expected None for AGENT_BRAIN_MCP_AUTH={value!r}"


# ---------------------------------------------------------------------------
# Test 3 — oauth ON + state_dir → returns httpx.Auth instance + caching
# ---------------------------------------------------------------------------


def test_get_auth_oauth_returns_provider_and_caches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With AGENT_BRAIN_MCP_AUTH=oauth and a state_dir, _get_auth() returns
    a non-None httpx.Auth instance (the OAuthClientProvider) and caches it —
    the second call returns the SAME instance (lazy-once construction).
    """
    monkeypatch.setenv("AGENT_BRAIN_MCP_AUTH", "oauth")

    backend = _make_backend(state_dir=tmp_path)

    first = backend._get_auth()  # type: ignore[union-attr]
    assert first is not None, "_get_auth() returned None when OAuth is enabled"
    assert isinstance(first, httpx.Auth), (
        f"Expected httpx.Auth instance, got {type(first)}"
    )

    # Second call must return the SAME object (lazy-once caching).
    second = backend._get_auth()  # type: ignore[union-attr]
    assert second is first, (
        "_get_auth() returned a different provider instance on the second call "
        "(provider should be constructed once per McpHttpBackend instance)"
    )


# ---------------------------------------------------------------------------
# Test 4 — oauth ON + state_dir=None → RuntimeError
# ---------------------------------------------------------------------------


def test_get_auth_oauth_without_state_dir_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AGENT_BRAIN_MCP_AUTH=oauth without a state_dir raises RuntimeError.

    FileTokenStorage cannot be keyed without a storage directory.  The error
    message must mention AGENT_BRAIN_MCP_AUTH and state_dir.
    """
    monkeypatch.setenv("AGENT_BRAIN_MCP_AUTH", "oauth")

    from agent_brain_mcp.client import McpHttpBackend  # noqa: PLC0415

    # When url is provided and state_dir is None, __init__ succeeds because
    # discovery is not needed — but _get_auth() should still raise.
    backend = McpHttpBackend(url="http://127.0.0.1:9999/mcp", state_dir=None)

    with pytest.raises(RuntimeError, match="AGENT_BRAIN_MCP_AUTH=oauth"):
        backend._get_auth()


# ---------------------------------------------------------------------------
# Test 5 — structural guard: exactly ONE streamablehttp_client( in source
# ---------------------------------------------------------------------------


def test_exactly_one_streamablehttp_client_call() -> None:
    """agent_brain_mcp.client module source has exactly one streamablehttp_client(
    invocation — all 17 former per-method call sites route through _http_session().

    This is the mechanical guard for Context decision B: one helper, one seam.
    """
    import agent_brain_mcp.client as client_module  # noqa: PLC0415

    source = inspect.getsource(client_module)
    count = source.count("streamablehttp_client(")
    assert count == 1, (
        f"Expected exactly 1 streamablehttp_client( call in agent_brain_mcp.client, "
        f"found {count}.  All call sites must route through _http_session()."
    )
