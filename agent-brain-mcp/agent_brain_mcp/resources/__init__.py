"""Resource registry — 5 read-only ``corpus://`` URIs (plan §6.5).

Each entry maps a URI to a (name, description, handler) triple. The
handler takes an :class:`agent_brain_mcp.client.ApiClient` and returns
a JSON-serializable dict.
"""

from .corpus import RESOURCE_REGISTRY, ResourceSpec

__all__ = ["RESOURCE_REGISTRY", "ResourceSpec"]
