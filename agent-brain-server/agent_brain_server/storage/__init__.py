"""Storage layer for vector database and graph operations."""

from .factory import get_effective_backend_type, get_storage_backend, reset_storage_backend_cache
from .graph_store import (
    GraphStoreManager,
    get_graph_store_manager,
    initialize_graph_store,
    reset_graph_store_manager,
)
from .protocol import EmbeddingMetadata, SearchResult, StorageBackendProtocol, StorageError
from .vector_store import VectorStoreManager, get_vector_store, initialize_vector_store

__all__ = [
    # Storage backend protocol (Phase 5)
    "StorageBackendProtocol",
    "SearchResult",
    "EmbeddingMetadata",
    "StorageError",
    "get_storage_backend",
    "get_effective_backend_type",
    "reset_storage_backend_cache",
    # Vector store (legacy, for backward compat)
    "VectorStoreManager",
    "get_vector_store",
    "initialize_vector_store",
    # Graph store (Feature 113)
    "GraphStoreManager",
    "get_graph_store_manager",
    "initialize_graph_store",
    "reset_graph_store_manager",
]
