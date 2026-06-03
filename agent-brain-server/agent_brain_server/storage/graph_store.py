"""Graph store manager for GraphRAG feature (Feature 113).

Provides abstraction over graph storage backends:
- SimplePropertyGraphStore: In-memory graph with JSON persistence (default)
- Kuzu: High-performance embedded graph database (optional)

All graph operations are no-ops when ENABLE_GRAPH_INDEX is False.
"""

import json
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from agent_brain_server.config import settings
from agent_brain_server.config.provider_config import (
    load_provider_settings,
)
from agent_brain_server.models import (
    GraphEntityRecord,
    GraphEntityRecordNeighbor,
    GraphEntityRecordNeighbors,
    GraphEntityRecordNode,
)
from agent_brain_server.storage.graph_snapshot import (
    GraphSnapshotManager,
    SnapshotTriplet,
)

logger = logging.getLogger(__name__)


class KuzuUnavailableError(RuntimeError):
    """Sentinel raised by the graph store when Kuzu corruption is detected.

    The router translates this to HTTP 503 ``kuzu_unavailable`` so a Kuzu
    SIGSEGV / catalog-corruption event (issue #178) returns a structured
    error to the caller rather than crashing the server process.

    Operator workaround: switch ``graphrag.store_type`` to ``simple`` until
    #178 is fixed. See Phase 50 design doc §2.4 and risk register R1.
    """


def _corrupted_sibling(path: Path, now: datetime | None = None) -> Path:
    """Return a sibling path with a .corrupted-<ts> suffix for renaming."""
    moment = now or datetime.now(timezone.utc)
    stamp = moment.strftime("%Y%m%dT%H%M%SZ")
    return path.with_name(f"{path.name}.corrupted-{stamp}")


def _quarantine_file(path: Path) -> Path | None:
    """Rename a (possibly corrupted) file to a .corrupted-<ts> sibling.

    Returns the quarantined path, or ``None`` if the source did not exist.
    Falls back to ``shutil.move`` if ``Path.rename`` fails (e.g. across
    filesystem boundaries — shouldn't happen for sibling renames but the
    extra robustness costs nothing).
    """
    if not path.exists():
        return None
    dest = _corrupted_sibling(path)
    try:
        path.rename(dest)
    except OSError:
        shutil.move(str(path), str(dest))
    return dest


def _label_of(node: Any) -> str:
    """Return a neighbor node's label, falling back to ``"Entity"``.

    Kuzu's ``get_triplets`` historically returns the literal ``"Entity"`` as
    the ``LabelledNode.label`` and stashes the real schema label inside
    ``node.properties["label"]``. SimplePropertyGraphStore puts it on
    ``node.label`` directly. We try both so neighbor records carry the
    schema type either way.
    """
    label = getattr(node, "label", None)
    if label and label != "Entity":
        return str(label)
    props = getattr(node, "properties", None) or {}
    prop_label = props.get("label") if isinstance(props, dict) else None
    if prop_label:
        return str(prop_label)
    return str(label) if label else "Entity"


def _id_of(node: Any) -> str:
    """Return a neighbor node's id (the entity's ``name`` in current backends)."""
    name = getattr(node, "name", None)
    if name:
        return str(name)
    return str(getattr(node, "id", ""))


def _graphrag_enabled() -> bool:
    """Whether GraphRAG is enabled, merging YAML and env-var config.

    YAML wins when set; otherwise the (env-var-backed) ``settings`` value
    applies. Reading ``settings`` here at call time keeps tests that
    ``@patch("agent_brain_server.storage.graph_store.settings", …)`` working.
    """
    try:
        yaml_value = load_provider_settings().graphrag.enabled
    except Exception:
        yaml_value = None
    if yaml_value is not None:
        return bool(yaml_value)
    return bool(settings.ENABLE_GRAPH_INDEX)


def _resolve_graph_index_path(configured_path: str) -> Path:
    """Resolve the graph-index directory.

    - Absolute paths are used verbatim.
    - The legacy default (``./graph_index``) is mapped under the project
      state directory so it lands in ``<state_dir>/data/graph_index``
      rather than CWD, matching how every other persistent store resolves
      its location (issue #126).
    - Any other relative path is resolved against ``state_dir`` if one is
      configured, else against CWD.
    """
    p = Path(configured_path).expanduser()
    if p.is_absolute():
        return p

    state_dir_env = os.getenv("AGENT_BRAIN_STATE_DIR") or os.getenv(
        "DOC_SERVE_STATE_DIR"
    )
    if state_dir_env:
        state_dir = Path(state_dir_env).expanduser().resolve()
        # Treat the historical default specially so it lands in the standard
        # storage location used by resolve_storage_paths().
        if configured_path in {"./graph_index", "graph_index"}:
            return state_dir / "data" / "graph_index"
        return (state_dir / p).resolve()

    return p.resolve()


class GraphStoreManager:
    """Manages graph storage backends for GraphRAG.

    Supports SimplePropertyGraphStore (default) and Kuzu (optional).
    Implements singleton pattern for consistent graph access.

    Attributes:
        persist_dir: Directory for graph persistence.
        store_type: Backend type - "simple" or "kuzu".
    """

    _instance: Optional["GraphStoreManager"] = None

    def __init__(self, persist_dir: Path, store_type: str = "simple") -> None:
        """Initialize graph store manager.

        Args:
            persist_dir: Directory for graph persistence.
            store_type: Backend type - "simple" or "kuzu".
        """
        self.persist_dir = persist_dir
        self.store_type = store_type
        self._graph_store: Any | None = None
        self._kuzu_db: Any | None = None
        self._initialized = False
        self._entity_count = 0
        self._relationship_count = 0
        self._last_updated: datetime | None = None

    @classmethod
    def get_instance(
        cls,
        persist_dir: Path | None = None,
        store_type: str | None = None,
    ) -> "GraphStoreManager":
        """Get or create singleton instance.

        Args:
            persist_dir: Directory for graph persistence.
            store_type: Backend type - "simple" or "kuzu".

        Returns:
            The singleton GraphStoreManager instance.
        """
        if cls._instance is None:
            if persist_dir is None or store_type is None:
                # YAML wins when set; otherwise fall back to env-var settings
                # so existing tests that patch ``settings`` keep working.
                try:
                    yaml_cfg = load_provider_settings().graphrag
                except Exception:
                    yaml_cfg = None

                if persist_dir is None:
                    yaml_path = getattr(yaml_cfg, "index_path", None)
                    persist_dir = _resolve_graph_index_path(
                        yaml_path or settings.GRAPH_INDEX_PATH
                    )
                if store_type is None:
                    yaml_store = getattr(yaml_cfg, "store_type", None)
                    store_type = yaml_store or settings.GRAPH_STORE_TYPE
            cls._instance = cls(persist_dir, store_type)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance. Used for testing."""
        cls._instance = None

    def initialize(self) -> None:
        """Initialize the graph store based on store_type.

        For "simple": Uses SimplePropertyGraphStore with JSON persistence.
        For "kuzu": Attempts to use Kuzu, falls back to simple with warning.

        This is a no-op when ENABLE_GRAPH_INDEX is False.
        """
        if not _graphrag_enabled():
            logger.debug("graph_store.initialize: skipped (ENABLE_GRAPH_INDEX=false)")
            return

        if self._initialized:
            logger.debug(
                "graph_store.initialize: skipped (already initialized)",
                extra={
                    "store_type": self.store_type,
                    "entity_count": self._entity_count,
                    "relationship_count": self._relationship_count,
                },
            )
            return

        logger.info(
            "graph_store.initialize: starting",
            extra={
                "store_type": self.store_type,
                "persist_dir": str(self.persist_dir),
            },
        )

        # Ensure persistence directory exists
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        if self.store_type == "kuzu":
            self._initialize_kuzu_store()
        else:
            self._initialize_simple_store()

        # Try to load existing graph data
        self.load()

        self._initialized = True
        logger.info(
            "graph_store.initialize: completed",
            extra={
                "store_type": self.store_type,
                "entity_count": self._entity_count,
                "relationship_count": self._relationship_count,
                "persist_dir": str(self.persist_dir),
            },
        )

    def _initialize_simple_store(self) -> None:
        """Initialize SimplePropertyGraphStore backend."""
        try:
            from llama_index.core.graph_stores import SimplePropertyGraphStore

            self._graph_store = SimplePropertyGraphStore()
            logger.debug("Initialized SimplePropertyGraphStore")
        except ImportError as e:
            logger.warning(f"Failed to import SimplePropertyGraphStore: {e}")
            # Create a minimal fallback store
            self._graph_store = _MinimalGraphStore()
            logger.debug("Using minimal fallback graph store")

    def _initialize_kuzu_store(self) -> None:
        """Initialize Kuzu graph store with fallback to simple.

        Compatible with ``llama-index-graph-stores-kuzu>=0.9.0``, whose
        ``KuzuPropertyGraphStore`` constructor takes a positional
        ``kuzu.Database`` object instead of the old ``database_path`` kwarg
        (issue #144). ``use_vector_index=False`` keeps the constructor from
        requiring an ``embed_model`` — agent-brain uses ChromaDB for vectors,
        not Kuzu's native vector index.
        """
        try:
            import kuzu
            from llama_index.graph_stores.kuzu import KuzuPropertyGraphStore

            # kuzu >= 0.10 uses a single-file database format; pre-creating
            # the path as a directory makes Database() raise. Ensure the
            # parent exists but leave the database path itself to Kuzu.
            self.persist_dir.mkdir(parents=True, exist_ok=True)
            kuzu_db_path = self.persist_dir / "kuzu_db"

            # Self-heal: pre-v10.0.4 left an empty kuzu_db/ directory at this
            # path, which kuzu 0.10+ rejects with "Database path cannot be a
            # directory". rmdir() only succeeds on empty dirs, so this is
            # safe; a non-empty leftover gets a clearer error than the raw
            # Kuzu message. Issue #151.
            if kuzu_db_path.is_dir():
                try:
                    kuzu_db_path.rmdir()
                    logger.info(
                        "Removed stale empty kuzu_db/ directory from a prior "
                        "version: %s",
                        kuzu_db_path,
                    )
                except OSError as exc:
                    raise RuntimeError(
                        f"Expected a kuzu database file at {kuzu_db_path} but "
                        "found a non-empty directory. This may be leftover "
                        "state from an earlier agent-brain version. Inspect "
                        "and remove it, or point GRAPH_INDEX_PATH at a fresh "
                        "location."
                    ) from exc

            self._kuzu_db, self._graph_store = self._open_kuzu_with_recovery(
                kuzu, KuzuPropertyGraphStore, kuzu_db_path
            )
            logger.debug(f"Initialized KuzuPropertyGraphStore at {kuzu_db_path}")

            # If we just recovered from corruption, replay the latest valid
            # snapshot to restore previously-extracted triplets. Done after
            # the graph store wrapper is in place so we can route through it.
            self._restore_from_snapshot_if_available()
        except ImportError as e:
            logger.warning(
                f"Kuzu not available ({e}), falling back to SimplePropertyGraphStore. "
                "Install with: pip install 'agent-brain-rag[graphrag-kuzu]'"
            )
            self.store_type = "simple"
            self._initialize_simple_store()

    def _open_kuzu_with_recovery(
        self, kuzu: Any, kuzu_store_cls: Any, kuzu_db_path: Path
    ) -> tuple[Any, Any]:
        """Open the Kuzu DB *and* its property-graph wrapper, recovering on
        corruption.

        Both ``kuzu.Database()`` AND ``KuzuPropertyGraphStore(db, ...)`` can
        fail when the on-disk catalog is corrupted — the wrapper opens a
        ``kuzu.Connection`` and runs ``init_schema()`` DDL during its
        constructor. We wrap both calls together so corruption that
        manifests during connection setup (not just the Database constructor)
        is also caught and self-healed.

        Sequence on corruption (see issue #166):

        1. Log a loud, actionable WARN naming the path and the originating
           exception (IndexError ``unordered_map::at: key not found`` is the
           canonical kill-mid-write signature; we also catch RuntimeError
           and broadly-typed exceptions raised from pybind11 internals).
        2. Rename ``kuzu_db`` and ``kuzu_db.wal`` to ``.corrupted-<ts>``
           siblings — preserved for post-mortem, never deleted.
        3. Retry the open-and-wrap pair on the now-empty path.
        4. Trigger snapshot replay (handled by caller after this returns).

        If the retry *also* fails we raise a structured ``RuntimeError`` with
        explicit reset instructions. We never loop.

        Sets ``self._recovered_from_corruption`` so
        ``_restore_from_snapshot_if_available`` only runs when there's
        something to restore.

        Returns:
            ``(kuzu.Database, KuzuPropertyGraphStore)`` tuple.
        """
        self._recovered_from_corruption = False

        def _attempt() -> tuple[Any, Any]:
            db = kuzu.Database(str(kuzu_db_path))
            store = kuzu_store_cls(db, use_vector_index=False)
            return db, store

        # Catch the narrow corruption signatures (IndexError, RuntimeError)
        # for the Database/Connection layer. We deliberately don't catch
        # broader Exception here so genuine misconfigurations (e.g.
        # ImportError from a missing extra) still surface clearly.
        try:
            return _attempt()
        except (IndexError, RuntimeError) as exc:
            logger.warning(
                "Kuzu graph store at %s appears corrupted (likely from a "
                "prior process kill mid-indexing): %s. Renaming to "
                ".corrupted-<ts> and starting fresh. Previously-extracted "
                "triplets will be restored from the latest snapshot if "
                "available; otherwise re-index to rebuild.",
                kuzu_db_path,
                exc,
            )
            quarantined_db = _quarantine_file(kuzu_db_path)
            quarantined_wal = _quarantine_file(
                kuzu_db_path.with_name(kuzu_db_path.name + ".wal")
            )
            logger.info(
                "Quarantined corrupted Kuzu files: db=%s wal=%s",
                quarantined_db,
                quarantined_wal,
            )
            self._recovered_from_corruption = True
            try:
                return _attempt()
            except (IndexError, RuntimeError) as retry_exc:
                raise RuntimeError(
                    f"Failed to initialize Kuzu graph store at {kuzu_db_path} "
                    f"even after quarantining the corrupted database "
                    f"({quarantined_db}). The retry attempt also raised: "
                    f"{retry_exc}. To fully reset, stop the server and "
                    f"`rm -rf {kuzu_db_path.parent}` (this loses all "
                    "previously-extracted triplets)."
                ) from retry_exc

    def _restore_from_snapshot_if_available(self) -> int:
        """Replay the latest valid triplet snapshot into the graph store.

        Only runs when ``self._recovered_from_corruption`` is True — on a
        clean DB there's nothing to restore. Walks newest-to-oldest
        snapshots, skipping (and renaming) corrupted ones, until a valid
        snapshot is found.

        Returns:
            Number of triplets restored (0 if no snapshot available).
        """
        if not getattr(self, "_recovered_from_corruption", False):
            return 0

        snapshot_mgr = GraphSnapshotManager(self.persist_dir)
        loaded = snapshot_mgr.load_latest_valid()
        if loaded is None:
            logger.info(
                "graph_store: no snapshot available after recovery; "
                "starting with empty graph at %s",
                self.persist_dir,
            )
            return 0

        snapshot_path, triplets = loaded
        restored = 0
        for triplet in triplets:
            if self._apply_triplet_to_store(triplet):
                restored += 1
        # Update bookkeeping counters so subsequent persist/load matches reality
        self._relationship_count = restored
        self._last_updated = datetime.now(timezone.utc)

        logger.warning(
            "Restored %d triplets from snapshot %s after recovering "
            "corrupted kuzu_db at %s",
            restored,
            snapshot_path.name,
            self.persist_dir / "kuzu_db",
        )
        return restored

    def _apply_triplet_to_store(self, triplet: SnapshotTriplet) -> bool:
        """Insert a triplet into the underlying graph store backend.

        This is the same body as ``add_triplet`` but without the
        ``_initialized`` guard, so it can run during initialization (during
        snapshot replay). Returns True on success.
        """
        store = self._graph_store
        if store is None:
            return False
        try:
            if hasattr(store, "upsert_triplet"):
                store.upsert_triplet(
                    subject=triplet.subject,
                    predicate=triplet.predicate,
                    object_=triplet.object,
                )
            elif hasattr(store, "upsert_relations") and hasattr(store, "upsert_nodes"):
                from llama_index.core.graph_stores.types import (
                    EntityNode,
                    Relation,
                )

                subj_node = EntityNode(
                    name=triplet.subject,
                    label=triplet.subject_type or "Entity",
                )
                obj_node = EntityNode(
                    name=triplet.object,
                    label=triplet.object_type or "Entity",
                )
                store.upsert_nodes([subj_node, obj_node])
                store.upsert_relations(
                    [
                        Relation(
                            label=triplet.predicate,
                            source_id=subj_node.id,
                            target_id=obj_node.id,
                            properties=(
                                {"source_chunk_id": triplet.source_chunk_id}
                                if triplet.source_chunk_id
                                else {}
                            ),
                        )
                    ]
                )
            elif hasattr(store, "add_triplet"):
                store.add_triplet(triplet.subject, triplet.predicate, triplet.object)
            elif hasattr(store, "_add_triplet"):
                store._add_triplet(
                    triplet.subject,
                    triplet.predicate,
                    triplet.object,
                    triplet.subject_type,
                    triplet.object_type,
                    triplet.source_chunk_id,
                )
            else:
                return False
            return True
        except Exception as exc:
            logger.warning(
                "graph_store._apply_triplet_to_store: failed for %s -%s-> %s: %s",
                triplet.subject,
                triplet.predicate,
                triplet.object,
                exc,
            )
            return False

    def preflight_check(self) -> bool:
        """Open the Kuzu DB proactively so corruption is caught at startup.

        Called from the server lifespan before any indexing job runs, so the
        first user-facing job doesn't pay the corruption-recovery tax. Safe
        to call multiple times; no-ops if GraphRAG is disabled or already
        initialized.

        Returns:
            True if the store is healthy (possibly after recovery), False
            if the preflight was skipped (graphrag disabled, non-kuzu).
        """
        if not _graphrag_enabled():
            return False
        if self.store_type != "kuzu":
            return False
        if self._initialized:
            return True
        self.initialize()
        return True

    def persist(self) -> None:
        """Persist graph to disk.

        For SimplePropertyGraphStore, serializes to JSON.
        For Kuzu, data is automatically persisted.

        This is a no-op when ENABLE_GRAPH_INDEX is False or not initialized.
        """
        if not _graphrag_enabled():
            return

        if not self._initialized or self._graph_store is None:
            logger.debug("Graph store not initialized, skipping persist")
            return

        if self.store_type == "simple":
            self._persist_simple_store()

        self._last_updated = datetime.now(timezone.utc)
        logger.debug(
            f"Graph persisted: entities={self._entity_count}, "
            f"relationships={self._relationship_count}"
        )

    def _persist_simple_store(self) -> None:
        """Persist SimplePropertyGraphStore to JSON."""
        persist_path = self.persist_dir / "graph_store.json"
        llamaindex_persist_path = self.persist_dir / "graph_store_llamaindex.json"

        try:
            # Try LlamaIndex native persistence first
            graph_store = self._graph_store
            if graph_store is not None and hasattr(graph_store, "persist"):
                graph_store.persist(str(llamaindex_persist_path))
                logger.debug(
                    f"Graph persisted via LlamaIndex to {llamaindex_persist_path}"
                )
            elif graph_store is not None and hasattr(graph_store, "_data"):
                # Minimal store fallback - use our own format
                data = getattr(graph_store, "_data", {})
                with open(persist_path, "w") as f:
                    json.dump(data, f, indent=2, default=str)
                logger.debug(f"Graph persisted to {persist_path}")

            # Always persist metadata separately
            metadata = {
                "entity_count": self._entity_count,
                "relationship_count": self._relationship_count,
                "last_updated": (
                    self._last_updated.isoformat() if self._last_updated else None
                ),
                "store_type": self.store_type,
            }
            metadata_path = self.persist_dir / "graph_metadata.json"
            with open(metadata_path, "w") as f:
                json.dump(metadata, f, indent=2)

        except (OSError, TypeError) as e:
            logger.error(f"Failed to persist graph store: {e}")

    def load(self) -> bool:
        """Load graph from disk.

        For SimplePropertyGraphStore, loads from JSON.
        For Kuzu, data is automatically loaded.

        Returns:
            True if loaded successfully, False otherwise.
        """
        if not _graphrag_enabled():
            return False

        if self._graph_store is None:
            return False

        if self.store_type == "simple":
            return self._load_simple_store()

        # Kuzu loads automatically, just update counts
        self._update_counts()
        return True

    def _load_simple_store(self) -> bool:
        """Load SimplePropertyGraphStore from persisted data."""
        llamaindex_persist_path = self.persist_dir / "graph_store_llamaindex.json"
        persist_path = self.persist_dir / "graph_store.json"
        metadata_path = self.persist_dir / "graph_metadata.json"

        # Load metadata if available
        if metadata_path.exists():
            try:
                with open(metadata_path) as f:
                    metadata = json.load(f)
                self._entity_count = metadata.get("entity_count", 0)
                self._relationship_count = metadata.get("relationship_count", 0)
                last_updated_str = metadata.get("last_updated")
                if last_updated_str:
                    self._last_updated = datetime.fromisoformat(last_updated_str)
            except (OSError, json.JSONDecodeError) as e:
                logger.warning(f"Failed to load graph metadata: {e}")

        # Try LlamaIndex native load first
        if llamaindex_persist_path.exists():
            try:
                from llama_index.core.graph_stores import SimplePropertyGraphStore

                self._graph_store = SimplePropertyGraphStore.from_persist_path(
                    str(llamaindex_persist_path)
                )
                logger.debug(
                    f"Graph loaded from {llamaindex_persist_path}: "
                    f"entities={self._entity_count}, "
                    f"relationships={self._relationship_count}"
                )
                return True
            except Exception as e:
                logger.warning(f"Failed to load via LlamaIndex: {e}")

        # Fall back to minimal store format
        if persist_path.exists():
            try:
                with open(persist_path) as f:
                    data = json.load(f)

                # Restore minimal store data
                graph_store = self._graph_store
                if graph_store is not None and hasattr(graph_store, "_data"):
                    graph_store._data = data
                    if "entities" in data:
                        graph_store._entities = data.get("entities", {})
                    if "relationships" in data:
                        graph_store._relationships = data.get("relationships", [])

                logger.debug(
                    f"Graph loaded from {persist_path}: "
                    f"entities={self._entity_count}, "
                    f"relationships={self._relationship_count}"
                )
                return True
            except (OSError, json.JSONDecodeError) as e:
                logger.error(f"Failed to load graph store: {e}")
                return False

        logger.debug("No graph data found to load")
        return False

    def _update_counts(self) -> None:
        """Update entity and relationship counts from graph store."""
        if self._graph_store is None:
            return

        try:
            # Try to get counts from graph store
            if hasattr(self._graph_store, "get_triplets"):
                triplets = self._graph_store.get_triplets()
                entities: set[str] = set()
                for triplet in triplets:
                    if hasattr(triplet, "subject"):
                        entities.add(triplet.subject)
                    if hasattr(triplet, "object"):
                        entities.add(triplet.object)
                self._entity_count = len(entities)
                self._relationship_count = len(triplets)
            elif hasattr(self._graph_store, "_entities"):
                self._entity_count = len(self._graph_store._entities)
                self._relationship_count = len(
                    getattr(self._graph_store, "_relationships", [])
                )
        except Exception as e:
            logger.warning(f"Failed to update graph counts: {e}")

    def add_triplet(
        self,
        subject: str,
        predicate: str,
        obj: str,
        subject_type: str | None = None,
        object_type: str | None = None,
        source_chunk_id: str | None = None,
    ) -> bool:
        """Add a triplet to the graph.

        Args:
            subject: Subject entity.
            predicate: Relationship type.
            obj: Object entity.
            subject_type: Optional type for subject.
            object_type: Optional type for object.
            source_chunk_id: Optional source chunk ID.

        Returns:
            True if added successfully, False otherwise.
        """
        if not _graphrag_enabled():
            return False

        if not self._initialized or self._graph_store is None:
            logger.warning(
                "graph_store.add_triplet: skipped (store not initialized)",
                extra={
                    "subject": subject,
                    "predicate": predicate,
                    "object": obj,
                },
            )
            return False

        try:
            if hasattr(self._graph_store, "upsert_triplet"):
                self._graph_store.upsert_triplet(
                    subject=subject,
                    predicate=predicate,
                    object_=obj,
                )
            elif hasattr(self._graph_store, "upsert_relations") and hasattr(
                self._graph_store, "upsert_nodes"
            ):
                # Modern PropertyGraphStore API (e.g. KuzuPropertyGraphStore >= 0.9).
                # No upsert_triplet helper — build EntityNode + Relation objects.
                from llama_index.core.graph_stores.types import EntityNode, Relation

                subj_node = EntityNode(name=subject, label=subject_type or "Entity")
                obj_node = EntityNode(name=obj, label=object_type or "Entity")
                self._graph_store.upsert_nodes([subj_node, obj_node])
                self._graph_store.upsert_relations(
                    [
                        Relation(
                            label=predicate,
                            source_id=subj_node.id,
                            target_id=obj_node.id,
                            properties=(
                                {"source_chunk_id": source_chunk_id}
                                if source_chunk_id
                                else {}
                            ),
                        )
                    ]
                )
            elif hasattr(self._graph_store, "add_triplet"):
                self._graph_store.add_triplet(subject, predicate, obj)
            elif hasattr(self._graph_store, "_add_triplet"):
                # Minimal store fallback
                self._graph_store._add_triplet(
                    subject, predicate, obj, subject_type, object_type, source_chunk_id
                )

            # Update counts
            self._entity_count = max(
                self._entity_count,
                self._entity_count + 1,  # Approximate
            )
            self._relationship_count += 1
            self._last_updated = datetime.now(timezone.utc)

            logger.debug(
                "graph_store.add_triplet: success",
                extra={
                    "subject": subject,
                    "predicate": predicate,
                    "object": obj,
                    "subject_type": subject_type,
                    "object_type": object_type,
                    "source_chunk_id": source_chunk_id,
                    "total_relationships": self._relationship_count,
                },
            )

            return True
        except Exception as e:
            logger.error(
                "graph_store.add_triplet: failed",
                extra={
                    "subject": subject,
                    "predicate": predicate,
                    "object": obj,
                    "error": str(e),
                },
            )
            return False

    def get_entity_by_id(
        self,
        entity_type: str,
        entity_id: str,
    ) -> GraphEntityRecord | None:
        """Fetch an entity by ``(type, id)`` with its 1-hop neighbors.

        Backs ``GET /graph/entity/{entity_type}/{entity_id}`` and the MCP
        ``graph-entity://<type>/<id>`` resource scheme (URI-02 in Phase 51).
        Wire shape locked by Phase 50 design doc §2.4.

        Implementation strategy: both ``SimplePropertyGraphStore`` and
        ``KuzuPropertyGraphStore`` inherit the LlamaIndex ``PropertyGraphStore``
        contract, so we drive both backends through the same primitives:

        - ``graph_store.get(ids=[entity_id])`` — entity lookup by id
        - ``graph_store.get_triplets(ids=[entity_id])`` — 1-hop relationships

        We then filter the returned entity by label (``entity_type``) so a
        request for ``Function/foo`` does not return a ``Class/foo`` even
        when both exist. Direction (incoming vs outgoing) is derived from
        whether the relation's ``source_id`` matches the target entity.

        Args:
            entity_type: SCHEMA-01 entity type (caller validates against the
                vocabulary; this method treats it as an opaque label so
                non-canonical labels in legacy data still resolve).
            entity_id: Entity id (the entity's ``name`` in current backends).

        Returns:
            ``GraphEntityRecord`` when the ``(type, id)`` pair exists.
            ``None`` when no entity with that type+id is found — the router
            translates this to HTTP 404 ``entity_not_found``.

        Raises:
            KuzuUnavailableError: When the Kuzu backend raises a corruption
                signature (IndexError / RuntimeError / OSError out of
                pybind11 internals). The router translates this to HTTP 503
                ``kuzu_unavailable`` so the server keeps running. See #178.
        """
        if not _graphrag_enabled():
            return None
        if not self._initialized or self._graph_store is None:
            return None

        store = self._graph_store
        try:
            nodes = store.get(ids=[entity_id])
        except (IndexError, RuntimeError, OSError) as exc:
            # Kuzu SIGSEGV / catalog corruption signature (issue #178).
            # Surface as a structured error the router can translate to 503
            # rather than crashing the process.
            if self.store_type == "kuzu":
                logger.warning(
                    "graph_store.get_entity_by_id: Kuzu unavailable for "
                    "%s/%s (#178 corruption signature): %s",
                    entity_type,
                    entity_id,
                    exc,
                )
                raise KuzuUnavailableError(
                    f"Kuzu graph store raised during entity lookup: {exc}. "
                    "Operator workaround: set graphrag.store_type=simple."
                ) from exc
            # Simple store / minimal fallback shouldn't raise these — but
            # we treat them as transient and return None rather than
            # crashing.
            logger.warning(
                "graph_store.get_entity_by_id: %s raised on get(ids=...) "
                "for %s/%s: %s",
                self.store_type,
                entity_type,
                entity_id,
                exc,
            )
            return None

        # Filter by entity_type so (Function, "foo") and (Class, "foo")
        # are distinguishable. Backends differ on which attribute carries
        # the schema label: SimplePropertyGraphStore puts it on
        # ``node.label`` directly; Kuzu's ``get_triplets`` sets ``.label``
        # to the literal ``"Entity"`` and stashes the real schema label
        # inside ``node.properties["label"]``. We accept either.
        matching = [n for n in nodes if _label_of(n) == entity_type]
        if not matching:
            return None
        node = matching[0]

        # Use the actual backend-internal id (in current LlamaIndex
        # PropertyGraphStore impls this is the same as ``name``; we resolve
        # it through ``getattr`` so a future backend can carry a separate
        # opaque id without changing the wire shape).
        node_id = getattr(node, "id", entity_id) or entity_id

        try:
            triplets = store.get_triplets(ids=[node_id])
        except (IndexError, RuntimeError, OSError) as exc:
            if self.store_type == "kuzu":
                logger.warning(
                    "graph_store.get_entity_by_id: Kuzu unavailable for "
                    "neighbors of %s/%s (#178): %s",
                    entity_type,
                    entity_id,
                    exc,
                )
                raise KuzuUnavailableError(
                    f"Kuzu graph store raised during neighbor lookup: {exc}. "
                    "Operator workaround: set graphrag.store_type=simple."
                ) from exc
            logger.warning(
                "graph_store.get_entity_by_id: %s raised on "
                "get_triplets(ids=...) for %s/%s: %s",
                self.store_type,
                entity_type,
                entity_id,
                exc,
            )
            triplets = []

        incoming: list[GraphEntityRecordNeighbor] = []
        outgoing: list[GraphEntityRecordNeighbor] = []
        # Backends differ in how they identify nodes inside triplets:
        # SimplePropertyGraphStore sets source_id == name; KuzuPropertyGraphStore
        # may use the id field. Match against the union of both so direction
        # detection works on either backend.
        target_match = {node_id, entity_id, getattr(node, "name", entity_id)}
        for triplet in triplets or []:
            try:
                subject_node, relation, object_node = triplet
            except (TypeError, ValueError):
                logger.debug(
                    "graph_store.get_entity_by_id: skipping malformed triplet "
                    "for %s/%s",
                    entity_type,
                    entity_id,
                )
                continue

            relation_props = dict(getattr(relation, "properties", {}) or {})
            source_id = getattr(relation, "source_id", None)
            target_id = getattr(relation, "target_id", None)
            predicate = getattr(relation, "label", "") or ""

            if source_id in target_match:
                # Outgoing edge: target entity points at object_node.
                outgoing.append(
                    GraphEntityRecordNeighbor(
                        type=_label_of(object_node),
                        id=_id_of(object_node),
                        predicate=predicate,
                        properties=relation_props,
                    )
                )
            elif target_id in target_match:
                # Incoming edge: subject_node points at target entity.
                incoming.append(
                    GraphEntityRecordNeighbor(
                        type=_label_of(subject_node),
                        id=_id_of(subject_node),
                        predicate=predicate,
                        properties=relation_props,
                    )
                )
            else:
                # Triplet doesn't actually touch the target entity — likely
                # a backend quirk (e.g. Kuzu returning extra rows). Skip.
                continue

        return GraphEntityRecord(
            entity=GraphEntityRecordNode(
                type=entity_type,
                id=getattr(node, "name", entity_id) or entity_id,
                properties=dict(getattr(node, "properties", {}) or {}),
            ),
            neighbors=GraphEntityRecordNeighbors(
                incoming=incoming,
                outgoing=outgoing,
            ),
        )

    def clear(self) -> None:
        """Clear all graph data.

        This is a no-op when ENABLE_GRAPH_INDEX is False.
        """
        if not _graphrag_enabled():
            logger.debug("graph_store.clear: skipped (ENABLE_GRAPH_INDEX=false)")
            return

        prev_entities = self._entity_count
        prev_relationships = self._relationship_count

        if self._graph_store is not None:
            if hasattr(self._graph_store, "clear"):
                self._graph_store.clear()
            elif hasattr(self._graph_store, "_data"):
                self._graph_store._data = {}

        self._entity_count = 0
        self._relationship_count = 0
        self._last_updated = None

        # Remove persisted data
        persist_path = self.persist_dir / "graph_store.json"
        if persist_path.exists():
            persist_path.unlink()

        logger.info(
            "graph_store.clear: completed",
            extra={
                "previous_entities": prev_entities,
                "previous_relationships": prev_relationships,
                "persist_dir": str(self.persist_dir),
            },
        )

    @property
    def is_initialized(self) -> bool:
        """Check if the graph store is initialized."""
        return self._initialized

    @property
    def entity_count(self) -> int:
        """Return number of entities in graph."""
        return self._entity_count

    @property
    def relationship_count(self) -> int:
        """Return number of relationships in graph."""
        return self._relationship_count

    @property
    def last_updated(self) -> datetime | None:
        """Return timestamp of last update."""
        return self._last_updated

    @property
    def graph_store(self) -> Any | None:
        """Return the underlying graph store instance."""
        return self._graph_store


class _MinimalGraphStore:
    """Minimal fallback graph store when LlamaIndex is not available.

    Provides basic in-memory graph storage with JSON serialization.
    """

    def __init__(self) -> None:
        """Initialize minimal graph store."""
        self._data: dict[str, Any] = {
            "entities": {},
            "relationships": [],
        }
        self._entities: dict[str, dict[str, Any]] = {}
        self._relationships: list[dict[str, Any]] = []

    def _add_triplet(
        self,
        subject: str,
        predicate: str,
        obj: str,
        subject_type: str | None = None,
        object_type: str | None = None,
        source_chunk_id: str | None = None,
    ) -> None:
        """Add a triplet to the minimal store."""
        # Add entities
        if subject not in self._entities:
            self._entities[subject] = {"name": subject, "type": subject_type}
        if obj not in self._entities:
            self._entities[obj] = {"name": obj, "type": object_type}

        # Add relationship
        self._relationships.append(
            {
                "subject": subject,
                "predicate": predicate,
                "object": obj,
                "source_chunk_id": source_chunk_id,
            }
        )

        # Update data dict
        self._data["entities"] = self._entities
        self._data["relationships"] = self._relationships

    def clear(self) -> None:
        """Clear all data."""
        self._data = {"entities": {}, "relationships": []}
        self._entities = {}
        self._relationships = []


# Module-level singleton access
_graph_store_manager: GraphStoreManager | None = None


def get_graph_store_manager(
    persist_dir: Path | None = None,
    store_type: str | None = None,
) -> GraphStoreManager:
    """Get the global graph store manager instance.

    Args:
        persist_dir: Directory for graph persistence.
        store_type: Backend type - "simple" or "kuzu".

    Returns:
        The singleton GraphStoreManager instance.
    """
    global _graph_store_manager
    if _graph_store_manager is None:
        _graph_store_manager = GraphStoreManager.get_instance(persist_dir, store_type)
    return _graph_store_manager


def initialize_graph_store(
    persist_dir: Path | None = None,
    store_type: str | None = None,
) -> GraphStoreManager:
    """Initialize and return the global graph store manager.

    Args:
        persist_dir: Directory for graph persistence.
        store_type: Backend type - "simple" or "kuzu".

    Returns:
        The initialized GraphStoreManager instance.
    """
    manager = get_graph_store_manager(persist_dir, store_type)
    manager.initialize()
    return manager


def reset_graph_store_manager() -> None:
    """Reset the global graph store manager. Used for testing."""
    global _graph_store_manager
    _graph_store_manager = None
    GraphStoreManager.reset_instance()
