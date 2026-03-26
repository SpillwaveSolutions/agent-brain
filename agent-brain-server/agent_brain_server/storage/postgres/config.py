"""PostgreSQL backend configuration.

This module provides the PostgresConfig Pydantic model for configuring
PostgreSQL connection parameters, pool sizing, HNSW index tuning, and
full-text search language.
"""

from __future__ import annotations

import urllib.parse

from pydantic import BaseModel, field_validator

# Supported PostgreSQL text search languages
SUPPORTED_LANGUAGES = frozenset(
    {
        "english",
        "spanish",
        "french",
        "german",
        "italian",
        "portuguese",
        "russian",
        "simple",
    }
)


class PostgresConfig(BaseModel):
    """Configuration for PostgreSQL storage backend.

    Provides connection parameters, pool sizing, HNSW index tuning, and
    full-text search configuration. Supports both field-level configuration
    and DATABASE_URL override.

    Attributes:
        host: PostgreSQL host address.
        port: PostgreSQL port number (1-65535).
        database: Database name.
        user: Database user.
        password: Database password (empty for local dev).
        pool_size: Connection pool size.
        pool_max_overflow: Max overflow connections beyond pool_size.
        pool_timeout: Seconds to wait for a connection from the pool.
        language: PostgreSQL tsvector language for full-text search.
        hnsw_m: HNSW index m parameter (max connections per node).
        hnsw_ef_construction: HNSW ef_construction parameter (build quality).
        debug: Enable SQLAlchemy SQL echo logging.
    """

    host: str = "localhost"
    port: int = 5432
    database: str = "agent_brain"
    user: str = "agent_brain"
    password: str = ""
    pool_size: int = 10
    pool_max_overflow: int = 10
    pool_timeout: int = 30
    language: str = "english"
    hnsw_m: int = 16
    hnsw_ef_construction: int = 64
    debug: bool = False

    @field_validator("language", mode="before")
    @classmethod
    def validate_language(cls, v: object) -> str:
        """Validate and normalize tsvector language.

        Args:
            v: Language value to validate.

        Returns:
            Normalized lowercase language string.

        Raises:
            ValueError: If language is not in the supported set.
        """
        val = str(v).lower()
        if val not in SUPPORTED_LANGUAGES:
            raise ValueError(
                f"Unsupported language '{v}'. "
                f"Must be one of: {', '.join(sorted(SUPPORTED_LANGUAGES))}"
            )
        return val

    @field_validator("port", mode="after")
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Validate port is in valid range.

        Args:
            v: Port value to validate.

        Returns:
            Validated port number.

        Raises:
            ValueError: If port is outside 1-65535 range.
        """
        if v < 1 or v > 65535:
            raise ValueError(f"Port must be between 1 and 65535, got {v}")
        return v

    def get_connection_url(self) -> str:
        """Build asyncpg connection URL from config fields.

        URL-encodes the password to handle special characters safely.

        Returns:
            SQLAlchemy-compatible asyncpg connection URL.
        """
        encoded_password = urllib.parse.quote_plus(self.password)
        if encoded_password:
            return (
                f"postgresql+asyncpg://{self.user}:{encoded_password}"
                f"@{self.host}:{self.port}/{self.database}"
            )
        return (
            f"postgresql+asyncpg://{self.user}"
            f"@{self.host}:{self.port}/{self.database}"
        )

    @classmethod
    def from_database_url(cls, url: str) -> PostgresConfig:
        """Parse a DATABASE_URL string into a PostgresConfig.

        Supports standard PostgreSQL connection URLs. The asyncpg scheme
        prefix is stripped if present.

        Args:
            url: Database URL string (e.g.,
                ``postgresql://user:pass@host:5432/dbname`` or
                ``postgresql+asyncpg://user:pass@host:5432/dbname``).

        Returns:
            PostgresConfig instance with parsed connection fields.

        Raises:
            ValueError: If the URL cannot be parsed.
        """
        # Normalize scheme: strip +asyncpg suffix for urlparse
        normalized = url.replace("postgresql+asyncpg://", "postgresql://")
        parsed = urllib.parse.urlparse(normalized)

        if not parsed.hostname:
            raise ValueError(f"Cannot parse host from DATABASE_URL: {url}")

        return cls(
            host=parsed.hostname,
            port=parsed.port or 5432,
            database=(parsed.path or "/agent_brain").lstrip("/") or "agent_brain",
            user=parsed.username or "agent_brain",
            password=urllib.parse.unquote(parsed.password or ""),
        )
