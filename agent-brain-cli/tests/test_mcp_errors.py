"""Issue #254: unwrap ExceptionGroup / TaskGroup wrappers for MCP errors."""

from __future__ import annotations

from mcp import McpError
from mcp.types import ErrorData

from agent_brain_cli.mcp_errors import (
    format_exception_message,
    is_mcp_error,
    unwrap_exception,
)


class _FakeTaskGroupError(Exception):
    """Stand-in for ExceptionGroup on Python 3.10 and anyio wrappers."""

    def __init__(self, message: str, exceptions: list[BaseException]) -> None:
        super().__init__(message)
        self.exceptions = exceptions


def test_unwrap_prefers_inner_mcp_error() -> None:
    inner = McpError(
        ErrorData(code=-32602, message="Missing required argument: folder")
    )
    group = _FakeTaskGroupError(
        "unhandled errors in a TaskGroup (1 sub-exception)", [inner]
    )
    assert unwrap_exception(group) is inner
    assert is_mcp_error(group)
    assert "Missing required argument: folder" in format_exception_message(group)
    assert "TaskGroup" not in format_exception_message(group)


def test_unwrap_invalid_entity_type() -> None:
    inner = McpError(ErrorData(code=-32602, message="invalid_entity_type: type=Symbol"))
    group = _FakeTaskGroupError(
        "unhandled errors in a TaskGroup (1 sub-exception)", [inner]
    )
    assert "invalid_entity_type" in format_exception_message(group)
    assert "TaskGroup" not in format_exception_message(group)


def test_unwrap_passthrough_plain_exception() -> None:
    exc = RuntimeError("subprocess died")
    assert unwrap_exception(exc) is exc
    assert format_exception_message(exc) == "subprocess died"
    assert not is_mcp_error(exc)
