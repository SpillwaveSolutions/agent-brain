"""Phase 4 test: server refuses to start below version floor (plan §12.3 #14)."""

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
            ("10.0.7-beta", (10, 0, 7)),
            ("10.0", (10, 0)),
            ("10", (10,)),
            ("", ()),
        ],
    )
    def test_parse_version(self, version: str, expected: tuple) -> None:
        assert _parse_version(version) == expected


class TestVersionCompatCheck:
    def test_accepts_exact_minimum(self) -> None:
        # MUST NOT raise.
        check_backend_version(MIN_BACKEND_VERSION)

    def test_accepts_higher_version(self) -> None:
        check_backend_version("10.1.0")
        check_backend_version("11.0.0")

    def test_rejects_lower_patch(self) -> None:
        with pytest.raises(McpError) as ei:
            check_backend_version("10.0.6")
        assert ei.value.error.code == INVALID_PARAMS
        assert "10.0.6" in ei.value.error.message

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
