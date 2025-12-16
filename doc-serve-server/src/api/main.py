"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import health_router, index_router, query_router
from ..config import settings
from ..storage import initialize_vector_store

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting Doc-Serve server...")
    try:
        await initialize_vector_store()
        logger.info("Vector store initialized")
    except Exception as e:
        logger.error(f"Failed to initialize vector store: {e}")
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
async def root():
    """Root endpoint redirects to docs."""
    return {
        "name": "Doc-Serve API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


def run():
    """Run the server using uvicorn."""
    uvicorn.run(
        "src.api.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
    )


if __name__ == "__main__":
    run()
