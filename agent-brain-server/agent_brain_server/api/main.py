"""FastAPI application entry point.

This module provides the Agent Brain RAG server, a FastAPI application
for document indexing and semantic search.

Note: This server assumes a single uvicorn worker process. If running
multiple workers, ensure only one worker handles indexing jobs by using
the single-worker model or a separate job processor service.
"""

import asyncio
import logging
import os
import socket
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import click
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agent_brain_server import __version__
from agent_brain_server.api import uds_bind
from agent_brain_server.config import settings
from agent_brain_server.config.provider_config import (
    ValidationSeverity,
    clear_settings_cache,
    has_critical_errors,
    load_provider_settings,
    validate_provider_config,
)
from agent_brain_server.indexing.bm25_index import BM25IndexManager, set_bm25_manager
from agent_brain_server.job_queue import JobQueueService, JobQueueStore, JobWorker
from agent_brain_server.locking import (
    acquire_lock,
    cleanup_stale,
    is_stale,
    release_lock,
)
from agent_brain_server.project_root import resolve_project_root
from agent_brain_server.runtime import RuntimeState, delete_runtime, write_runtime
from agent_brain_server.services import FolderManager, IndexingService, QueryService
from agent_brain_server.storage import (
    VectorStoreManager,
    get_effective_backend_type,
    get_storage_backend,
    set_vector_store,
)
from agent_brain_server.storage_paths import resolve_state_dir, resolve_storage_paths

from .routers import (
    cache_router,
    folders_router,
    health_router,
    index_router,
    jobs_router,
    query_router,
)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Module-level state for multi-instance mode
_runtime_state: RuntimeState | None = None
_state_dir: Path | None = None

# Module-level reference to job worker for cleanup
_job_worker: JobWorker | None = None

# Module-level reference to file watcher service for cleanup
_file_watcher: object = None


_STRAY_CWD_DATA_DIRS = ("chroma_db", "bm25_index", "graph_index")


def _warn_about_stray_cwd_data_dirs(state_dir: Path) -> None:
    """Log a warning if CWD-relative data dirs from older versions exist.

    Issue #170: prior to the singleton setter fix, calling
    get_vector_store() or get_bm25_manager() before the FastAPI lifespan
    had registered the state-dir-resolved instance would create stray
    directories named ``chroma_db/`` or ``bm25_index/`` at the current
    working directory. The fix prevents new strays but does not migrate
    existing ones — silent data motion is dangerous.

    Args:
        state_dir: The resolved state directory, used to build the
            recommended ``mv`` command in the warning message.
    """
    cwd = Path.cwd().resolve()
    for name in _STRAY_CWD_DATA_DIRS:
        stray = cwd / name
        if not stray.is_dir():
            continue
        canonical = state_dir / "data" / name
        if stray.resolve() == canonical.resolve():
            continue
        logger.warning(
            "Detected stray data directory %s (likely from a pre-fix "
            "release of agent-brain — issue #170). The canonical "
            "location is %s. If this directory holds valuable data, "
            "merge it manually; otherwise remove it: rm -rf %s",
            stray,
            canonical,
            stray,
        )


def _build_provider_fingerprint() -> str:
    """Build a stable provider:model:dimensions fingerprint string.

    Used by the embedding cache to detect provider or model changes on
    startup (ECACHE-04 auto-wipe).

    Returns:
        Fingerprint string of the form ``"provider:model:dimensions"``,
        e.g. ``"openai:text-embedding-3-large:3072"``.
        Returns ``"unknown:unknown:0"`` on any configuration error.
    """
    try:
        ps = load_provider_settings()
        from agent_brain_server.providers.factory import ProviderRegistry

        provider = ProviderRegistry.get_embedding_provider(ps.embedding)
        dims = provider.get_dimensions()
        return f"{ps.embedding.provider}:{ps.embedding.model}:{dims}"
    except Exception as exc:
        logger.warning("Failed to build provider fingerprint: %s", exc)
        return "unknown:unknown:0"


async def check_embedding_compatibility(
    vector_store: VectorStoreManager,
) -> str | None:
    """Check if current embedding config matches existing index.

    Args:
        vector_store: Initialized vector store manager

    Returns:
        Warning message if mismatch detected, None if compatible
    """
    try:
        stored_metadata = await vector_store.get_embedding_metadata()
        if stored_metadata is None:
            return None  # No existing index

        # Get current config
        provider_settings = load_provider_settings()
        from agent_brain_server.providers.factory import ProviderRegistry

        embedding_provider = ProviderRegistry.get_embedding_provider(
            provider_settings.embedding
        )
        current_dimensions = embedding_provider.get_dimensions()
        current_provider = str(provider_settings.embedding.provider)
        current_model = provider_settings.embedding.model

        # Check for mismatch
        if (
            stored_metadata.dimensions != current_dimensions
            or stored_metadata.provider != current_provider
            or stored_metadata.model != current_model
        ):
            return (
                f"Embedding provider mismatch: index was created with "
                f"{stored_metadata.provider}/{stored_metadata.model} "
                f"({stored_metadata.dimensions}d), but current config uses "
                f"{current_provider}/{current_model} ({current_dimensions}d). "
                f"Queries may return incorrect results. "
                f"Re-index with --force to update."
            )
        return None
    except Exception as e:
        logger.warning(f"Failed to check embedding compatibility: {e}")
        return None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan manager.

    Initializes services and stores them on app.state for dependency
    injection via request.app.state in route handlers.

    In per-project mode:
    - Resolves project root and state directory
    - Acquires lock (with stale detection)
    - Writes runtime.json with server info
    - Initializes job queue system
    - Cleans up on shutdown
    """
    global _runtime_state, _state_dir, _job_worker, _file_watcher

    logger.info("Starting Agent Brain RAG server...")

    # Suppress ChromaDB telemetry noise (PostHog) during startup.
    os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
    logging.getLogger("chromadb.telemetry").setLevel(logging.WARNING)
    logging.getLogger("posthog").setLevel(logging.WARNING)

    # Load and validate provider configuration
    # Clear cache first to ensure we pick up env vars set by CLI
    clear_settings_cache()
    strict_mode = settings.AGENT_BRAIN_STRICT_MODE

    try:
        provider_settings = load_provider_settings()
        enable_reranking = getattr(settings, "ENABLE_RERANKING", False)
        validation_errors = validate_provider_config(
            provider_settings,
            reranking_enabled=bool(enable_reranking),
        )

        if validation_errors:
            for error in validation_errors:
                if error.severity == ValidationSeverity.CRITICAL:
                    logger.error(f"Provider config error: {error}")
                else:
                    logger.warning(f"Provider config warning: {error}")

            # In strict mode, fail on critical errors
            if strict_mode and has_critical_errors(validation_errors):
                critical_msgs = [
                    str(e)
                    for e in validation_errors
                    if e.severity == ValidationSeverity.CRITICAL
                ]
                raise RuntimeError(
                    f"Critical provider configuration errors (strict mode): "
                    f"{'; '.join(critical_msgs)}"
                )

        # Log active provider configuration
        logger.info(
            f"Embedding provider: {provider_settings.embedding.provider} "
            f"(model: {provider_settings.embedding.model})"
        )
        logger.info(
            f"Summarization provider: {provider_settings.summarization.provider} "
            f"(model: {provider_settings.summarization.model})"
        )
    except Exception as e:
        logger.error(f"Failed to load provider configuration: {e}")
        # Continue with defaults - EmbeddingGenerator will handle provider creation

    if settings.OPENAI_API_KEY:
        os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY

    # Determine mode and resolve paths
    mode = settings.AGENT_BRAIN_MODE
    state_dir = _state_dir  # May be set by run() function

    # If not set via run(), check environment variable (set by CLI subprocess)
    if state_dir is None and settings.AGENT_BRAIN_STATE_DIR:
        state_dir = Path(settings.AGENT_BRAIN_STATE_DIR).resolve()
        logger.info(f"Using state directory from environment: {state_dir}")

    storage_paths: dict[str, Path] | None = None

    if state_dir is not None:
        # Per-project mode with explicit state directory
        mode = "project"

        # Check for stale locks and clean up
        if is_stale(state_dir):
            logger.info(f"Cleaning stale lock in {state_dir}")
            cleanup_stale(state_dir)

        # Acquire exclusive lock
        if not acquire_lock(state_dir):
            raise RuntimeError(
                f"Another Agent Brain instance is already running for {state_dir}"
            )

        # Resolve storage paths (creates directories)
        storage_paths = resolve_storage_paths(state_dir)
        logger.info(f"State directory: {state_dir}")
    elif state_dir is None:
        # Fallback for direct server runs with no explicit state directory.
        # Resolve relative to project root to avoid CWD-relative storage paths.
        try:
            state_dir = resolve_state_dir(Path.cwd())
            storage_paths = resolve_storage_paths(state_dir)
            logger.info(f"Resolved fallback state directory: {state_dir}")
        except Exception as e:
            logger.warning(f"Failed to resolve fallback storage paths: {e}")
            # Guaranteed fallback: use .agent-brain in CWD so state_dir is never None
            state_dir = Path.cwd() / ".agent-brain"
            state_dir.mkdir(parents=True, exist_ok=True)
            storage_paths = resolve_storage_paths(state_dir)
            logger.info(f"Created fallback state directory: {state_dir}")

    # At this point state_dir is guaranteed non-None
    assert state_dir is not None, "state_dir must be resolved by lifespan"
    logger.info(f"Resolved storage paths: state_dir={state_dir}")

    # Warn if stray CWD-relative data dirs from older versions are present.
    # See issue #170 — older versions could leak ./chroma_db and ./bm25_index
    # next to the project root if the singleton getters were hit before
    # lifespan registered the explicit state-dir-resolved instances.
    _warn_about_stray_cwd_data_dirs(state_dir)

    # Determine project root for path validation
    project_root: Path | None = None
    if state_dir is not None:
        # Project root is parent of .agent-brain (depth 1)
        # or 3 levels up from legacy .claude/agent-brain (depth 3)
        from agent_brain_server.storage_paths import LEGACY_STATE_DIR_NAME

        if state_dir.name == ".agent-brain":
            project_root = state_dir.parent
        elif str(state_dir).endswith(LEGACY_STATE_DIR_NAME):
            project_root = state_dir.parent.parent.parent
        else:
            # Custom state dir — use env var or resolve
            env_root = os.environ.get("AGENT_BRAIN_PROJECT_ROOT")
            if env_root:
                project_root = Path(env_root).resolve()
            else:
                project_root = resolve_project_root(state_dir)

    try:
        # Initialize storage backend (Phase 5)
        backend_type = get_effective_backend_type()
        logger.info(f"Storage backend: {backend_type}")

        # Get storage backend instance from factory
        storage_backend = get_storage_backend()
        await storage_backend.initialize()
        app.state.storage_backend = storage_backend
        app.state.backend_type = backend_type
        logger.info("Storage backend initialized")

        # Conditional ChromaDB initialization (only when backend is chroma)
        if backend_type == "chroma":
            # Determine persistence directories
            if storage_paths:
                chroma_dir = str(storage_paths["chroma_db"])
                bm25_dir = str(storage_paths["bm25_index"])
            elif state_dir is not None:
                chroma_dir = str(state_dir / "data" / "chroma_db")
                bm25_dir = str(state_dir / "data" / "bm25_index")
            else:
                # This branch is unreachable: state_dir is always resolved above
                raise RuntimeError(
                    "Storage path resolution failed: state_dir is unexpectedly None"
                )

            # Initialize ChromaDB components
            vector_store = VectorStoreManager(
                persist_dir=chroma_dir,
            )
            await vector_store.initialize()
            # Register the singleton so downstream services that pull
            # through get_vector_store() share this state-dir-resolved
            # instance instead of constructing a CWD-relative one.
            set_vector_store(vector_store)
            app.state.vector_store = vector_store
            logger.info("Vector store initialized")

            # Check embedding compatibility (PROV-07)
            embedding_warning = await check_embedding_compatibility(vector_store)
            if embedding_warning:
                logger.warning(f"Embedding compatibility: {embedding_warning}")
                # Store warning for health endpoint
                app.state.embedding_warning = embedding_warning
            else:
                app.state.embedding_warning = None

            bm25_manager = BM25IndexManager(
                persist_dir=bm25_dir,
            )
            bm25_manager.initialize()
            set_bm25_manager(bm25_manager)
            app.state.bm25_manager = bm25_manager
            logger.info("BM25 index manager initialized")
        else:
            # PostgreSQL or other backend - no ChromaDB components needed
            app.state.vector_store = None
            app.state.bm25_manager = None
            app.state.embedding_warning = None
            logger.info(f"Skipping ChromaDB initialization (backend: {backend_type})")

        # Initialize embedding cache service (Phase 16)
        # Must be initialized BEFORE IndexingService so get_embedding_cache()
        # returns the instance when the first embed call happens.
        from agent_brain_server.services.embedding_cache import (
            EmbeddingCacheService,
            set_embedding_cache,
        )

        if storage_paths:
            cache_db_path = storage_paths["embedding_cache"] / "embeddings.db"
        elif state_dir is not None:
            cache_db_path = state_dir / "embedding_cache" / "embeddings.db"
            cache_db_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            import tempfile

            cache_db_path = (
                Path(tempfile.mkdtemp(prefix="agent-brain-cache-")) / "embeddings.db"
            )

        provider_fingerprint = _build_provider_fingerprint()
        embedding_cache = EmbeddingCacheService(
            db_path=cache_db_path,
            max_mem_entries=settings.EMBEDDING_CACHE_MAX_MEM_ENTRIES,
            max_disk_mb=settings.EMBEDDING_CACHE_MAX_DISK_MB,
            persist_stats=settings.EMBEDDING_CACHE_PERSIST_STATS,
        )
        await embedding_cache.initialize(provider_fingerprint)
        set_embedding_cache(embedding_cache)
        app.state.embedding_cache = embedding_cache
        logger.info("Embedding cache service initialized")

        # Initialize query cache (Phase 17)
        from agent_brain_server.services.query_cache import (
            QueryCacheService,
            set_query_cache,
        )

        query_cache = QueryCacheService(
            ttl=settings.QUERY_CACHE_TTL,
            max_size=settings.QUERY_CACHE_MAX_SIZE,
        )
        set_query_cache(query_cache)
        app.state.query_cache = query_cache
        logger.info(
            "Query cache initialized (TTL=%ds, max_size=%d)",
            settings.QUERY_CACHE_TTL,
            settings.QUERY_CACHE_MAX_SIZE,
        )

        # Load project config for exclude patterns
        exclude_patterns = None
        if state_dir:
            from agent_brain_server.config.settings import load_project_config

            project_config = load_project_config(state_dir)
            exclude_patterns = project_config.get("exclude_patterns")
            if exclude_patterns:
                logger.info(
                    f"Using exclude patterns from config: {exclude_patterns[:3]}..."
                )

        # Initialize FolderManager for indexed folder tracking (Phase 12)
        if state_dir is not None:
            folder_manager_dir = state_dir
        else:
            # No state directory — use a temp dir (in-memory equivalent)
            import tempfile

            folder_manager_dir = Path(tempfile.mkdtemp(prefix="agent-brain-folders-"))
        folder_manager = FolderManager(state_dir=folder_manager_dir)
        await folder_manager.initialize()
        app.state.folder_manager = folder_manager
        logger.info("Folder manager initialized")

        # Create document loader with exclude patterns
        from agent_brain_server.indexing import DocumentLoader

        document_loader = DocumentLoader(exclude_patterns=exclude_patterns)

        # Initialize ManifestTracker for incremental indexing (Phase 14)
        manifest_tracker = None
        if storage_paths and "manifests" in storage_paths:
            from agent_brain_server.services.manifest_tracker import ManifestTracker

            manifest_tracker = ManifestTracker(manifests_dir=storage_paths["manifests"])
            logger.info("Manifest tracker initialized")
        elif state_dir is not None:
            from agent_brain_server.services.manifest_tracker import ManifestTracker

            manifest_tracker = ManifestTracker(manifests_dir=state_dir / "manifests")
            logger.info("Manifest tracker initialized (fallback)")

        # Create indexing service with storage_backend (Phase 9)
        indexing_service = IndexingService(
            storage_backend=storage_backend,
            document_loader=document_loader,
            folder_manager=folder_manager,
            manifest_tracker=manifest_tracker,
        )
        app.state.indexing_service = indexing_service

        # Create query service with storage_backend (Phase 9)
        query_service = QueryService(
            storage_backend=storage_backend,
            query_cache=query_cache,
        )
        app.state.query_service = query_service

        # Initialize job queue system (Feature 115)
        if state_dir is not None:
            # Initialize job queue store
            job_store = JobQueueStore(state_dir)
            await job_store.initialize()
            logger.info("Job queue store initialized")

            # Initialize job queue service
            job_service = JobQueueService(
                store=job_store,
                project_root=project_root,
            )
            app.state.job_service = job_service
            logger.info("Job queue service initialized")

            # Initialize and start job worker
            _job_worker = JobWorker(
                job_store=job_store,
                indexing_service=indexing_service,
                max_runtime_seconds=settings.AGENT_BRAIN_JOB_TIMEOUT,
                progress_checkpoint_interval=settings.AGENT_BRAIN_CHECKPOINT_INTERVAL,
            )
            await _job_worker.start()
            logger.info("Job worker started")

            # Initialize and start file watcher service (Phase 15)
            from agent_brain_server.services.file_watcher_service import (
                FileWatcherService,
            )

            _file_watcher = FileWatcherService(
                folder_manager=folder_manager,
                job_service=job_service,
                default_debounce_seconds=settings.AGENT_BRAIN_WATCH_DEBOUNCE_SECONDS,
            )
            await _file_watcher.start()
            app.state.file_watcher_service = _file_watcher
            logger.info("File watcher service started")

            # Wire JobWorker to FileWatcherService and FolderManager (Phase 15-02)
            _job_worker.set_file_watcher_service(_file_watcher)
            _job_worker.set_folder_manager(folder_manager)
            # Wire JobWorker to QueryCacheService (Phase 17)
            _job_worker.set_query_cache(query_cache)
        else:
            # No state directory - create minimal job service for backward compat
            # Jobs will not be persisted in this mode
            logger.warning(
                "No state directory configured - job queue persistence disabled"
            )
            # Create in-memory store with temp directory
            import tempfile

            temp_dir = Path(tempfile.mkdtemp(prefix="agent-brain-"))
            job_store = JobQueueStore(temp_dir)
            await job_store.initialize()

            job_service = JobQueueService(
                store=job_store,
                project_root=project_root,
            )
            app.state.job_service = job_service

            _job_worker = JobWorker(
                job_store=job_store,
                indexing_service=indexing_service,
                max_runtime_seconds=settings.AGENT_BRAIN_JOB_TIMEOUT,
                progress_checkpoint_interval=settings.AGENT_BRAIN_CHECKPOINT_INTERVAL,
            )
            await _job_worker.start()

            # Initialize and start file watcher service (Phase 15, no-state-dir branch)
            from agent_brain_server.services.file_watcher_service import (
                FileWatcherService,
            )

            _file_watcher = FileWatcherService(
                folder_manager=folder_manager,
                job_service=job_service,
                default_debounce_seconds=settings.AGENT_BRAIN_WATCH_DEBOUNCE_SECONDS,
            )
            await _file_watcher.start()
            app.state.file_watcher_service = _file_watcher

            # Wire JobWorker to FileWatcherService and FolderManager (Phase 15-02)
            _job_worker.set_file_watcher_service(_file_watcher)
            _job_worker.set_folder_manager(folder_manager)
            # Wire JobWorker to QueryCacheService (Phase 17)
            _job_worker.set_query_cache(query_cache)

        # Kuzu graph store preflight (Issue #166): proactively open the
        # Kuzu DB so corruption from a prior kill-mid-write is detected and
        # self-healed at startup, rather than failing the first user
        # indexing job. No-op when GraphRAG is disabled or store_type !=
        # "kuzu". Runs in a thread because kuzu.Database() is sync I/O.
        try:
            from agent_brain_server.storage.graph_store import (
                get_graph_store_manager,
            )

            graph_store_mgr = get_graph_store_manager()
            preflight_ok = await asyncio.to_thread(graph_store_mgr.preflight_check)
            if preflight_ok:
                logger.info(
                    "Kuzu graph store preflight: OK " "(entities=%d, relationships=%d)",
                    graph_store_mgr.entity_count,
                    graph_store_mgr.relationship_count,
                )
        except Exception as preflight_exc:  # pragma: no cover - defensive
            # Preflight is best-effort. A failure here means recovery
            # couldn't complete; surface it but don't block startup so the
            # user can still hit /health and run `agent-brain doctor --fix`.
            logger.error(
                "Kuzu graph store preflight failed: %s. Server will start "
                "but graph operations may fail until you run "
                "`agent-brain doctor --fix`.",
                preflight_exc,
            )

        # Set multi-instance metadata on app.state for health endpoint
        app.state.mode = mode
        app.state.instance_id = _runtime_state.instance_id if _runtime_state else None
        app.state.project_id = _runtime_state.project_id if _runtime_state else None
        app.state.active_projects = None  # For shared mode (future)
        app.state.strict_mode = strict_mode

    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        # Clean up lock if we acquired it
        if state_dir is not None:
            release_lock(state_dir)
        raise

    yield

    logger.info("Shutting down Agent Brain RAG server...")

    # Stop file watcher service BEFORE job worker (Phase 15)
    if _file_watcher is not None:
        from agent_brain_server.services.file_watcher_service import FileWatcherService

        if isinstance(_file_watcher, FileWatcherService):
            await _file_watcher.stop()
            logger.info("File watcher service stopped")
        _file_watcher = None

    # Stop job worker gracefully
    if _job_worker is not None:
        await _job_worker.stop()
        logger.info("Job worker stopped")
        _job_worker = None

    # Reset query cache singleton (Phase 17)
    from agent_brain_server.services.query_cache import reset_query_cache

    reset_query_cache()

    # Close storage backend if it has a close method (PostgreSQL pool)
    shutdown_backend = getattr(app.state, "storage_backend", None)
    if shutdown_backend is not None and hasattr(shutdown_backend, "close"):
        await shutdown_backend.close()
        logger.info("Storage backend connection pool closed")

    # Cleanup for per-project mode
    if state_dir is not None:
        delete_runtime(state_dir)
        release_lock(state_dir)
        logger.info(f"Released lock and cleaned up state in {state_dir}")


# Create FastAPI application
app = FastAPI(
    title="Agent Brain RAG API",
    description=(
        "RAG-based document indexing and semantic search API. "
        "Index documents from folders and query them using natural language."
    ),
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router, prefix="/health", tags=["Health"])
app.include_router(index_router, prefix="/index", tags=["Indexing"])
app.include_router(cache_router, prefix="/index/cache", tags=["Cache"])
app.include_router(folders_router, prefix="/index/folders", tags=["Folders"])
app.include_router(jobs_router, prefix="/index/jobs", tags=["Jobs"])
app.include_router(query_router, prefix="/query", tags=["Querying"])


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    """Root endpoint redirects to docs."""
    return {
        "name": "Agent Brain RAG API",
        "version": __version__,
        "docs": "/docs",
        "health": "/health",
    }


def _find_free_port() -> int:
    """Find a free port by binding to port 0.

    Returns:
        An available port number.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port  # type: ignore[no-any-return]


def run(
    host: str | None = None,
    port: int | None = None,
    reload: bool | None = None,
    state_dir: str | None = None,
) -> None:
    """Run the server using uvicorn.

    Args:
        host: Host to bind to (default: from settings)
        port: Port to bind to (default: from settings, 0 = auto-assign)
        reload: Enable auto-reload (default: from DEBUG setting)
        state_dir: State directory for per-project mode (enables locking)
    """
    global _runtime_state, _state_dir

    resolved_host = host or settings.API_HOST
    resolved_port = port if port is not None else settings.API_PORT

    # Handle port 0: find a free port
    if resolved_port == 0:
        resolved_port = _find_free_port()
        logger.info(f"Auto-assigned port: {resolved_port}")

    # Set up per-project mode if state_dir specified
    if state_dir:
        _state_dir = Path(state_dir).resolve()

        # Determine project root from state dir layout
        if _state_dir.name == ".agent-brain":
            _project_root = str(_state_dir.parent)
        else:
            # Legacy .claude/agent-brain or custom path
            env_root = os.environ.get("AGENT_BRAIN_PROJECT_ROOT")
            _project_root = env_root or str(_state_dir.parent.parent.parent)

        # Create runtime state
        _runtime_state = RuntimeState(
            mode="project",
            project_root=_project_root,
            bind_host=resolved_host,
            port=resolved_port,
            pid=os.getpid(),
            base_url=f"http://{resolved_host}:{resolved_port}",
        )

        # Write runtime.json before starting server
        # Note: Lock is acquired in lifespan, but we write runtime early
        # for port discovery by CLI tools
        _state_dir.mkdir(parents=True, exist_ok=True)
        write_runtime(_state_dir, _runtime_state)
        logger.info(f"Per-project mode enabled: {_state_dir}")

    # UDS branch — wire AGENT_BRAIN_UDS / _UDS_ONLY env vars from
    # `agent-brain start --uds` through to the uds_bind helpers (plan §5,
    # Phase 7 fix for reviewer finding A1).
    uds_only_env = os.environ.get("AGENT_BRAIN_UDS_ONLY", "0") == "1"
    uds_env = uds_only_env or os.environ.get("AGENT_BRAIN_UDS", "0") == "1"

    if uds_env:
        uds_path_env = os.environ.get("AGENT_BRAIN_UDS_PATH")
        if uds_path_env:
            requested_socket: Path | None = Path(uds_path_env).expanduser()
        else:
            requested_socket = None

        if _state_dir is None:
            if requested_socket is None:
                raise RuntimeError(
                    "UDS requested (AGENT_BRAIN_UDS=1) but neither "
                    "AGENT_BRAIN_UDS_PATH nor --state-dir was provided; "
                    "refusing to guess at the socket location."
                )
            socket_path = requested_socket
            used_fallback = False
        else:
            socket_path, used_fallback = uds_bind.resolve_bind_path(
                _state_dir, requested_socket
            )

        socket_path.parent.mkdir(parents=True, exist_ok=True)
        # Pre-emptively chmod the parent dir to satisfy validate_socket().
        try:
            os.chmod(socket_path.parent, 0o700)
        except OSError as exc:
            logger.warning("Failed to chmod parent dir 0o700: %s", exc)

        if used_fallback:
            logger.info(
                "Long-path fallback: binding UDS at %s (pointer in %s)",
                socket_path,
                _state_dir,
            )

        if uds_only_env:
            logger.info("Binding UDS only at %s", socket_path)
            asyncio.run(uds_bind.serve_uds_only(app, socket_path=socket_path))
        else:
            logger.info(
                "Dual-binding TCP %s:%s + UDS %s",
                resolved_host,
                resolved_port,
                socket_path,
            )
            asyncio.run(
                uds_bind.serve_dual(
                    app,
                    host=resolved_host,
                    port=resolved_port,
                    socket_path=socket_path,
                )
            )
        return

    uvicorn.run(
        "agent_brain_server.api.main:app",
        host=resolved_host,
        port=resolved_port,
        reload=reload if reload is not None else settings.DEBUG,
    )


@click.command()
@click.version_option(version=__version__, prog_name="agent-brain-serve")
@click.option(
    "--host",
    "-h",
    default=None,
    help=f"Host to bind to (default: {settings.API_HOST})",
)
@click.option(
    "--port",
    "-p",
    type=int,
    default=None,
    help=f"Port to bind to (default: {settings.API_PORT}, 0 = auto-assign)",
)
@click.option(
    "--reload/--no-reload",
    default=None,
    help=f"Enable auto-reload (default: {'enabled' if settings.DEBUG else 'disabled'})",
)
@click.option(
    "--state-dir",
    "-s",
    default=None,
    help="State directory for per-project mode (enables locking and runtime.json)",
)
@click.option(
    "--project-dir",
    "-d",
    default=None,
    help="Project directory (auto-resolves state-dir to .agent-brain)",
)
def cli(
    host: str | None,
    port: int | None,
    reload: bool | None,
    state_dir: str | None,
    project_dir: str | None,
) -> None:
    """Agent Brain RAG Server - Document indexing and semantic search API.

    Start the FastAPI server for document indexing and querying.

    \b
    Examples:
      agent-brain-serve                           # Start with default settings
      agent-brain-serve --port 8080               # Start on port 8080
      agent-brain-serve --port 0                  # Auto-assign an available port
      agent-brain-serve --host 0.0.0.0            # Bind to all interfaces
      agent-brain-serve --reload                  # Enable auto-reload
      agent-brain-serve --project-dir /my/project # Per-project mode
      agent-brain-serve --state-dir /path/.agent-brain          # Explicit state dir

    \b
    Environment Variables:
      API_HOST                Server host (default: 127.0.0.1)
      API_PORT                Server port (default: 8000)
      DEBUG                   Enable debug mode (default: false)
      AGENT_BRAIN_STATE_DIR   Override state directory
      AGENT_BRAIN_MODE        Instance mode: 'project' or 'shared'
    """
    # Resolve state directory from options
    resolved_state_dir = state_dir

    if project_dir and not state_dir:
        # Auto-resolve state-dir from project directory
        project_root = resolve_project_root(Path(project_dir))
        resolved_state_dir = str(resolve_state_dir(project_root))
    elif settings.AGENT_BRAIN_STATE_DIR and not state_dir:
        # Use environment variable if set
        resolved_state_dir = settings.AGENT_BRAIN_STATE_DIR

    run(host=host, port=port, reload=reload, state_dir=resolved_state_dir)


if __name__ == "__main__":
    cli()
