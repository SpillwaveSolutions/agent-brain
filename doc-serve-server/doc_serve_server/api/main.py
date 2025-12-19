"""FastAPI application entry point."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Optional

import click
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from doc_serve_server import __version__
from doc_serve_server.config import settings
from doc_serve_server.indexing import get_bm25_manager
from doc_serve_server.storage import initialize_vector_store

from .routers import health_router, index_router, query_router

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Application lifespan manager.

    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting Doc-Serve server...")

    # Set environment variable for LlamaIndex components
    import os
    if settings.OPENAI_API_KEY:
        os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY

    try:
        await initialize_vector_store()
        logger.info("Vector store initialized")

        # Initialize BM25 index
        bm25_manager = get_bm25_manager()
        bm25_manager.initialize()
        logger.info("BM25 index manager initialized")
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down Doc-Serve server...")


# Create FastAPI application
app = FastAPI(
    title="Doc-Serve API",
    description=(
        "RAG-based document indexing and semantic search API. "
        "Index documents from folders and query them using natural language."
    ),
    version="1.0.0",
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
app.include_router(query_router, prefix="/query", tags=["Querying"])


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    """Root endpoint redirects to docs."""
    return {
        "name": "Doc-Serve API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


def run(
    host: Optional[str] = None,
    port: Optional[int] = None,
    reload: Optional[bool] = None,
) -> None:
    """Run the server using uvicorn.

    Args:
        host: Host to bind to (default: from settings)
        port: Port to bind to (default: from settings)
        reload: Enable auto-reload (default: from DEBUG setting)
    """
    uvicorn.run(
        "doc_serve_server.api.main:app",
        host=host or settings.API_HOST,
        port=port or settings.API_PORT,
        reload=reload if reload is not None else settings.DEBUG,
    )


@click.command()
@click.version_option(version=__version__, prog_name="doc-serve")
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
    help=f"Port to bind to (default: {settings.API_PORT})",
)
@click.option(
    "--reload/--no-reload",
    default=None,
    help=f"Enable auto-reload (default: {'enabled' if settings.DEBUG else 'disabled'})",
)
def cli(host: Optional[str], port: Optional[int], reload: Optional[bool]) -> None:
    """Doc-Serve Server - RAG-based document indexing and semantic search API.

    Start the FastAPI server for document indexing and querying.

    \b
    Examples:
      doc-serve                      # Start with default settings
      doc-serve --port 8080          # Start on port 8080
      doc-serve --host 0.0.0.0       # Bind to all interfaces
      doc-serve --reload             # Enable auto-reload

    \b
    Environment Variables:
      API_HOST    Server host (default: 127.0.0.1)
      API_PORT    Server port (default: 8000)
      DEBUG       Enable debug mode (default: false)
    """
    run(host=host, port=port, reload=reload)


if __name__ == "__main__":
    cli()
