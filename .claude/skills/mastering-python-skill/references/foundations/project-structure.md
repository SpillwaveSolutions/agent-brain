# Modern Project Structure and Organization

## Contents

- [Quick Snippets](#quick-snippets)
- [Core Concepts](#core-concepts)
- [Production Examples](#production-examples)
  - [Example 1: Standard Project Layout](#example-1-standard-project-layout)
  - [Example 2: Configuration with Pydantic Settings](#example-2-configuration-with-pydantic-settings)
  - [Example 3: Entry Points and CLI](#example-3-entry-points-and-cli)
  - [Example 4: pyproject.toml Configuration](#example-4-pyprojecttoml-configuration)
- [Common Patterns](#common-patterns)
- [Pitfalls to Avoid](#pitfalls-to-avoid)
- [See Also](#see-also)

---

## Quick Snippets

| Task | Command/Pattern |
|------|-----------------|
| Create venv | `python -m venv .venv` |
| Activate (Unix) | `source .venv/bin/activate` |
| Activate (Windows) | `.venv\Scripts\activate` |
| Install editable | `pip install -e .` |
| Poetry new project | `poetry new myproject` |
| Poetry init existing | `poetry init` |
| Load .env | `from dotenv import load_dotenv; load_dotenv()` |

---

## Core Concepts

A well-structured Python project separates concerns into distinct areas:
- **src/** layout isolates package code from project files
- **tests/** keeps tests separate from implementation
- **pyproject.toml** centralizes all configuration (PEP 517/518)
- **Configuration** lives in `.env` files or environment variables

Benefits of proper structure:
- Reduced onboarding time for new developers
- Improved testability with clear boundaries
- Simplified CI/CD automation
- Future-proofing for tool evolution

---

## Production Examples

### Example 1: Standard Project Layout

**Use case**: Organize a Python package for maintainability and distribution.

```
myproject/
├── src/                      # Source code directory (src layout)
│   └── myproject/            # Main package
│       ├── __init__.py       # Package initialization
│       ├── __main__.py       # Enables: python -m myproject
│       ├── cli.py            # Command-line interface
│       ├── config.py         # Configuration management
│       ├── core/             # Core business logic
│       │   ├── __init__.py
│       │   ├── models.py
│       │   └── services.py
│       └── utils/            # Utility functions
│           ├── __init__.py
│           └── helpers.py
├── tests/                    # Test directory (mirrors src structure)
│   ├── __init__.py
│   ├── conftest.py           # Shared pytest fixtures
│   ├── test_cli.py
│   └── core/
│       ├── __init__.py
│       └── test_models.py
├── docs/                     # Documentation
│   └── README.md
├── scripts/                  # Development/deployment scripts
│   └── setup_dev.sh
├── .env.example              # Example environment variables
├── .gitignore
├── LICENSE
├── README.md
├── pyproject.toml            # Project configuration (PEP 517/518)
└── Makefile                  # Common development tasks
```

**Package `__init__.py`:**

```python
#!/usr/bin/env python3
"""MyProject - A well-structured Python package.

This module exposes the public API of the package.
"""

from myproject.core.models import User, Order
from myproject.core.services import process_order

__version__ = "0.1.0"
__all__ = ["User", "Order", "process_order", "__version__"]
```

**Package `__main__.py`:**

```python
#!/usr/bin/env python3
"""Enable running the package with: python -m myproject"""

from myproject.cli import main

if __name__ == "__main__":
    main()
```

**Key points**:
- The `src/` layout prevents accidental imports from project root
- `__all__` explicitly defines the public API
- `__main__.py` enables `python -m myproject` execution

---

### Example 2: Configuration with Pydantic Settings

**Use case**: Type-safe configuration from environment variables and .env files.

```python
#!/usr/bin/env python3
"""Configuration management with Pydantic Settings v2.

Loads settings from environment variables with validation,
type conversion, and sensible defaults.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database connection settings."""

    model_config = SettingsConfigDict(
        env_prefix="DB_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    url: str = "sqlite:///./app.db"
    pool_size: int = Field(default=5, ge=1, le=100)
    pool_timeout: float = Field(default=30.0, gt=0)
    echo: bool = False  # Log SQL queries


class AppSettings(BaseSettings):
    """Application-wide settings."""

    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # Application info
    name: str = "MyProject"
    version: str = "0.1.0"
    debug: bool = False

    # Environment
    environment: Literal["development", "staging", "production"] = "development"

    # Security
    secret_key: SecretStr
    api_key: SecretStr | None = None

    # Logging
    log_level: str = Field(default="INFO")

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Ensure log level is valid."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper_v = v.upper()
        if upper_v not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return upper_v


class Settings(BaseSettings):
    """Root settings combining all configuration sections."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra env vars
    )

    app: AppSettings = Field(default_factory=AppSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    Using lru_cache ensures settings are only loaded once,
    improving performance and consistency.
    """
    return Settings()


# Usage example
if __name__ == "__main__":
    settings = get_settings()

    print(f"App: {settings.app.name} v{settings.app.version}")
    print(f"Environment: {settings.app.environment}")
    print(f"Debug: {settings.app.debug}")
    print(f"Log Level: {settings.app.log_level}")
    print(f"Database URL: {settings.database.url}")
    print(f"Pool Size: {settings.database.pool_size}")

    # SecretStr hides value in output
    print(f"Secret Key: {settings.app.secret_key}")
    # To get the actual value:
    # settings.app.secret_key.get_secret_value()
```

**Example `.env` file:**

```bash
# .env - Environment-specific settings (DO NOT COMMIT)
APP_ENVIRONMENT=development
APP_DEBUG=true
APP_SECRET_KEY=your-secret-key-here
APP_LOG_LEVEL=DEBUG

DB_URL=postgresql://user:pass@localhost:5432/mydb
DB_POOL_SIZE=10
DB_ECHO=true
```

**Example `.env.example` file:**

```bash
# .env.example - Template for required environment variables
# Copy to .env and fill in values

APP_ENVIRONMENT=development
APP_DEBUG=false
APP_SECRET_KEY=generate-a-secure-key
APP_LOG_LEVEL=INFO

DB_URL=sqlite:///./app.db
DB_POOL_SIZE=5
```

**Key points**:
- Use `@lru_cache` to avoid reloading settings
- `SecretStr` hides sensitive values from logs
- Prefix env vars by section (`APP_`, `DB_`) for organization
- Provide `.env.example` as a template (commit this, not `.env`)

---

### Example 3: Entry Points and CLI

**Use case**: Create installable command-line tools with Click.

```python
#!/usr/bin/env python3
"""Command-line interface using Click.

Provides a clean CLI with subcommands, options, and help text.
"""

import sys
from pathlib import Path

import click

from myproject import __version__
from myproject.config import get_settings
from myproject.core.services import process_data


@click.group()
@click.version_option(version=__version__, prog_name="myproject")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """MyProject - A tool for processing data.

    Run 'myproject COMMAND --help' for command-specific help.
    """
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["settings"] = get_settings()


@cli.command()
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output", "-o",
    type=click.Path(path_type=Path),
    default=None,
    help="Output file path (default: stdout)"
)
@click.option(
    "--format", "-f",
    type=click.Choice(["json", "csv", "yaml"]),
    default="json",
    help="Output format"
)
@click.pass_context
def process(
    ctx: click.Context,
    input_file: Path,
    output: Path | None,
    format: str
) -> None:
    """Process an input file and generate output.

    INPUT_FILE: Path to the file to process
    """
    verbose = ctx.obj["verbose"]

    if verbose:
        click.echo(f"Processing: {input_file}")
        click.echo(f"Format: {format}")

    try:
        result = process_data(input_file, output_format=format)

        if output:
            output.write_text(result)
            click.echo(f"Output written to: {output}")
        else:
            click.echo(result)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def config(ctx: click.Context) -> None:
    """Display current configuration."""
    settings = ctx.obj["settings"]

    click.echo("Current Configuration:")
    click.echo(f"  Environment: {settings.app.environment}")
    click.echo(f"  Debug: {settings.app.debug}")
    click.echo(f"  Log Level: {settings.app.log_level}")
    click.echo(f"  Database: {settings.database.url}")


@cli.command()
@click.option("--check", is_flag=True, help="Check health without fixing")
@click.pass_context
def health(ctx: click.Context, check: bool) -> None:
    """Check application health status."""
    verbose = ctx.obj["verbose"]

    checks = [
        ("Configuration", True),
        ("Database", True),
        ("External Services", True),
    ]

    all_ok = True
    for name, status in checks:
        icon = "✓" if status else "✗"
        color = "green" if status else "red"
        click.echo(click.style(f"  {icon} {name}", fg=color))
        if not status:
            all_ok = False

    if all_ok:
        click.echo(click.style("\nAll checks passed!", fg="green"))
    else:
        click.echo(click.style("\nSome checks failed!", fg="red"))
        sys.exit(1)


def main() -> None:
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
```

**Key points**:
- Use `@click.group()` for subcommands
- Pass context with `@click.pass_context` for shared state
- Use `click.Path(path_type=Path)` for typed path arguments
- Exit with non-zero status on errors

---

### Example 4: pyproject.toml Configuration

**Use case**: Centralize all project configuration in a single file.

```toml
# pyproject.toml - Project configuration (PEP 517/518)

[build-system]
requires = ["poetry-core>=1.0.0"]
build-backend = "poetry.core.masonry.api"

[tool.poetry]
name = "myproject"
version = "0.1.0"
description = "A well-structured Python project"
authors = ["Your Name <you@example.com>"]
license = "MIT"
readme = "README.md"
homepage = "https://github.com/username/myproject"
repository = "https://github.com/username/myproject"
documentation = "https://myproject.readthedocs.io"
keywords = ["python", "example", "project"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.12",
]
packages = [{ include = "myproject", from = "src" }]

[tool.poetry.dependencies]
python = "^3.12"
click = "^8.1.0"
pydantic = "^2.5.0"
pydantic-settings = "^2.1.0"

[tool.poetry.group.dev.dependencies]
pytest = "^8.0.0"
pytest-cov = "^4.1.0"
ruff = "^0.1.0"
mypy = "^1.7.0"
pre-commit = "^3.6.0"

[tool.poetry.scripts]
myproject = "myproject.cli:main"

# Ruff configuration
[tool.ruff]
line-length = 88
target-version = "py312"
src = ["src", "tests"]

[tool.ruff.lint]
select = [
    "E",     # pycodestyle errors
    "F",     # pyflakes
    "I",     # isort
    "B",     # flake8-bugbear
    "C4",    # flake8-comprehensions
    "UP",    # pyupgrade
    "ARG",   # flake8-unused-arguments
    "SIM",   # flake8-simplify
]
ignore = ["E501"]  # Line too long (handled by formatter)

[tool.ruff.lint.isort]
known-first-party = ["myproject"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"

# Mypy configuration
[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true
plugins = ["pydantic.mypy"]

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false

# Pytest configuration
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
addopts = [
    "--strict-markers",
    "-ra",
    "-q",
]
markers = [
    "slow: marks tests as slow",
    "integration: marks integration tests",
]

# Coverage configuration
[tool.coverage.run]
source = ["src"]
branch = true
omit = ["*/tests/*"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "if __name__ == .__main__.:",
]
fail_under = 80
```

**Key points**:
- `packages = [{ include = "myproject", from = "src" }]` for src layout
- `[tool.poetry.scripts]` defines CLI entry points
- Configure all tools (ruff, mypy, pytest, coverage) in one file
- Use dependency groups for dev/test/docs separation

---

## Common Patterns

### Pattern: Makefile for Common Tasks
```makefile
.PHONY: install test lint format clean

install:
	poetry install

test:
	poetry run pytest

lint:
	poetry run ruff check .
	poetry run mypy src/

format:
	poetry run ruff format .
	poetry run ruff check --fix .

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
```

### Pattern: conftest.py for Shared Fixtures
```python
# tests/conftest.py
import pytest
from myproject.config import Settings

@pytest.fixture
def settings():
    """Provide test settings."""
    return Settings(
        app={"environment": "testing", "debug": True},
        database={"url": "sqlite:///:memory:"},
    )

@pytest.fixture
def client(settings):
    """Provide test client."""
    from myproject.app import create_app
    app = create_app(settings)
    return app.test_client()
```

---

## Pitfalls to Avoid

**Don't do this:**
```python
# Hardcoded configuration in code
DATABASE_URL = "postgresql://user:password@localhost/db"
API_KEY = "sk_live_abc123"
```

**Do this instead:**
```python
# Load from environment with validation
from myproject.config import get_settings

settings = get_settings()
database_url = settings.database.url
api_key = settings.app.api_key.get_secret_value()
```

---

**Don't do this:**
```
# Flat project structure
myproject/
├── main.py
├── utils.py
├── models.py
├── test_main.py      # Tests mixed with code!
└── requirements.txt
```

**Do this instead:**
```
# Proper src layout
myproject/
├── src/myproject/    # Package code
├── tests/            # Separate test directory
└── pyproject.toml    # Modern configuration
```

---

## See Also

- [code-quality.md](code-quality.md) - Linting and formatting setup
- [poetry-workflow.md](../packaging/poetry-workflow.md) - Dependency management
- [pyproject-config.md](../packaging/pyproject-config.md) - Deep dive into pyproject.toml
