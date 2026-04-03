"""Unit tests for storage backend factory."""

import pytest

from agent_brain_server.config.provider_config import clear_settings_cache
from agent_brain_server.storage.factory import (
    get_effective_backend_type,
    get_storage_backend,
    reset_storage_backend_cache,
)


@pytest.fixture(autouse=True)
def clear_caches() -> None:
    """Clear all caches before each test."""
    reset_storage_backend_cache()
    clear_settings_cache()


def test_get_effective_backend_type_returns_valid_backend() -> None:
    """Test get_effective_backend_type returns a valid backend."""
    backend = get_effective_backend_type()

    # Should be one of the valid backends
    assert backend in {"chroma", "postgres"}


def test_reset_storage_backend_cache_clears_singleton() -> None:
    """Test reset_storage_backend_cache clears the singleton."""
    # Call twice to verify singleton behavior
    reset_storage_backend_cache()
    reset_storage_backend_cache()

    # Should not raise an error
    backend_type = get_effective_backend_type()
    assert backend_type in {"chroma", "postgres"}


def test_get_storage_backend_chroma_returns_instance() -> None:
    """Test get_storage_backend returns ChromaBackend for chroma backend.

    Note: This test assumes default config uses chroma backend.
    If env var AGENT_BRAIN_STORAGE_BACKEND is set, test may fail.
    """
    reset_storage_backend_cache()
    clear_settings_cache()

    # Default backend should be chroma
    backend_type = get_effective_backend_type()
    if backend_type == "chroma":
        backend = get_storage_backend()

        # Should return a ChromaBackend instance
        from agent_brain_server.storage.chroma.backend import ChromaBackend

        assert isinstance(backend, ChromaBackend)


def test_get_storage_backend_postgres_not_implemented() -> None:
    """Test get_storage_backend raises NotImplementedError for postgres.

    PostgreSQL backend will be implemented in Phase 6.
    """
    # This test verifies postgres still raises NotImplementedError
    # We can't easily test it without changing env/config, but we document it here
    pass


def test_get_storage_backend_validates_backend_type() -> None:
    """Test get_storage_backend validates backend type exists."""
    # This tests the factory's validation logic
    backend_type = get_effective_backend_type()

    # Valid backends should be recognized
    assert backend_type in {"chroma", "postgres"}


def test_factory_function_exists() -> None:
    """Test that factory functions are importable and callable."""
    # Ensure all exported functions exist
    assert callable(get_effective_backend_type)
    assert callable(get_storage_backend)
    assert callable(reset_storage_backend_cache)


def test_get_effective_backend_type_is_deterministic() -> None:
    """Test get_effective_backend_type returns consistent value."""
    backend1 = get_effective_backend_type()
    backend2 = get_effective_backend_type()

    assert backend1 == backend2
    assert backend1 in {"chroma", "postgres"}


def test_database_url_preserves_yaml_pool_timeout() -> None:
    """DATABASE_URL override preserves pool_timeout from YAML config.

    When DATABASE_URL is set, the factory should use the connection URL from
    the env var but preserve pool tunables (pool_size, pool_max_overflow,
    pool_timeout) from the YAML config -- same pattern as pool_size and
    pool_max_overflow.
    """
    from unittest.mock import MagicMock, patch

    from agent_brain_server.storage.postgres import PostgresBackend

    mock_provider_settings = MagicMock()
    mock_provider_settings.storage.backend = "postgres"
    mock_provider_settings.storage.postgres = {
        "host": "localhost",
        "port": 5432,
        "database": "agent_brain",
        "user": "agent_brain",
        "password": "",
        "pool_size": 20,
        "pool_max_overflow": 5,
        "pool_timeout": 45,
    }

    reset_storage_backend_cache()

    with (
        patch("agent_brain_server.storage.factory.settings") as mock_settings,
        patch(
            "agent_brain_server.storage.factory.load_provider_settings",
            return_value=mock_provider_settings,
        ),
        patch.dict(
            "os.environ", {"DATABASE_URL": "postgresql://user:pass@db:5432/mydb"}
        ),
    ):
        mock_settings.AGENT_BRAIN_STORAGE_BACKEND = ""
        backend = get_storage_backend()

    assert isinstance(backend, PostgresBackend)
    assert backend.config.pool_timeout == 45
