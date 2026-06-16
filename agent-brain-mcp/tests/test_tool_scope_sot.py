"""Single-source-of-truth tests for the per-tool scope map (OAUTH-06 SC#4).

Verifies:
  1. TOOL_SCOPE_REQUIREMENTS covers every key in TOOL_REGISTRY (completeness).
  2. Every scope value is one of the 4 locked valid scopes.
  3. The exact locked assignment per the design doc (parametrized; pins accidental
     re-scopes, e.g. cancel_job→read would fail here).
  4. The import-time drift guard raises RuntimeError naming a removed tool.
  5. require_scope() round-trip cases including the deny-by-default empty-scopes case.

Design doc: docs/plans/2026-06-14-mcp-v4-oauth-design.md §"Scope-to-Tool Mapping"
"""

from __future__ import annotations

import pytest

from agent_brain_mcp.oauth.scopes import (
    VALID_SCOPES,
    InsufficientScopeError,
    require_scope,
)
from agent_brain_mcp.tools import TOOL_REGISTRY, TOOL_SCOPE_REQUIREMENTS

# ---------------------------------------------------------------------------
# 1. Completeness: every registry tool has a scope; no phantom entries
# ---------------------------------------------------------------------------


def test_scope_map_covers_all_registry_tools() -> None:
    """set(TOOL_SCOPE_REQUIREMENTS) == set(TOOL_REGISTRY)."""
    missing = sorted(set(TOOL_REGISTRY) - set(TOOL_SCOPE_REQUIREMENTS))
    extra = sorted(set(TOOL_SCOPE_REQUIREMENTS) - set(TOOL_REGISTRY))
    assert set(TOOL_SCOPE_REQUIREMENTS.keys()) == set(TOOL_REGISTRY.keys()), (
        f"Scope map diverges from registry.\n"
        f"  missing from scope map: {missing}\n"
        f"  extra in scope map:     {extra}"
    )


def test_scope_map_has_exactly_16_entries() -> None:
    """There are exactly 16 registered tools."""
    assert len(TOOL_SCOPE_REQUIREMENTS) == 16, (
        f"Expected 16 scope entries, got {len(TOOL_SCOPE_REQUIREMENTS)}: "
        f"{sorted(TOOL_SCOPE_REQUIREMENTS)}"
    )


# ---------------------------------------------------------------------------
# 2. Valid-scope values: every value is one of the 4 locked scopes
# ---------------------------------------------------------------------------


def test_every_scope_value_is_valid() -> None:
    """Every value in TOOL_SCOPE_REQUIREMENTS must be in VALID_SCOPES."""
    invalid = {
        name: scope
        for name, scope in TOOL_SCOPE_REQUIREMENTS.items()
        if scope not in VALID_SCOPES
    }
    assert not invalid, f"Tools with invalid scope values: {invalid}"


def test_valid_scopes_frozenset() -> None:
    """VALID_SCOPES contains exactly the 4 locked scope strings."""
    assert VALID_SCOPES == frozenset(
        {
            "agent-brain:read",
            "agent-brain:index",
            "agent-brain:admin",
            "agent-brain:subscribe",
        }
    )


# ---------------------------------------------------------------------------
# 3. Locked assignment (parametrized — pins the design-doc table exactly)
# ---------------------------------------------------------------------------


_LOCKED_ASSIGNMENTS: list[tuple[str, str]] = [
    # agent-brain:read — read-only tools
    ("search_documents", "agent-brain:read"),
    ("explain_result", "agent-brain:read"),
    ("server_health", "agent-brain:read"),
    ("query_count", "agent-brain:read"),
    ("cache_status", "agent-brain:read"),
    ("list_folders", "agent-brain:read"),
    ("list_file_types", "agent-brain:read"),
    ("list_jobs", "agent-brain:read"),
    ("get_job", "agent-brain:read"),
    # agent-brain:index — index/mutation tools
    ("index_folder", "agent-brain:index"),
    ("add_documents", "agent-brain:index"),
    ("inject_documents", "agent-brain:index"),
    ("wait_for_job", "agent-brain:index"),
    # agent-brain:admin — destructive/admin tools
    ("cancel_job", "agent-brain:admin"),
    ("remove_folder", "agent-brain:admin"),
    ("clear_cache", "agent-brain:admin"),
]


@pytest.mark.parametrize("tool_name,expected_scope", _LOCKED_ASSIGNMENTS)
def test_locked_scope_assignment(tool_name: str, expected_scope: str) -> None:
    """Each tool is assigned exactly the scope the design doc mandates."""
    actual = TOOL_SCOPE_REQUIREMENTS.get(tool_name)
    assert actual == expected_scope, (
        f"Tool '{tool_name}': expected scope '{expected_scope}', got '{actual}'. "
        f"The scope assignment is LOCKED — re-scoping requires a design-doc update."
    )


# ---------------------------------------------------------------------------
# 4. Import-time drift guard raises RuntimeError naming a removed tool
# ---------------------------------------------------------------------------


def test_drift_guard_raises_on_missing_tool() -> None:
    """_scope_drift() names a tool removed from TOOL_SCOPE_REQUIREMENTS."""
    from agent_brain_mcp.tools import _scope_drift  # type: ignore[attr-defined]

    # Build a doctored scope map with 'clear_cache' removed.
    doctored = dict(TOOL_SCOPE_REQUIREMENTS)
    doctored.pop("clear_cache")

    unassigned, unknown, bad_values = _scope_drift(
        set(TOOL_REGISTRY.keys()), set(doctored.keys()), doctored, VALID_SCOPES
    )
    assert (
        "clear_cache" in unassigned
    ), f"Expected 'clear_cache' in unassigned; got {unassigned}"


def test_drift_guard_raises_runtime_error_on_missing_tool() -> None:
    """_assert_every_tool_has_scope raises RuntimeError naming the unassigned tool."""
    import agent_brain_mcp.tools as tools_mod
    from agent_brain_mcp.tools import (
        _assert_every_tool_has_scope,  # type: ignore[attr-defined]
    )

    # Temporarily remove 'clear_cache' from the module's scope map.
    original = dict(tools_mod.TOOL_SCOPE_REQUIREMENTS)
    doctored = dict(original)
    doctored.pop("clear_cache")
    tools_mod.TOOL_SCOPE_REQUIREMENTS = doctored  # type: ignore[assignment]

    try:
        with pytest.raises(RuntimeError, match="clear_cache"):
            _assert_every_tool_has_scope()
    finally:
        tools_mod.TOOL_SCOPE_REQUIREMENTS = original  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# 5. require_scope round-trip (including deny-by-default empty-scopes)
# ---------------------------------------------------------------------------


def test_require_scope_passes_when_present() -> None:
    """require_scope returns None when the required scope is in the token."""
    result = require_scope("agent-brain:read", ["agent-brain:read"])
    assert result is None


def test_require_scope_passes_with_multiple_scopes() -> None:
    """require_scope passes when required scope is among several granted scopes."""
    result = require_scope(
        "agent-brain:read", ["agent-brain:read", "agent-brain:index"]
    )
    assert result is None


def test_require_scope_raises_when_absent() -> None:
    """require_scope raises InsufficientScopeError when scope is not granted."""
    with pytest.raises(InsufficientScopeError) as exc_info:
        require_scope("agent-brain:admin", ["agent-brain:read"])
    assert exc_info.value.required == "agent-brain:admin"


def test_require_scope_required_attribute() -> None:
    """InsufficientScopeError.required names the REQUIRED scope (not the token's)."""
    with pytest.raises(InsufficientScopeError) as exc_info:
        require_scope("agent-brain:admin", ["agent-brain:read", "agent-brain:index"])
    assert exc_info.value.required == "agent-brain:admin"


def test_require_scope_empty_granted_scopes_raises() -> None:
    """require_scope raises InsufficientScopeError when granted scopes is empty.

    This is the deny-by-default case: a token with no scopes must be rejected
    for every tool — including the cheapest read.  Plan 02's pre-dispatch guard
    relies on this to close the window where an unscoped token could slip through.
    """
    with pytest.raises(InsufficientScopeError) as exc_info:
        require_scope("agent-brain:index", [])
    assert exc_info.value.required == "agent-brain:index"


def test_insufficient_scope_error_carries_required_scope() -> None:
    """InsufficientScopeError stores the required scope on the .required attribute."""
    exc = InsufficientScopeError("agent-brain:admin")
    assert exc.required == "agent-brain:admin"


def test_insufficient_scope_error_message_names_required_scope() -> None:
    """Exception message must reference the required scope for diagnostic clarity."""
    exc = InsufficientScopeError("agent-brain:index")
    assert "agent-brain:index" in str(exc)


def test_insufficient_scope_error_token_scopes_default_empty() -> None:
    """token_scopes defaults to an empty list when not supplied."""
    exc = InsufficientScopeError("agent-brain:read")
    assert exc.token_scopes == []


def test_insufficient_scope_error_token_scopes_stored() -> None:
    """token_scopes is stored when supplied."""
    exc = InsufficientScopeError("agent-brain:admin", token_scopes=["agent-brain:read"])
    assert exc.token_scopes == ["agent-brain:read"]
