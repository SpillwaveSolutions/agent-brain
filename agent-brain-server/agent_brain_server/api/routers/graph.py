"""Graph entity endpoint — ``GET /graph/entity/{entity_type}/{entity_id}``.

Backs the MCP ``graph-entity://<type>/<id>`` resource scheme (URI-02 in
Phase 51). Wire shape locked by Phase 50 design doc §2.4:

    {
      "entity":    { "type": str, "id": str, "properties": {...} },
      "neighbors": {
        "incoming": [
          {"type": str, "id": str, "predicate": str, "properties": {...}},
          ...
        ],
        "outgoing": [{ ... }]
      }
    }

Status codes (decision B in 50-CONTEXT.md):

- ``200 GraphEntityRecord`` — entity exists; 1-hop neighbors attached.
- ``503 graphrag_disabled`` — GraphRAG is not enabled in config. Distinct
  from 404 because it's a config-state error, not a data-state error.
- ``503 kuzu_unavailable`` — Kuzu raised a corruption signature
  (issue #178); the server keeps running but graph lookup is offline
  until the operator switches to ``graphrag.store_type: simple`` or the
  Kuzu issue is fixed.
- ``400 invalid_entity_type`` — ``entity_type`` is not one of the 17
  SCHEMA-01 types. Response body includes the canonical ``valid_types``
  list so callers can discover the vocabulary at runtime.
- ``404 entity_not_found`` — type is valid but no entity with that
  ``(type, id)`` exists in the graph.

The valid type vocabulary is sourced from ``ENTITY_TYPES`` in
``agent_brain_server.models.graph`` — the same Literal that the
extraction pipeline validates against. Plan 03 deliberately does NOT
keep a parallel list (SCHEMA-01 vocabulary drift risk noted in the plan).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status

from agent_brain_server.api.security import verify_bearer_token
from agent_brain_server.config.provider_config import load_provider_settings
from agent_brain_server.config.settings import settings
from agent_brain_server.models import ENTITY_TYPES, GraphEntityRecord
from agent_brain_server.storage.graph_store import (
    KuzuUnavailableError,
    get_graph_store_manager,
)

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(verify_bearer_token)])


# Frozen at module import for predictable 400-body content. The 17 SCHEMA-01
# entity types are stable for the v2 milestone; new types added in future
# milestones will flip ``ENTITY_TYPES`` and this set together.
_VALID_ENTITY_TYPES: frozenset[str] = frozenset(ENTITY_TYPES)


def _graphrag_enabled() -> bool:
    """Return True when GraphRAG is enabled, per YAML or env-var.

    Mirrors ``agent_brain_server.storage.graph_store._graphrag_enabled`` so
    the router's 503 trigger matches the same source of truth the rest of
    the codebase uses (YAML wins when set; otherwise the env-var-backed
    ``settings.ENABLE_GRAPH_INDEX`` applies).
    """
    try:
        yaml_value = load_provider_settings().graphrag.enabled
    except Exception:
        yaml_value = None
    if yaml_value is not None:
        return bool(yaml_value)
    return bool(settings.ENABLE_GRAPH_INDEX)


@router.get(
    "/entity/{entity_type}/{entity_id}",
    response_model=GraphEntityRecord,
    summary="Get graph entity by type and id",
    description=(
        "Fetch an entity from the knowledge graph by ``(type, id)`` along "
        "with its 1-hop incoming and outgoing neighbors. Returns 503 when "
        "GraphRAG is disabled, 400 on an unknown entity type, and 404 when "
        "the type is valid but no matching entity exists."
    ),
    responses={
        200: {"description": "Entity record with 1-hop neighbors."},
        400: {
            "description": (
                "Unknown entity type — response body lists the valid " "vocabulary."
            )
        },
        404: {"description": "No entity with this (type, id) in the graph."},
        503: {
            "description": (
                "GraphRAG disabled, or Kuzu backend reported a corruption "
                "signature (#178). The server keeps running; switch "
                "graphrag.store_type to simple to work around."
            )
        },
    },
)
async def get_graph_entity(
    entity_type: str,
    entity_id: str,
    request: Request,
) -> GraphEntityRecord:
    """Look up an entity in the knowledge graph by type and id.

    See module docstring for status-code semantics.
    """
    # 503: GraphRAG not enabled (decision B in 50-CONTEXT.md). Distinct
    # from 404 — operator hasn't turned graph addressing on.
    if not _graphrag_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "graphrag_disabled",
                "hint": (
                    "set graphrag.enabled = true in config to enable "
                    "graph-entity addressing"
                ),
            },
        )

    # 400: unknown entity type. We do this BEFORE touching the graph store
    # so a bogus type doesn't load the graph manager.
    if entity_type not in _VALID_ENTITY_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_entity_type",
                "type": entity_type,
                "valid_types": sorted(_VALID_ENTITY_TYPES),
            },
        )

    graph_mgr = get_graph_store_manager()
    # Lazy-initialize: in production the lifespan preflight runs for Kuzu,
    # but simple-store deployments may not have initialized before the
    # first /graph/entity request. Initialize on demand.
    if not graph_mgr.is_initialized:
        try:
            graph_mgr.initialize()
        except KuzuUnavailableError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error": "kuzu_unavailable",
                    "hint": (
                        "Kuzu graph store is unhealthy (issue #178). "
                        "Set graphrag.store_type=simple in config until "
                        "the Kuzu fix lands."
                    ),
                },
            ) from exc
        except Exception as exc:
            # Defensive: any other init failure leaves the endpoint
            # unable to serve, so surface as 503 rather than 500.
            logger.warning("graph_entity: graph store initialization failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error": "graphrag_disabled",
                    "hint": (
                        "graph store could not be initialized; check " "server logs"
                    ),
                },
            ) from exc

    try:
        record = graph_mgr.get_entity_by_id(entity_type, entity_id)
    except KuzuUnavailableError as exc:
        # 503 with a distinct error code so MCP clients (and operators
        # tailing logs) can distinguish "graphrag was turned off" from
        # "the Kuzu binary corrupted itself mid-write" — different
        # operator response in each case.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "kuzu_unavailable",
                "hint": (
                    "Kuzu graph store raised during lookup (issue #178). "
                    "Set graphrag.store_type=simple in config until the "
                    "Kuzu fix lands."
                ),
            },
        ) from exc

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "entity_not_found",
                "type": entity_type,
                "id": entity_id,
            },
        )
    return record
