"""API routers for different endpoint groups."""

from .health import router as health_router
from .index import router as index_router
from .query import router as query_router

__all__ = [
    "health_router",
    "index_router",
    "query_router",
]
