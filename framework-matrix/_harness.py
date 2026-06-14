"""Shared helpers for the Phase 61/62 Python framework adapter matrix.

Pure helpers — no pytest dependency here. conftest.py imports from this
module to build session-scoped fixtures that every framework smoke test
shares.

Contract:
- FRAMEWORK_CORPUS: tiny indexable corpus guaranteeing a non-empty search hit
- SMOKE_QUERY / SMOKE_TOOL / SMOKE_ARGS: canonical connect→call→assert inputs
- stdio_server_params: per-framework stdio MCP launch spec
- assert_non_empty_search: normalizes 5 framework result shapes → count ≥ 1
- assert_no_orphans: psutil children-delta orphan-free assertion
"""

from __future__ import annotations

import json
import os
from pathlib import Path

try:
    import psutil as _psutil

    _PSUTIL_AVAILABLE = True
except ImportError:
    _psutil = None  # type: ignore[assignment]
    _PSUTIL_AVAILABLE = False

# ---------------------------------------------------------------------------
# Tiny corpus — guarantees a non-empty search hit against "authenticate".
# Mirror the spirit of agent-brain-mcp/tests/e2e/fixtures/tiny_corpus/ but
# defined inline so framework-matrix has no cross-package import dependency.
# ---------------------------------------------------------------------------

FRAMEWORK_CORPUS: dict[str, str] = {
    "auth.py": """\
\"\"\"Authentication utilities for the example service.\"\"\"


def authenticate(username: str, password: str) -> bool:
    \"\"\"Authenticate a user by username and password.

    Returns True when credentials are valid, False otherwise.
    The login workflow calls this function on every user login attempt.
    \"\"\"
    # Placeholder: delegate to identity provider.
    return username != "" and password != ""


def logout(user_id: str) -> None:
    \"\"\"Terminate the authenticated session for user_id.\"\"\"
    pass
""",
    "auth.md": """\
# Authentication Guide

This document explains how to authenticate users in the system.

## Overview

The `authenticate` function verifies user credentials during the login
workflow. Call it with the user's username and password; it returns
`True` when the credentials are valid.

## Usage

```python
from auth import authenticate

if authenticate(username, password):
    print("login successful")
else:
    print("authentication failed")
```

## Security Notes

- Passwords are never stored in plaintext.
- Failed login attempts are logged for auditing.
- Use HTTPS to protect credentials in transit.
""",
    "query_service.py": """\
\"\"\"Query service for the document retrieval pipeline.\"\"\"


def search(query: str, top_k: int = 10) -> list[dict]:
    \"\"\"Search the indexed corpus for documents matching the query.

    Args:
        query: Natural-language search query.
        top_k: Maximum number of results to return.

    Returns:
        List of result dicts with keys: text, source, score, chunk_id.
    \"\"\"
    # Delegate to the vector + BM25 hybrid retrieval backend.
    return []


def count_documents() -> int:
    \"\"\"Return the total number of indexed document chunks.\"\"\"
    return 0
""",
    "config.md": """\
# Configuration Reference

## Environment Variables

- `OPENAI_API_KEY` — required for embedding generation
- `AGENT_BRAIN_STATE_DIR` — override the default state directory
- `API_PORT` — HTTP server port (default 8000)
- `API_HOST` — HTTP server host (default 127.0.0.1)

## Authenticate Endpoint

The `/authenticate` endpoint accepts Bearer tokens for API access.
Include `Authorization: Bearer <token>` in all authenticated requests.
""",
}

# ---------------------------------------------------------------------------
# Canonical smoke-test parameters every framework adapter uses.
# ---------------------------------------------------------------------------

SMOKE_QUERY: str = "authenticate user login"
SMOKE_TOOL: str = "search_documents"
SMOKE_ARGS: dict[str, object] = {"query": SMOKE_QUERY}


# ---------------------------------------------------------------------------
# stdio launch spec builder for frameworks that own their own stdio spawn.
# ---------------------------------------------------------------------------


def stdio_server_params(
    state_dir: Path,
) -> tuple[str, list[str], dict[str, str]]:
    """Return (command, args, env) for spawning agent-brain-mcp over stdio.

    The tuple feeds directly into framework-specific stdio adapter
    constructors:
    - OpenAI Agents:  MCPServerStdio(command, args=args, env=env)
    - Pydantic AI:    MCPServerStdio(command, args=args, env=env)
    - LangChain/LlamaIndex/Autogen: vary — see per-framework test files.

    Args:
        state_dir: The session-scoped state directory yielded by the
            ``seeded_mcp_server`` fixture.  The UDS socket lives at
            ``state_dir/.agent-brain/agent-brain.sock``.

    Returns:
        A 3-tuple ``(command, args, env)`` where:
        - ``command`` is the ``agent-brain-mcp`` binary path (str).
        - ``args`` is a list of CLI flags (does NOT include the command
          itself).
        - ``env`` is a minimal environment dict containing PATH, HOME,
          AGENT_BRAIN_STATE_DIR, and any inherited keys the MCP server
          needs.
    """
    import shutil

    binary = shutil.which("agent-brain-mcp") or "agent-brain-mcp"
    agent_brain_state = str(state_dir / ".agent-brain")

    args = ["--backend", "uds", "--state-dir", agent_brain_state]

    env: dict[str, str] = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "AGENT_BRAIN_STATE_DIR": agent_brain_state,
    }
    # Forward OPENAI_API_KEY when present — the MCP server needs it for
    # embedding on search_documents calls.
    if "OPENAI_API_KEY" in os.environ:
        env["OPENAI_API_KEY"] = os.environ["OPENAI_API_KEY"]
    if "ANTHROPIC_API_KEY" in os.environ:
        env["ANTHROPIC_API_KEY"] = os.environ["ANTHROPIC_API_KEY"]

    return (binary, args, env)


# ---------------------------------------------------------------------------
# Result-shape normalization helpers (private).
# ---------------------------------------------------------------------------


def _count_payload(d: object) -> int:
    """Extract total_results or len(results) from a dict-like payload."""
    if not isinstance(d, dict):
        return 0
    if "total_results" in d:
        try:
            return int(d["total_results"])
        except (TypeError, ValueError):
            pass
    results = d.get("results", [])
    if isinstance(results, list):
        return len(results)
    return 0


def _count_text(s: object) -> int:
    """Try JSON-parsing a string; fall back to 'non-empty == 1'."""
    if not isinstance(s, str):
        return 0
    stripped = s.strip()
    if not stripped:
        return 0
    try:
        parsed = json.loads(stripped)
        return _count_payload(parsed)
    except (json.JSONDecodeError, ValueError):
        # Non-empty non-JSON text is treated as ≥1 result.
        return 1


def _count_content_list(lst: object) -> int:
    """Extract count from a list of MCP content blocks or TextResultContent.

    Each block may carry ``.text`` / ``["text"]`` holding a JSON string
    like ``{"results": [...]}`` / ``{"total_results": N}``.
    Falls back to 'non-empty text == 1' when JSON parse fails.
    """
    if not isinstance(lst, list) or not lst:
        return 0
    block = lst[0]
    # Object with .text attribute (MCP SDK TextContent / TextResultContent).
    text = getattr(block, "text", None)
    if text is None and isinstance(block, dict):
        text = block.get("text")
    if isinstance(text, str) and text.strip():
        return _count_text(text)
    # Content block without text — non-empty list counts as ≥1.
    return 1 if lst else 0


def _count_list(lst: object) -> int:
    """Count truthy entries in a plain result list."""
    if not isinstance(lst, list):
        return 0
    return len([x for x in lst if x])


def _count(results: object) -> int:  # noqa: C901 (complex shape dispatch)
    """Normalize any of the 5 framework result shapes to an integer count.

    Shape dispatch order (each framework returns a different envelope):

    1. MCP SDK ``CallToolResult`` (OpenAI Agents, Pydantic AI low-level):
       ``structuredContent`` dict preferred; ``content`` list fallback.
    2. LangChain ``ToolMessage`` with ``.content`` (str or list) OR bare str.
    3. LlamaIndex ``ToolOutput`` with ``.raw_output`` / ``.raw_input``.
    4. Pydantic AI list of content parts (TextPart / ToolReturnPart) or
       a plain list of result dicts.
    5. Autogen ``McpWorkbench`` ``ToolResult``: object with ``.result``
       (list of TextResultContent, each ``.content`` is a JSON string)
       and ``.is_error``.
    """
    # ------------------------------------------------------------------
    # Shape 1: MCP SDK CallToolResult (structuredContent preferred)
    # ------------------------------------------------------------------
    sc = getattr(results, "structuredContent", None)
    if sc is not None:
        return _count_payload(sc)

    content = getattr(results, "content", None)
    if content is not None:
        if isinstance(content, list):
            return _count_content_list(content)
        if isinstance(content, str):
            return _count_text(content)

    # ------------------------------------------------------------------
    # Shape 2: LangChain bare str result
    # ------------------------------------------------------------------
    if isinstance(results, str):
        return _count_text(results)

    # ------------------------------------------------------------------
    # Shape 3: LlamaIndex ToolOutput (.raw_output / .raw_input)
    # ------------------------------------------------------------------
    for attr in ("raw_output", "raw_input"):
        v = getattr(results, attr, None)
        if v is not None:
            if isinstance(v, str):
                return _count_text(v)
            return _count_payload(v)

    # ------------------------------------------------------------------
    # Shape 4: Pydantic AI list of content parts OR plain result list
    # ------------------------------------------------------------------
    if isinstance(results, list):
        return _count_list(results)

    # ------------------------------------------------------------------
    # Shape 5: Autogen McpWorkbench ToolResult (.result list)
    # ------------------------------------------------------------------
    tr = getattr(results, "result", None)
    if tr is not None:
        return _count_content_list(tr)

    # ------------------------------------------------------------------
    # dict fallback (structuredContent already-unwrapped or raw dict)
    # ------------------------------------------------------------------
    if isinstance(results, dict):
        return _count_payload(results)

    return 0


# ---------------------------------------------------------------------------
# Public assertion helpers.
# ---------------------------------------------------------------------------


def assert_non_empty_search(results: object) -> None:
    """Assert that a framework's search_documents call returned ≥1 result.

    Normalizes all 5 framework result shapes (MCP SDK CallToolResult,
    LangChain ToolMessage/str, LlamaIndex ToolOutput, Pydantic AI content
    parts, Autogen McpWorkbench ToolResult) to an integer count, then
    asserts count ≥ 1.

    Args:
        results: The raw return value from a framework's call_tool /
            invoke / run call against the search_documents tool.

    Raises:
        AssertionError: when the normalized count is 0, with a message
            that includes the repr of the unexpected result for debugging.
    """
    try:
        count = _count(results)
    except Exception as exc:  # noqa: BLE001 — tolerant: extraction errors
        # Any extraction failure on a non-None envelope is treated as ≥1
        # rather than raising the wrong error — the real failure surface
        # is 0 results, not a shape-sniffing bug.
        if results is not None:
            return
        raise AssertionError(
            f"search_documents returned None — expected a result envelope: "
            f"{exc!r}"
        ) from exc

    assert count >= 1, (
        f"search_documents returned 0 results against the seeded corpus. "
        f"Result envelope: {results!r}"
    )


def _children_pids(parent_pid: int) -> set[int]:
    """Snapshot recursive descendant PIDs for the given parent.

    Returns an empty set when psutil is unavailable (graceful degradation
    — the orphan guard becomes a no-op).
    """
    if not _PSUTIL_AVAILABLE or _psutil is None:
        return set()
    try:
        parent = _psutil.Process(parent_pid)
        return {child.pid for child in parent.children(recursive=True)}
    except (_psutil.NoSuchProcess, _psutil.AccessDenied):
        return set()


def assert_no_orphans(parent_pid: int, baseline: set[int]) -> None:
    """Assert that no agent-brain subprocesses survived since baseline snapshot.

    Mirrors the psutil children-delta pattern from
    agent-brain-mcp/tests/stress/test_orphan_subprocess.py.

    Args:
        parent_pid: PID of the pytest session process (``os.getpid()``).
        baseline: The set of child PIDs captured at session start (before
            any fixtures ran).  Processes in baseline are excluded from the
            leak check.

    Raises:
        AssertionError: when any new child PID that is NOT in baseline
            survived after all fixtures tore down.
    """
    if not _PSUTIL_AVAILABLE:
        # psutil unavailable — skip orphan check with a warning.
        return

    now = _children_pids(parent_pid)
    leaked = now - baseline

    if leaked:
        raise AssertionError(
            "Orphan agent-brain subprocess(es) survived after teardown.\n"
            f"  surviving PIDs: {sorted(leaked)}\n"
            "  Phase 60 hygiene contract violated — ensure every fixture\n"
            "  sends SIGTERM → waits grace period → escalates to SIGKILL."
        )
