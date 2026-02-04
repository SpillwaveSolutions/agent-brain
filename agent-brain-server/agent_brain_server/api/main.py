"""FastAPI application entry point.

This module provides the Agent Brain RAG server, a FastAPI application
for document indexing and semantic search.

Note: This server assumes a single uvicorn worker process. If running
multiple workers, ensure only one worker handles indexing jobs by using
the single-worker model or a separate job processor service.
"""

import logging
import os
import socket
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import click
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agent_brain_server import __version__
from agent_brain_server.config import settings
from agent_brain_server.config.provider_config import (
    clear_settings_cache,
    load_provider_settings,
    validate_provider_config,
)
from agent_brain_server.indexing.bm25_index import BM25IndexManager
from agent_brain_server.job_queue import JobQueueService, JobQueueStore, JobWorker
from agent_brain_server.locking import (
    acquire_lock,
    cleanup_stale,
    is_stale,
    release_lock,
)
from agent_brain_server.project_root import resolve_project_root
from agent_brain_server.runtime import RuntimeState, delete_runtime, write_runtime
from agent_brain_server.services import IndexingService, QueryService
from agent_brain_server.storage import VectorStoreManager
from agent_brain_server.storage_paths import resolve_state_dir, resolve_storage_paths

from .routers import health_router, index_router, jobs_router, query_router

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Module-level state for multi-instance mode
_runtime_state: Optional[RuntimeState] = None
_state_dir: Optional[Path] = None

# Module-level reference to job worker for cleanup
_job_worker: Optional[JobWorker] = None


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
    global _runtime_state, _state_dir, _job_worker

    logger.info("Starting Agent Brain RAG server...")

    # Load and validate provider configuration
    # Clear cache first to ensure we pick up env vars set by CLI
    clear_settings_cache()
    try:
        provider_settings = load_provider_settings()
        validation_errors = validate_provider_config(provider_settings)

        if validation_errors:
            for error in validation_errors:
                logger.warning(f"Provider config warning: {error}")
            # Log but don't fail - providers may work if keys are set later
            # or if using Ollama which doesn't need keys

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

    storage_paths: Optional[dict[str, Path]] = None

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

    # Determine project root for path validation
    project_root: Optional[Path] = None
    if state_dir is not None:
        # Project root is 3 levels up from .claude/agent-brain
        project_root = state_dir.parent.parent.parent

    try:
        # Determine persistence directories
        chroma_dir = (
            str(storage_paths["chroma_db"])
            if storage_paths
            else settings.CHROMA_PERSIST_DIR
        )
        bm25_dir = (
            str(storage_paths["bm25_index"])
            if storage_paths
            else settings.BM25_INDEX_PATH
        )

        # Initialize services and store on app.state for DI
        vector_store = VectorStoreManager(
            persist_dir=chroma_dir,
        )
        await vector_store.initialize()
        app.state.vector_store = vector_store
        logger.info("Vector store initialized")

        bm25_manager = BM25IndexManager(
            persist_dir=bm25_dir,
        )
        bm25_manager.initialize()
        app.state.bm25_manager = bm25_manager
        logger.info("BM25 index manager initialized")

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

        # Create document loader with exclude patterns
        from agent_brain_server.indexing import DocumentLoader

        document_loader = DocumentLoader(exclude_patterns=exclude_patterns)

        # Create indexing service with injected deps
        indexing_service = IndexingService(
            vector_store=vector_store,
            bm25_manager=bm25_manager,
            document_loader=document_loader,
        )
        app.state.indexing_service = indexing_service

        # Create query service with injected deps
        query_service = QueryService(
            vector_store=vector_store,
            bm25_manager=bm25_manager,
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

        # Set multi-instance metadata on app.state for health endpoint
        app.state.mode = mode
        app.state.instance_id = _runtime_state.instance_id if _runtime_state else None
        app.state.project_id = _runtime_state.project_id if _runtime_state else None
        app.state.active_projects = None  # For shared mode (future)

    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        # Clean up lock if we acquired it
        if state_dir is not None:
            release_lock(state_dir)
        raise

    yield

    logger.info("Shutting down Agent Brain RAG server...")

    # Stop job worker gracefully
    if _job_worker is not None:
        await _job_worker.stop()
        logger.info("Job worker stopped")
        _job_worker = None

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
    host: Optional[str] = None,
    port: Optional[int] = None,
    reload: Optional[bool] = None,
    state_dir: Optional[str] = None,
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

        # Create runtime state
        _runtime_state = RuntimeState(
            mode="project",
            project_root=str(_state_dir.parent.parent.parent),  # .claude/agent-brain
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
    help="Project directory (auto-resolves state-dir to .claude/agent-brain)",
)
def cli(
    host: Optional[str],
    port: Optional[int],
    reload: Optional[bool],
    state_dir: Optional[str],
    project_dir: Optional[str],
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
      agent-brain-serve --state-dir /path/.claude/agent-brain  # Explicit state dir

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
