#!/usr/bin/env python3
"""
Configuration Loader CLI

Demonstrates Pydantic settings patterns:
- Environment variable loading
- .env file support
- Type validation and coercion
- Nested configuration
- Secret handling with SecretStr

Usage:
    python config_loader.py
    APP_DEBUG=true APP_LOG_LEVEL=DEBUG python config_loader.py
    python config_loader.py --env-file .env.production
    python config_loader.py --show-secrets  # Show actual secret values

See: ../references/web-apis/pydantic-validation.md
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from pydantic import (
        BaseModel,
        Field,
        SecretStr,
        field_validator,
        model_validator,
    )
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:
    print("Error: pydantic and pydantic-settings not installed.")
    print("Run: pip install pydantic pydantic-settings")
    sys.exit(1)


# ============================================================
# CONFIGURATION MODELS
# ============================================================

class DatabaseSettings(BaseModel):
    """Database configuration."""

    url: str = Field(
        default="sqlite:///./app.db",
        description="Database connection URL",
    )
    pool_size: int = Field(
        default=5,
        ge=1,
        le=100,
        description="Connection pool size",
    )
    pool_timeout: int = Field(
        default=30,
        ge=1,
        description="Pool timeout in seconds",
    )
    echo: bool = Field(
        default=False,
        description="Echo SQL queries (debug)",
    )


class RedisSettings(BaseModel):
    """Redis configuration."""

    host: str = Field(default="localhost")
    port: int = Field(default=6379, ge=1, le=65535)
    db: int = Field(default=0, ge=0)
    password: SecretStr | None = Field(default=None)

    @property
    def url(self) -> str:
        """Build Redis URL."""
        auth = ""
        if self.password:
            auth = f":{self.password.get_secret_value()}@"
        return f"redis://{auth}{self.host}:{self.port}/{self.db}"


class AppSettings(BaseSettings):
    """Application settings loaded from environment."""

    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
        case_sensitive=False,
    )

    # Application settings
    name: str = Field(
        default="MyApp",
        description="Application name",
    )
    version: str = Field(
        default="1.0.0",
        description="Application version",
    )
    environment: str = Field(
        default="development",
        pattern="^(development|staging|production)$",
        description="Runtime environment",
    )
    debug: bool = Field(
        default=False,
        description="Debug mode",
    )
    log_level: str = Field(
        default="INFO",
        pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$",
        description="Logging level",
    )

    # Server settings
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8000, ge=1, le=65535)

    # Secrets
    secret_key: SecretStr = Field(
        default=SecretStr("change-me-in-production"),
        description="Secret key for signing",
    )
    api_key: SecretStr | None = Field(
        default=None,
        description="External API key",
    )

    # Nested settings (use APP__DATABASE__URL, APP__REDIS__HOST, etc.)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Normalize environment name."""
        return v.lower()

    @model_validator(mode="after")
    def validate_production(self) -> "AppSettings":
        """Ensure production has proper settings."""
        if self.environment == "production":
            if self.debug:
                raise ValueError("Debug must be disabled in production")
            if self.secret_key.get_secret_value() == "change-me-in-production":
                raise ValueError("Secret key must be changed in production")
        return self

    def to_safe_dict(self, show_secrets: bool = False) -> dict[str, Any]:
        """Convert to dict, optionally masking secrets."""
        data = self.model_dump()

        if not show_secrets:
            # Mask secret values
            data["secret_key"] = "***" if self.secret_key else None
            data["api_key"] = "***" if self.api_key else None
            if data["redis"]["password"]:
                data["redis"]["password"] = "***"

        return data


# ============================================================
# CLI
# ============================================================

def load_settings(env_file: str | None = None) -> AppSettings:
    """Load settings with optional custom env file."""
    if env_file:
        # Temporarily override env file
        class CustomSettings(AppSettings):
            model_config = SettingsConfigDict(
                env_prefix="APP_",
                env_file=env_file,
                env_file_encoding="utf-8",
                env_nested_delimiter="__",
                extra="ignore",
            )

        return CustomSettings()

    return AppSettings()


def print_settings(settings: AppSettings, show_secrets: bool = False) -> None:
    """Print settings in a readable format."""
    data = settings.to_safe_dict(show_secrets=show_secrets)

    print("=" * 60)
    print("APPLICATION SETTINGS")
    print("=" * 60)
    print()

    # Basic settings
    print("General:")
    print(f"  Name:        {data['name']}")
    print(f"  Version:     {data['version']}")
    print(f"  Environment: {data['environment']}")
    print(f"  Debug:       {data['debug']}")
    print(f"  Log Level:   {data['log_level']}")
    print()

    # Server
    print("Server:")
    print(f"  Host: {data['host']}")
    print(f"  Port: {data['port']}")
    print()

    # Secrets
    print("Secrets:")
    print(f"  Secret Key: {data['secret_key']}")
    print(f"  API Key:    {data['api_key'] or '(not set)'}")
    print()

    # Database
    print("Database:")
    print(f"  URL:          {data['database']['url']}")
    print(f"  Pool Size:    {data['database']['pool_size']}")
    print(f"  Pool Timeout: {data['database']['pool_timeout']}s")
    print(f"  Echo SQL:     {data['database']['echo']}")
    print()

    # Redis
    print("Redis:")
    print(f"  Host:     {data['redis']['host']}")
    print(f"  Port:     {data['redis']['port']}")
    print(f"  DB:       {data['redis']['db']}")
    print(f"  Password: {data['redis']['password'] or '(not set)'}")
    print()


def print_json(settings: AppSettings, show_secrets: bool = False) -> None:
    """Print settings as JSON."""
    data = settings.to_safe_dict(show_secrets=show_secrets)
    print(json.dumps(data, indent=2, default=str))


def print_env_vars() -> None:
    """Print example environment variables."""
    print("=" * 60)
    print("ENVIRONMENT VARIABLES")
    print("=" * 60)
    print()
    print("Set these environment variables or add to .env file:")
    print()
    print("# Basic settings")
    print("APP_NAME=MyApp")
    print("APP_VERSION=1.0.0")
    print("APP_ENVIRONMENT=development  # development|staging|production")
    print("APP_DEBUG=false")
    print("APP_LOG_LEVEL=INFO  # DEBUG|INFO|WARNING|ERROR|CRITICAL")
    print()
    print("# Server")
    print("APP_HOST=127.0.0.1")
    print("APP_PORT=8000")
    print()
    print("# Secrets")
    print("APP_SECRET_KEY=your-secret-key-here")
    print("APP_API_KEY=optional-api-key")
    print()
    print("# Database (nested with double underscore)")
    print("APP__DATABASE__URL=postgresql://user:pass@localhost/db")
    print("APP__DATABASE__POOL_SIZE=10")
    print("APP__DATABASE__POOL_TIMEOUT=30")
    print("APP__DATABASE__ECHO=false")
    print()
    print("# Redis")
    print("APP__REDIS__HOST=localhost")
    print("APP__REDIS__PORT=6379")
    print("APP__REDIS__DB=0")
    print("APP__REDIS__PASSWORD=optional-password")
    print()


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Load and display application configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                           # Show current config
  %(prog)s --json                    # Output as JSON
  %(prog)s --show-secrets            # Show actual secret values
  %(prog)s --env-file .env.prod      # Use specific env file
  %(prog)s --show-env                # Show example env vars

  # With environment variables:
  APP_DEBUG=true APP_LOG_LEVEL=DEBUG %(prog)s
        """,
    )

    parser.add_argument(
        "--env-file",
        type=str,
        default=None,
        help="Path to .env file (default: .env)",
    )

    parser.add_argument(
        "--show-secrets",
        action="store_true",
        help="Show actual secret values (not masked)",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )

    parser.add_argument(
        "--show-env",
        action="store_true",
        help="Show example environment variables",
    )

    args = parser.parse_args()

    if args.show_env:
        print_env_vars()
        return 0

    try:
        settings = load_settings(args.env_file)

        if args.json:
            print_json(settings, show_secrets=args.show_secrets)
        else:
            print_settings(settings, show_secrets=args.show_secrets)

        return 0

    except Exception as e:
        print(f"Error loading configuration: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
