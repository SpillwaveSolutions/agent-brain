"""Test: server refuses to start below version floor (plan §12.3 #14).

Phase 51 Plan 04 bumped the floor from "10.0.7" → "10.2.0" so the MCP
process refuses to start against a server missing the v2 endpoints
(``GET /query/chunk/{id}`` and ``GET /graph/entity/{type}/{id}``).
The new floor cases below pin that bump:

  - 10.1.5 (pre-Phase-50 server) → MCP refuses to start.
  - 10.2.0 (Phase 50 ships these endpoints) → MCP accepts.
  - 10.3.0 (future server above the floor) → MCP accepts.
"""

from __future__ import annotations

import pytest
from mcp import McpError

from agent_brain_mcp.errors import INVALID_PARAMS
from agent_brain_mcp.server import (
    MIN_BACKEND_VERSION,
    _parse_version,
    check_backend_version,
)


class TestVersionParsing:
    @pytest.mark.parametrize(
        "version,expected",
        [
            ("10.0.7", (10, 0, 7)),
            ("10.1.0", (10, 1, 0)),
            ("10.2.0", (10, 2, 0)),
            ("10.0.7-beta", (10, 0, 7)),
            ("10.0", (10, 0)),
            ("10", (10,)),
            ("", ()),
        ],
    )
    def test_parse_version(self, version: str, expected: tuple) -> None:
        assert _parse_version(version) == expected


class TestVersionCompatCheck:
    def test_floor_is_10_2_0(self) -> None:
        """Pin the Phase 51 Plan 04 bump. If this changes, downstream
        Phase 52+ release notes need to acknowledge it explicitly."""
        assert MIN_BACKEND_VERSION == "10.2.0"

    def test_accepts_exact_minimum(self) -> None:
        # MUST NOT raise.
        check_backend_version(MIN_BACKEND_VERSION)

    def test_accepts_10_2_0_explicit(self) -> None:
        """Phase 50 ships GET /query/chunk/{id} + GET /graph/entity/{type}/{id}
        in agent-brain-server 10.2.0 — MCP starts cleanly against it."""
        check_backend_version("10.2.0")

    def test_accepts_higher_minor(self) -> None:
        """A future server above the floor is compatible."""
        check_backend_version("10.3.0")
        check_backend_version("11.0.0")

    def test_rejects_10_1_5_below_floor(self) -> None:
        """A pre-Phase-50 server (10.1.x) is missing /query/chunk/{id}
        and /graph/entity/{type}/{id}. MCP refuses to start so operators
        get a clear upgrade message instead of confusing 404s at read time."""
        with pytest.raises(McpError) as ei:
            check_backend_version("10.1.5")
        assert ei.value.error.code == INVALID_PARAMS
        assert "10.1.5" in ei.value.error.message
        assert ei.value.error.data is not None
        assert ei.value.error.data["minimum"] == "10.2.0"

    def test_rejects_10_2_0_minus_one_patch(self) -> None:
        """Even the closest below-floor version is rejected (no silent
        slop on the floor — release-train coupling per CONTEXT specifics
        #3)."""
        # Strictly below 10.2.0 — 10.1.99 sits right at the boundary.
        with pytest.raises(McpError) as ei:
            check_backend_version("10.1.99")
        assert ei.value.error.code == INVALID_PARAMS

    def test_rejects_lower_minor(self) -> None:
        with pytest.raises(McpError) as ei:
            check_backend_version("9.99.99")
        assert ei.value.error.code == INVALID_PARAMS

    def test_error_data_carries_versions(self) -> None:
        with pytest.raises(McpError) as ei:
            check_backend_version("9.0.0")
        data = ei.value.error.data
        assert data is not None
        assert data["backendVersion"] == "9.0.0"
        assert data["minimum"] == MIN_BACKEND_VERSION
        assert data["minimum"] == "10.2.0"
