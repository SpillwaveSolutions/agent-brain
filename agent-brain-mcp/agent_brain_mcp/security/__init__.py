"""Re-export shim for the file_sandbox helpers — Phase 51 Plan 03.

THIS MODULE MUST NOT CONTAIN LOGIC. It is a thin re-export of the
Phase 50 deliverable :mod:`agent_brain_server.security.file_sandbox`,
which is the *single source of truth* for the ``file://`` MCP resource
path-policy decision (CONTEXT.md decision E, "SHARE, do not fork").

Forking the sandbox logic into ``agent_brain_mcp`` would create silent
policy drift between server-side ``file://`` reads (none today, but
plausible in v3+) and MCP-side ``file://`` reads (this phase). Any
new sandbox rule, new deny reason, or new size cap MUST be added to
the server module, never duplicated here.

Re-exported names
-----------------

- :data:`DEFAULT_MAX_READ_BYTES` — per-file read cap (10 MiB default).
- :func:`canonicalize_path` — resolve symlinks + collapse ``..``.
- :func:`is_path_allowed` — core policy decision; returns
  ``(allowed, deny_reason)``.
- :func:`list_sandbox_roots` — MCP ``roots/list`` rendering helper.

The Phase 50 module returns four deny-reason string literals:

- ``outside_indexed_roots`` — canonical path is outside every root.
- ``hidden_file`` — outside every root AND a dot-prefixed component.
- ``symlink_escape`` — literal path is a symlink that resolves outside
  every root.
- ``size_limit`` — file exceeds ``max_bytes`` (10 MiB default).

Plan 51-03's ``handle_file_uri`` re-emits these strings verbatim via
``McpError(INVALID_PARAMS, data={"reason": <deny_reason>})`` so MCP
clients can route on them without re-parsing.

Re-export contract: the import below is the ONLY thing this module
does. If a future plan needs to add ``agent_brain_mcp``-side logic
around the sandbox (e.g., a TTL cache on the roots list), put it in a
sibling module — keep this file a pure pass-through.
"""

from __future__ import annotations

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
