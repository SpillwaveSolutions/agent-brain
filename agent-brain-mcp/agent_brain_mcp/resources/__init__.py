"""Resource registry — static ``corpus://*`` URIs + parameterized schemes.

The ``corpus`` module owns the 5 read-only static resources (plan §6.5).
The ``parameterized`` module owns the 4 parameterized schemes added in
Phase 51 (``chunk://``, ``graph-entity://``, ``job://``, ``file://``).

Both registries are surfaced here so :mod:`agent_brain_mcp.server` only
imports from this package, not from the per-scheme submodules.
"""

from .corpus import RESOURCE_REGISTRY, ResourceSpec
from .parameterized import (
    PARAMETERIZED_HANDLERS,
    PARAMETERIZED_SCHEMES,
    ParameterizedHandler,
    ParsedURI,
    parse_uri,
)

__all__ = [
    "PARAMETERIZED_HANDLERS",
    "PARAMETERIZED_SCHEMES",
    "ParameterizedHandler",
    "ParsedURI",
    "RESOURCE_REGISTRY",
    "ResourceSpec",
    "parse_uri",
]
