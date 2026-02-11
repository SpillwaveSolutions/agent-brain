"""Unit tests for PostgresConfig Pydantic model."""

from __future__ import annotations

import pytest

from agent_brain_server.storage.postgres.config import (
    SUPPORTED_LANGUAGES,
    PostgresConfig,
)


class TestPostgresConfigDefaults:
    """Tests for PostgresConfig default values."""

    def test_default_host(self) -> None:
        """Default host is localhost."""
        config = PostgresConfig()
        assert config.host == "localhost"

    def test_default_port(self) -> None:
        """Default port is 5432."""
        config = PostgresConfig()
        assert config.port == 5432

    def test_default_database(self) -> None:
        """Default database is agent_brain."""
        config = PostgresConfig()
        assert config.database == "agent_brain"

    def test_default_user(self) -> None:
        """Default user is agent_brain."""
        config = PostgresConfig()
        assert config.user == "agent_brain"

    def test_default_pool_size(self) -> None:
        """Default pool_size is 10."""
        config = PostgresConfig()
        assert config.pool_size == 10

    def test_default_pool_max_overflow(self) -> None:
        """Default pool_max_overflow is 10."""
        config = PostgresConfig()
        assert config.pool_max_overflow == 10

    def test_default_hnsw_m(self) -> None:
        """Default HNSW m is 16."""
        config = PostgresConfig()
        assert config.hnsw_m == 16

    def test_default_hnsw_ef_construction(self) -> None:
        """Default HNSW ef_construction is 64."""
        config = PostgresConfig()
        assert config.hnsw_ef_construction == 64


class TestPostgresConfigConnectionUrl:
    """Tests for get_connection_url()."""

    def test_connection_url_with_password(self) -> None:
        """Connection URL includes encoded password."""
        config = PostgresConfig(
            host="db.example.com",
            port=5433,
            database="mydb",
            user="myuser",
            password="mypass",
        )
        url = config.get_connection_url()
        assert url == (
            "postgresql+asyncpg://myuser:mypass"
            "@db.example.com:5433/mydb"
        )

    def test_connection_url_without_password(self) -> None:
        """Connection URL omits password when empty."""
        config = PostgresConfig(password="")
        url = config.get_connection_url()
        assert ":" not in url.split("@")[0].split("//")[1]
        assert "agent_brain@localhost:5432/agent_brain" in url

    def test_connection_url_encodes_special_chars(self) -> None:
        """Special characters in password are URL-encoded."""
        config = PostgresConfig(password="p@ss:word/123")
        url = config.get_connection_url()
        assert "p%40ss%3Aword%2F123" in url

    def test_custom_field_values(self) -> None:
        """Custom field values override all defaults."""
        config = PostgresConfig(
            host="pg.local",
            port=15432,
            database="test_db",
            user="test_user",
            password="secret",
            pool_size=20,
            pool_max_overflow=5,
            hnsw_m=32,
            hnsw_ef_construction=128,
        )
        assert config.host == "pg.local"
        assert config.port == 15432
        assert config.database == "test_db"
        assert config.user == "test_user"
        assert config.pool_size == 20
        assert config.pool_max_overflow == 5
        assert config.hnsw_m == 32
        assert config.hnsw_ef_construction == 128


class TestPostgresConfigFromDatabaseUrl:
    """Tests for from_database_url() class method."""

    def test_parse_standard_url(self) -> None:
        """Parses standard PostgreSQL URL."""
        config = PostgresConfig.from_database_url(
            "postgresql://user:pass@host.example.com/mydb"
        )
        assert config.host == "host.example.com"
        assert config.user == "user"
        assert config.password == "pass"
        assert config.database == "mydb"
        assert config.port == 5432  # default when not specified

    def test_parse_url_with_port(self) -> None:
        """Parses URL with explicit port."""
        config = PostgresConfig.from_database_url(
            "postgresql://user:pass@db:5433/mydb"
        )
        assert config.port == 5433

    def test_parse_asyncpg_url(self) -> None:
        """Parses asyncpg-scheme URL."""
        config = PostgresConfig.from_database_url(
            "postgresql+asyncpg://user:pass@host:5432/mydb"
        )
        assert config.host == "host"
        assert config.user == "user"


class TestPostgresConfigLanguageValidation:
    """Tests for language field validator."""

    def test_accepts_supported_languages(self) -> None:
        """All supported languages are accepted."""
        for lang in SUPPORTED_LANGUAGES:
            config = PostgresConfig(language=lang)
            assert config.language == lang

    def test_rejects_unsupported_language(self) -> None:
        """Unsupported language raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported language"):
            PostgresConfig(language="klingon")

    def test_language_case_insensitive(self) -> None:
        """Language validation is case-insensitive."""
        config = PostgresConfig(language="ENGLISH")
        assert config.language == "english"


class TestPostgresConfigPortValidation:
    """Tests for port field validator."""

    def test_rejects_port_zero(self) -> None:
        """Port 0 is invalid."""
        with pytest.raises(ValueError, match="Port must be between"):
            PostgresConfig(port=0)

    def test_rejects_port_too_high(self) -> None:
        """Port 65536 is invalid."""
        with pytest.raises(ValueError, match="Port must be between"):
            PostgresConfig(port=65536)

    def test_accepts_port_one(self) -> None:
        """Port 1 is valid (lower bound)."""
        config = PostgresConfig(port=1)
        assert config.port == 1

    def test_accepts_port_max(self) -> None:
        """Port 65535 is valid (upper bound)."""
        config = PostgresConfig(port=65535)
        assert config.port == 65535
