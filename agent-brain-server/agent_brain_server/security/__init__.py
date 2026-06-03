"""Security primitives for agent-brain-server.

Currently contains the file sandbox module that backs the MCP ``file://``
resource scheme. Phase 51 will import these helpers when wiring the MCP
``resources/read`` handler — the module itself is server-internal and adds
no HTTP routes in Phase 50.

Source of truth for the sandbox policy lives in
``docs/plans/2026-06-02-mcp-v2-subscriptions.md`` §2.5 ("Locked
``roots/list`` sandbox policy") and ``.planning/phases/50-server-endpoint-
prep-v2-design-doc/50-CONTEXT.md`` decision A.
"""

from agent_brain_server.security.file_sandbox import (
    DEFAULT_MAX_READ_BYTES,
    canonicalize_path,
    is_path_allowed,
    list_sandbox_roots,
)

__all__ = [
    "DEFAULT_MAX_READ_BYTES",
    "canonicalize_path",
    "is_path_allowed",
    "list_sandbox_roots",
]
