# Poetry Workflow and Dependency Management

## Contents

- [Quick Snippets](#quick-snippets)
- [Core Concepts](#core-concepts)
- [Production Examples](#production-examples)
  - [Example 1: Project Setup and Configuration](#example-1-project-setup-and-configuration)
  - [Example 2: Managing Dependencies](#example-2-managing-dependencies)
  - [Example 3: Dependency Groups and Environments](#example-3-dependency-groups-and-environments)
  - [Example 4: Publishing to PyPI](#example-4-publishing-to-pypi)
- [Common Patterns](#common-patterns)
- [Pitfalls to Avoid](#pitfalls-to-avoid)
- [See Also](#see-also)

---

## Quick Snippets

| Task | Code |
|------|------|
| Install Poetry | `pipx install poetry` |
| New project | `poetry new my-project` |
| Init existing | `poetry init` |
| Add dependency | `poetry add requests` |
| Add dev dep | `poetry add --group dev pytest` |
| Remove dep | `poetry remove requests` |
| Install deps | `poetry install` |
| Update deps | `poetry update` |
| Show deps | `poetry show --tree` |
| Build package | `poetry build` |
| Publish | `poetry publish` |
| Run command | `poetry run python script.py` |
| Shell | `poetry shell` |
| Export | `poetry export -f requirements.txt -o requirements.txt` |

---

## Core Concepts

Poetry is a modern Python dependency management and packaging tool that:

- **Unified Workflow**: Handles environment creation, dependency management, and publishing
- **Declarative Configuration**: All config in `pyproject.toml` (PEP 517/518 compliant)
- **Deterministic Builds**: Lock file ensures identical dependencies everywhere
- **SAT Solver**: Sophisticated dependency resolution avoids version conflicts

**Poetry vs Traditional Tools**:

| Feature | pip + requirements.txt | Poetry |
|---------|----------------------|--------|
| Lock file | Manual | Automatic |
| Virtual env | Separate tool | Built-in |
| Dep resolution | Basic | SAT solver |
| Publishing | Needs twine | Built-in |
| Dev deps | Separate file | Dependency groups |

---

## Production Examples

### Example 1: Project Setup and Configuration

**Use case**: Create a new project with proper structure and configuration.

```bash
# Install Poetry using pipx (recommended)
pipx install poetry

# Verify installation
poetry --version

# Create new project with standard layout
poetry new my-service
cd my-service

# Or initialize in existing directory
mkdir existing-project && cd existing-project
poetry init --no-interaction

# Project structure created:
# my-service/
# ├── pyproject.toml
# ├── README.md
# ├── my_service/
# │   └── __init__.py
# └── tests/
#     └── __init__.py
```

**pyproject.toml** (generated and customized):

```toml
[tool.poetry]
name = "my-service"
version = "0.1.0"
description = "A production-ready Python service"
authors = ["Your Name <your.email@example.com>"]
license = "MIT"
readme = "README.md"
homepage = "https://github.com/yourorg/my-service"
repository = "https://github.com/yourorg/my-service"
documentation = "https://my-service.readthedocs.io"
keywords = ["service", "api", "python"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]

# Package discovery
packages = [{include = "my_service", from = "src"}]

# Python version constraint
[tool.poetry.dependencies]
python = "^3.11"

# Build system (required for PEP 517)
[build-system]
requires = ["poetry-core>=1.5.0"]
build-backend = "poetry.core.masonry.api"
```

**Key configuration options**:

```toml
# Use src layout (recommended for larger projects)
packages = [{include = "my_service", from = "src"}]

# Include additional files
include = ["CHANGELOG.md", "data/*.json"]

# Exclude files from package
exclude = ["tests/*", "docs/*"]

# CLI entry points
[tool.poetry.scripts]
my-cli = "my_service.cli:main"

# Plugin entry points
[tool.poetry.plugins."my_service.plugins"]
default = "my_service.plugins.default:DefaultPlugin"
```

**Key points**:
- Use `pipx` to install Poetry globally (avoids dependency conflicts)
- `pyproject.toml` replaces setup.py, setup.cfg, and requirements.txt
- Version constraints use semantic versioning: `^3.11` means `>=3.11.0 <4.0.0`
- The `[build-system]` section is required for PEP 517 compliance

---

### Example 2: Managing Dependencies

**Use case**: Add, update, and manage project dependencies.

```bash
# Add runtime dependencies
poetry add fastapi
poetry add "uvicorn[standard]"  # With extras
poetry add pydantic==2.5.0  # Specific version
poetry add "sqlalchemy>=2.0,<3.0"  # Version range

# Add dependencies from git
poetry add git+https://github.com/org/repo.git
poetry add git+https://github.com/org/repo.git#branch=develop
poetry add git+https://github.com/org/repo.git#tag=v1.0.0

# Add from local path (for development)
poetry add ../my-local-package --editable

# Update dependencies
poetry update  # Update all
poetry update fastapi pydantic  # Update specific
poetry update --dry-run  # Preview changes

# Show dependency tree
poetry show --tree

# Show outdated packages
poetry show --outdated

# Remove dependencies
poetry remove fastapi

# Lock without installing
poetry lock

# Install from lock file only (production)
poetry install --no-root --only main
```

**Lock file explained** (`poetry.lock`):

```toml
# This file is auto-generated by Poetry
# DO NOT edit manually

[[package]]
name = "fastapi"
version = "0.109.0"
description = "FastAPI framework"
optional = false
python-versions = ">=3.8"

[package.dependencies]
pydantic = ">=1.7.4,<2.0.0 || >2.0.0,<3.0.0"
starlette = ">=0.35.0,<0.36.0"
typing-extensions = ">=4.8.0"

[package.extras]
all = ["email-validator", "httpx", "python-multipart", ...]

[[package]]
name = "starlette"
version = "0.35.1"
# ... transitive dependencies are also locked
```

**Environment management**:

```bash
# Poetry creates virtual env automatically
# Default location: {cache-dir}/virtualenvs/

# Configure to create .venv in project directory
poetry config virtualenvs.in-project true

# Show current environment info
poetry env info

# List all environments
poetry env list

# Remove environment
poetry env remove python3.11

# Use specific Python version
poetry env use python3.12
poetry env use /usr/bin/python3.12
```

**Key points**:
- The lock file pins exact versions of ALL dependencies (including transitive)
- Always commit `poetry.lock` to version control
- Use `poetry update` carefully—it can upgrade many packages
- `--no-root` skips installing the current project (useful in Docker)

---

### Example 3: Dependency Groups and Environments

**Use case**: Organize dependencies for different environments (dev, test, prod).

```toml
# pyproject.toml

[tool.poetry.dependencies]
python = "^3.11"
# Production dependencies
fastapi = "^0.109.0"
uvicorn = {extras = ["standard"], version = "^0.27.0"}
pydantic = "^2.5.0"
sqlalchemy = "^2.0.0"
alembic = "^1.13.0"

# Optional dependencies (extras)
[tool.poetry.extras]
postgres = ["psycopg2-binary"]
mysql = ["pymysql"]
all = ["psycopg2-binary", "pymysql"]

# Development tools
[tool.poetry.group.dev.dependencies]
black = "^24.1.0"
ruff = "^0.1.14"
mypy = "^1.8.0"
pre-commit = "^3.6.0"
ipython = "^8.20.0"

# Testing
[tool.poetry.group.test.dependencies]
pytest = "^8.0.0"
pytest-cov = "^4.1.0"
pytest-asyncio = "^0.23.0"
httpx = "^0.26.0"  # For testing FastAPI
factory-boy = "^3.3.0"

# Documentation
[tool.poetry.group.docs]
optional = true  # Not installed by default

[tool.poetry.group.docs.dependencies]
mkdocs = "^1.5.0"
mkdocs-material = "^9.5.0"
mkdocstrings = {extras = ["python"], version = "^0.24.0"}
```

**Working with dependency groups**:

```bash
# Install all groups (default)
poetry install

# Install only main + specific groups
poetry install --only main,test

# Skip specific groups
poetry install --without docs,dev

# Install optional group
poetry install --with docs

# Export specific groups
poetry export -f requirements.txt --only main -o requirements.txt
poetry export -f requirements.txt --with dev,test -o requirements-dev.txt

# Production deployment (main deps only)
poetry install --no-root --only main

# CI testing (main + test deps)
poetry install --only main,test
```

**Environment-specific installation script**:

```bash
#!/bin/bash
# install.sh - Install dependencies based on environment

set -e

case "${ENVIRONMENT:-development}" in
    production)
        echo "Installing production dependencies..."
        poetry install --no-root --only main
        ;;
    test)
        echo "Installing test dependencies..."
        poetry install --only main,test
        ;;
    development)
        echo "Installing all development dependencies..."
        poetry install
        ;;
    *)
        echo "Unknown environment: $ENVIRONMENT"
        exit 1
        ;;
esac
```

**GitHub Actions CI example**:

```yaml
# .github/workflows/ci.yml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install Poetry
        uses: snok/install-poetry@v1
        with:
          virtualenvs-create: true
          virtualenvs-in-project: true

      - name: Load cached venv
        id: cached-poetry-dependencies
        uses: actions/cache@v4
        with:
          path: .venv
          key: venv-${{ runner.os }}-${{ hashFiles('**/poetry.lock') }}

      - name: Install dependencies
        if: steps.cached-poetry-dependencies.outputs.cache-hit != 'true'
        run: poetry install --only main,test

      - name: Run tests
        run: poetry run pytest --cov=my_service --cov-report=xml

      - name: Type check
        run: poetry run mypy my_service
```

**Key points**:
- Use dependency groups to organize by purpose (dev, test, docs)
- Mark groups as `optional = true` if not needed by default
- Export to `requirements.txt` for Docker builds or compatibility
- Cache the virtual environment in CI for faster builds

---

### Example 4: Publishing to PyPI

**Use case**: Build and publish packages to PyPI or private registries.

```bash
# Build distributions
poetry build
# Creates:
# dist/
# ├── my_service-0.1.0-py3-none-any.whl
# └── my_service-0.1.0.tar.gz

# Check the built package
poetry run twine check dist/*

# Publish to PyPI
poetry publish

# Publish to TestPyPI first
poetry config repositories.testpypi https://test.pypi.org/legacy/
poetry publish -r testpypi

# Publish with token (non-interactive)
poetry config pypi-token.pypi your-token-here
poetry publish --no-interaction

# Build and publish in one command
poetry publish --build
```

**Configuring private registries**:

```bash
# Add private registry
poetry config repositories.private https://pypi.mycompany.com/simple/

# Set credentials
poetry config http-basic.private username password

# Or use token
poetry config pypi-token.private your-token-here

# Publish to private registry
poetry publish -r private

# Install from private registry
poetry source add private https://pypi.mycompany.com/simple/
poetry add my-private-package --source private
```

**pyproject.toml with sources**:

```toml
# Configure package sources
[[tool.poetry.source]]
name = "private"
url = "https://pypi.mycompany.com/simple/"
priority = "supplemental"  # Use for specific packages only

[[tool.poetry.source]]
name = "PyPI"
priority = "primary"
```

**Version management**:

```bash
# Bump version (follows semver)
poetry version patch   # 0.1.0 → 0.1.1
poetry version minor   # 0.1.0 → 0.2.0
poetry version major   # 0.1.0 → 1.0.0
poetry version prepatch  # 0.1.0 → 0.1.1a0
poetry version prerelease  # 0.1.0 → 0.1.0a0
poetry version 2.0.0  # Set exact version

# Show current version
poetry version --short
```

**Automated release workflow**:

```yaml
# .github/workflows/release.yml
name: Release

on:
  push:
    tags:
      - 'v*'

jobs:
  release:
    runs-on: ubuntu-latest
    permissions:
      id-token: write  # For trusted publishing

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install Poetry
        uses: snok/install-poetry@v1

      - name: Build
        run: poetry build

      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        # Uses trusted publishing - no token needed!
```

**Key points**:
- Always test with TestPyPI before publishing to production PyPI
- Use trusted publishing (OIDC) in GitHub Actions—no tokens needed
- Semantic versioning: major.minor.patch (breaking.feature.fix)
- Keep `poetry.lock` in version control for reproducible builds

---

## Common Patterns

### Pattern: Monorepo with Multiple Packages
```toml
# packages/core/pyproject.toml
[tool.poetry]
name = "myorg-core"

[tool.poetry.dependencies]
python = "^3.11"

# packages/api/pyproject.toml
[tool.poetry]
name = "myorg-api"

[tool.poetry.dependencies]
python = "^3.11"
myorg-core = {path = "../core", develop = true}
```

### Pattern: Platform-Specific Dependencies
```toml
[tool.poetry.dependencies]
pywin32 = {version = "^306", markers = "sys_platform == 'win32'"}
uvloop = {version = "^0.19", markers = "sys_platform != 'win32'"}
```

### Pattern: Dynamic Versioning
```toml
# Use poetry-dynamic-versioning plugin
[tool.poetry-dynamic-versioning]
enable = true
vcs = "git"
style = "pep440"
```

---

## Pitfalls to Avoid

**Don't do this:**
```bash
# Installing Poetry with pip in your project
pip install poetry  # Creates dependency conflicts!
```

**Do this instead:**
```bash
# Install Poetry system-wide with pipx
pipx install poetry
```

---

**Don't do this:**
```bash
# Ignoring the lock file
poetry install --no-lock  # Non-deterministic builds!
```

**Do this instead:**
```bash
# Always use lock file
poetry install  # Uses poetry.lock for exact versions
poetry lock  # Update lock file when needed
```

---

**Don't do this:**
```toml
# Overly permissive version constraints
[tool.poetry.dependencies]
requests = "*"  # Any version - dangerous!
```

**Do this instead:**
```toml
# Specific constraints with caret
[tool.poetry.dependencies]
requests = "^2.31.0"  # >=2.31.0 <3.0.0
```

---

## See Also

- [pyproject-config.md](pyproject-config.md) - pyproject.toml configuration
- [docker-deployment.md](docker-deployment.md) - Containerizing Python apps
- [project-structure.md](../foundations/project-structure.md) - Project layout
