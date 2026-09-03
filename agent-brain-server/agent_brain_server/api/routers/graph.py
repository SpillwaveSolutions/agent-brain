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
- ``400 invalid_entity_type`` — ``entity_type`` is not a SCHEMA-01 type
  and is not a namespaced ``prefix:Name`` (e.g. ``okf:Claim``). Response
  body includes the canonical ``valid_types`` list (SCHEMA-01) so callers
  can discover the built-in vocabulary; namespaced types are accepted in
  addition to that list (#235).
- ``404 entity_not_found`` — type is valid but no entity with that
  ``(type, id)`` exists in the graph.

``POST /graph/project`` and ``DELETE /graph/project`` (#235) accept
pre-typed entities/relations from an external projector. Writes run in
the same out-of-process kuzu isolation as document indexing (#178).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from agent_brain_server.api.security import verify_bearer_token
from agent_brain_server.config.provider_config import load_provider_settings
from agent_brain_server.config.settings import settings
from agent_brain_server.models import (
    ENTITY_TYPES,
    GraphEntityRecord,
    GraphProjectRequest,
    GraphProjectResponse,
    is_valid_entity_type,
)
from agent_brain_server.models.graph import SOURCE_TAG_RE
from agent_brain_server.storage.graph_store import (
    KuzuUnavailableError,
    get_graph_store_manager,
)

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(verify_bearer_token)])


# Frozen at module import for predictable 400-body content. The 17 SCHEMA-01
# entity types are the built-in vocabulary; namespaced types (``okf:Claim``)
# are accepted in addition via ``is_valid_entity_type``.
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
    # so a bogus type doesn't load the graph manager. SCHEMA-01 plus
    # namespaced ``prefix:Name`` (#235) are accepted; invented
    # un-namespaced types still 400.
    if not is_valid_entity_type(entity_type):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_entity_type",
                "type": entity_type,
                "valid_types": sorted(_VALID_ENTITY_TYPES),
                "hint": (
                    "Namespaced types (prefix:Name, e.g. okf:Claim) are "
                    "also accepted."
                ),
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


def _graph_disabled_exc() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "error": "graphrag_disabled",
            "hint": (
                "set graphrag.enabled = true in config to enable "
                "graph-entity addressing"
            ),
        },
    )


def _kuzu_unavailable_exc() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "error": "kuzu_unavailable",
            "hint": (
                "Kuzu graph store raised during projection (issue #178). "
                "Set graphrag.store_type=simple in config until the "
                "Kuzu fix lands."
            ),
        },
    )



@router.post(
    "/project",
    response_model=GraphProjectResponse,
    summary="Project pre-typed entities and relations",
    description=(
        "Upsert explicit typed entities and relations into the property "
        "graph with no LLM/AST extraction. Writes run in an out-of-process "
        "spawn worker so a kuzu-native crash cannot take down the server "
        "(#178). Pass ``replace=true`` to delete prior facts with the same "
        "``source_tag`` first (deterministic rebuild)."
    ),
    responses={
        200: {"description": "Projection applied; counts returned."},
        400: {"description": "Invalid type, predicate, or relation endpoint."},
        503: {
            "description": (
                "GraphRAG disabled, or isolated kuzu worker crashed (#178)."
            )
        },
    },
)
async def project_graph(body: GraphProjectRequest) -> GraphProjectResponse:
    """Accept pre-typed facts from an external projector (#235)."""
    if not _graphrag_enabled():
        raise _graph_disabled_exc()

    payload_ids = {entity.id for entity in body.entities}
    missing: list[str] = []
    for rel in body.relations:
        if rel.src not in payload_ids:
            missing.append(rel.src)
        if rel.dst not in payload_ids:
            missing.append(rel.dst)
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "unknown_relation_endpoint",
                "missing_ids": sorted(set(missing)),
                "hint": (
                    "Every relation src/dst must match an entity id in "
                    "the same request."
                ),
            },
        )

    entities = [
        {
            "type": entity.type,
            "id": entity.id,
            "properties": dict(entity.properties),
        }
        for entity in body.entities
    ]
    relations = [
        {"src": rel.src, "predicate": rel.predicate, "dst": rel.dst}
        for rel in body.relations
    ]

    try:
        from agent_brain_server.indexing.graph_index import project_isolated
        from agent_brain_server.storage.graph_errors import GraphBuildFailedError

        counts = project_isolated(
            entities,
            relations,
            body.source_tag,
            replace=body.replace,
        )
    except (GraphBuildFailedError, KuzuUnavailableError) as exc:
        raise _kuzu_unavailable_exc() from exc


    return GraphProjectResponse(
        entities_upserted=int(counts.get("entities_upserted", 0)),
        relations_upserted=int(counts.get("relations_upserted", 0)),
        entities_deleted=int(counts.get("entities_deleted", 0)),
        relations_deleted=int(counts.get("relations_deleted", 0)),
        source_tag=body.source_tag,
    )


@router.delete(
    "/project",
    response_model=GraphProjectResponse,
    summary="Delete projected facts by source_tag",
    description=(
        "Remove every node (and incident edge) stamped with ``source_tag``. "
        "Runs in the same isolated worker as ``POST /graph/project``."
    ),
    responses={
        200: {"description": "Tagged facts removed; counts returned."},
        400: {"description": "Missing or invalid source_tag."},
        503: {"description": "GraphRAG disabled, or isolated worker crashed."},
    },
)
async def delete_projected_graph(
    source_tag: str = Query(..., min_length=1, max_length=64),
) -> GraphProjectResponse:
    """Delete-by-source_tag for a deterministic projector rebuild (#235)."""
    if not _graphrag_enabled():
        raise _graph_disabled_exc()

    if SOURCE_TAG_RE.fullmatch(source_tag) is None:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_source_tag",
                "source_tag": source_tag,
            },
        )

    try:
        from agent_brain_server.indexing.graph_index import project_isolated
        from agent_brain_server.storage.graph_errors import GraphBuildFailedError

        counts = project_isolated(
            [],
            [],
            source_tag,
            replace=True,
        )
    except (GraphBuildFailedError, KuzuUnavailableError) as exc:
        raise _kuzu_unavailable_exc() from exc


    return GraphProjectResponse(
        entities_upserted=0,
        relations_upserted=0,
        entities_deleted=int(counts.get("entities_deleted", 0)),
        relations_deleted=int(counts.get("relations_deleted", 0)),
        source_tag=source_tag,
    )

