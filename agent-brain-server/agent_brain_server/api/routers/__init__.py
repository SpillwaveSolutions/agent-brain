"""API routers for different endpoint groups."""

from .folders import router as folders_router
from .health import router as health_router
from .index import router as index_router
from .jobs import router as jobs_router
from .query import router as query_router

__all__ = [
    "folders_router",
    "health_router",
    "index_router",
    "jobs_router",
    "query_router",
]
