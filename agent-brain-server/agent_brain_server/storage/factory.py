"""Storage backend factory with config-driven selection.

This module provides a factory function that returns the appropriate storage
backend based on configuration (env var > YAML > default).
"""

import logging

from agent_brain_server.config import settings
from agent_brain_server.config.provider_config import load_provider_settings
from agent_brain_server.storage.protocol import StorageBackendProtocol

logger = logging.getLogger(__name__)

# Global singleton instance
_storage_backend: StorageBackendProtocol | None = None
_backend_type: str | None = None


def get_effective_backend_type() -> str:
    """Get the resolved backend type without creating an instance.

    Resolution order:
    1. AGENT_BRAIN_STORAGE_BACKEND env var (if set)
    2. YAML config storage.backend
    3. Default: "chroma"

    Returns:
        Backend type string ("chroma" or "postgres")
    """
    # Check environment variable override first
    env_backend = settings.AGENT_BRAIN_STORAGE_BACKEND
    if env_backend:
        backend = env_backend.lower()
        logger.debug(f"Using storage backend from env var: {backend}")
        return backend

    # Check YAML config
    try:
        provider_settings = load_provider_settings()
        backend = provider_settings.storage.backend
        logger.debug(f"Using storage backend from config.yaml: {backend}")
        return backend
    except Exception as e:
        logger.warning(f"Failed to load provider settings: {e}, using default")
        return "chroma"


def get_storage_backend() -> StorageBackendProtocol:
    """Get the global storage backend instance.

    This function uses a singleton pattern to ensure only one backend
    instance exists per process.

    Returns:
        Storage backend implementation

    Raises:
        ValueError: If backend type is unknown
        NotImplementedError: If backend is not yet implemented
    """
    global _storage_backend, _backend_type

    backend_type = get_effective_backend_type()

    # If we already have a backend of the correct type, return it
    if _storage_backend is not None and _backend_type == backend_type:
        return _storage_backend

    # Validate backend type
    valid_backends = {"chroma", "postgres"}
    if backend_type not in valid_backends:
        raise ValueError(
            f"Unknown storage backend: {backend_type}. "
            f"Valid options: {', '.join(sorted(valid_backends))}"
        )

    # Log which config source was used
    env_backend = settings.AGENT_BRAIN_STORAGE_BACKEND
    if env_backend:
        logger.info(
            f"Using storage backend: {backend_type} "
            f"(from AGENT_BRAIN_STORAGE_BACKEND)"
        )
    else:
        logger.info(f"Using storage backend: {backend_type} (from config.yaml)")

    # Create backend instance based on type
    if backend_type == "chroma":
        from agent_brain_server.storage.chroma.backend import ChromaBackend

        _storage_backend = ChromaBackend()
        _backend_type = backend_type
        return _storage_backend
    elif backend_type == "postgres":
        # PostgresBackend will be implemented in Phase 6
        raise NotImplementedError(
            "PostgresBackend not yet implemented — see Phase 6 (STOR-06). "
            "PostgreSQL backend requires pgvector extension and will provide "
            "async vector search with native BM25 via tsvector."
        )

    # This should never be reached due to validation above
    raise ValueError(f"Unknown storage backend: {backend_type}")


def reset_storage_backend_cache() -> None:
    """Clear the storage backend singleton cache.

    This is primarily used for testing to ensure a fresh backend
    instance is created with different configurations.
    """
    global _storage_backend, _backend_type
    _storage_backend = None
    _backend_type = None
    logger.debug("Storage backend cache cleared")
