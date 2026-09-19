"""Helpers for surfacing MCP errors through asyncio TaskGroup wrappers.

Issue #254: anyio / the MCP SDK wraps server-side errors in an
``ExceptionGroup`` (``unhandled errors in a TaskGroup (1 sub-exception)``),
so the CLI printed the wrapper instead of the real message (missing
prompt argument, invalid entity type, etc.).
"""

from __future__ import annotations


def unwrap_exception(exc: BaseException) -> BaseException:
    """Return the innermost exception, unwrapping ExceptionGroup wrappers.

    Prefers ``mcp.McpError`` when a group contains one. Walks ``__cause__``
    after unwrapping groups. Safe on Python 3.10 (no builtin
    ``ExceptionGroup``) by inspecting the ``exceptions`` attribute.
    """
    seen: set[int] = set()
    current: BaseException = exc
    while id(current) not in seen:
        seen.add(id(current))
        grouped = _group_exceptions(current)
        if grouped:
            preferred = _prefer_mcp_error(grouped)
            current = preferred if preferred is not None else grouped[0]
            continue
        if current.__cause__ is not None:
            current = current.__cause__
            continue
        break
    return current


def format_exception_message(exc: BaseException) -> str:
    """Human-readable message for a (possibly grouped) exception."""
    inner = unwrap_exception(exc)
    message = str(inner).strip() or inner.__class__.__name__
    return message


def _group_exceptions(exc: BaseException) -> tuple[BaseException, ...] | None:
    exceptions = getattr(exc, "exceptions", None)
    if not isinstance(exceptions, (list, tuple)) or not exceptions:
        return None
    if not all(isinstance(item, BaseException) for item in exceptions):
        return None
    # Builtin ExceptionGroup/BaseExceptionGroup, or anyio's TaskGroup wrapper.
    name = type(exc).__name__
    if name in {"ExceptionGroup", "BaseExceptionGroup"} or "TaskGroup" in name:
        return tuple(exceptions)
    # anyio 4 / Python 3.11 ExceptionGroup subclass names vary; accept
    # anything that *looks* like a group and whose str mentions TaskGroup.
    if "TaskGroup" in str(exc) or "unhandled errors" in str(exc).lower():
        return tuple(exceptions)
    return None


def _prefer_mcp_error(exceptions: tuple[BaseException, ...]) -> BaseException | None:
    try:
        from mcp import McpError
    except ImportError:  # pragma: no cover — mcp is a hard CLI dep
        return None
    for item in exceptions:
        if isinstance(item, McpError):
            return item
        nested = _group_exceptions(item)
        if nested:
            found = _prefer_mcp_error(nested)
            if found is not None:
                return found
    return None


def is_mcp_error(exc: BaseException) -> bool:
    """True if ``exc`` (possibly wrapped) is an MCP protocol error."""
    try:
        from mcp import McpError
    except ImportError:  # pragma: no cover
        return False
    inner = unwrap_exception(exc)
    return isinstance(inner, McpError) or isinstance(exc, McpError)
