"""HTTP-to-MCP error mapping.

Plan §6.3 — Agent Brain HTTP responses are translated into MCP JSON-RPC
error codes when surfaced through MCP tool calls. Tools call
:func:`raise_for_status` after each HTTP request; the wrapper raises an
:class:`McpError` whose ``code`` matches the plan's mapping table.

Standard JSON-RPC error codes (per spec):
    -32700 ParseError, -32600 InvalidRequest, -32601 MethodNotFound,
    -32602 InvalidParams, -32603 InternalError

Custom Agent Brain codes (in the application-defined range):
    -32000 InvalidRequest (HTTP 409 Conflict)
    -32001 BackendUnavailable (HTTP 502)
    -32002 ServiceIndexing (HTTP 503 — server is in mid-index)
    -32003 BackendTimeout (HTTP 504)
"""

from __future__ import annotations

from typing import Any

import httpx
from mcp import McpError
from mcp.types import ErrorData

# Standard JSON-RPC codes
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

# Agent Brain custom application codes (plan §6.3)
INVALID_REQUEST = -32000
BACKEND_UNAVAILABLE = -32001
SERVICE_INDEXING = -32002
BACKEND_TIMEOUT = -32003


def _extract_detail(response: httpx.Response) -> str:
    """Pull a useful detail string out of a server error body."""
    try:
        data = response.json()
        if isinstance(data, dict):
            detail = data.get("detail")
            if isinstance(detail, str):
                return detail
            if isinstance(detail, list | dict):
                return str(detail)
            return str(data)
        return str(data)
    except Exception:
        return response.text or "(empty body)"


def raise_for_status(
    response: httpx.Response, *, request_id: str | None = None
) -> None:
    """Map a non-success HTTP response to an MCP error and raise.

    Args:
        response: An ``httpx.Response`` already checked at the call site.
        request_id: Optional request correlation ID to embed in
            ``data.requestId`` for 500-class errors.
    """
    if response.status_code < 400:
        return

    detail = _extract_detail(response)
    data: dict[str, Any] = {
        "httpStatus": response.status_code,
        "cause": detail,
    }
    if request_id is not None:
        data["requestId"] = request_id

    status = response.status_code

    if status in (400, 404, 422):
        code = INVALID_PARAMS
        message = f"Invalid parameters (HTTP {status}): {detail}"
    elif status == 409:
        code = INVALID_REQUEST
        message = f"Conflict (HTTP 409): {detail}"
    elif status == 502:
        code = BACKEND_UNAVAILABLE
        message = f"Backend unavailable (HTTP 502): {detail}"
    elif status == 503:
        code = SERVICE_INDEXING
        message = f"Service indexing (HTTP 503): {detail}"
    elif status == 504:
        code = BACKEND_TIMEOUT
        message = f"Backend timeout (HTTP 504): {detail}"
    elif status >= 500:
        code = INTERNAL_ERROR
        message = f"Internal server error (HTTP {status}): {detail}"
    else:
        # 4xx not in the explicit table — surface as InvalidParams.
        code = INVALID_PARAMS
        message = f"Client error (HTTP {status}): {detail}"

    raise McpError(ErrorData(code=code, message=message, data=data))


def raise_backend_unavailable(cause: Exception) -> None:
    """Raise BackendUnavailable for transport-layer failures (UDS gone,
    HTTP unreachable, connection refused)."""
    raise McpError(
        ErrorData(
            code=BACKEND_UNAVAILABLE,
            message=f"Backend unavailable: {cause}",
            data={"cause": str(cause)},
        )
    )


def raise_backend_timeout(cause: Exception) -> None:
    """Raise BackendTimeout for httpx-level timeouts."""
    raise McpError(
        ErrorData(
            code=BACKEND_TIMEOUT,
            message=f"Backend timeout: {cause}",
            data={"cause": str(cause)},
        )
    )
