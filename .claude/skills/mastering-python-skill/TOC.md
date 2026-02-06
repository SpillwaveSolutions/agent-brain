# Mastering Python Skill - Table of Contents

Complete reference guide for modern Python development.

## Quick Navigation

| Category | Files | Topics |
|----------|-------|--------|
| [Foundations](#foundations) | 4 | Types, project structure, code quality, syntax |
| [Patterns](#patterns) | 5 | Async, error handling, decorators, context managers, generators |
| [Testing](#testing) | 3 | Pytest, mocking, property-based testing |
| [Web APIs](#web-apis) | 3 | FastAPI, Pydantic, database access |
| [Packaging](#packaging) | 3 | Poetry, pyproject.toml, Docker |
| [Production](#production) | 3 | CI/CD, monitoring, security |
| [Sample CLI](#sample-cli) | 5 | Runnable example tools |

---

## Foundations

Core Python concepts and project setup.

| File | Topics | Key Sections |
|------|--------|--------------|
| [syntax-essentials.md](references/foundations/syntax-essentials.md) | Variables, functions, control flow | Comprehensions, match/case, walrus operator |
| [type-systems.md](references/foundations/type-systems.md) | Type hints, generics, Protocols | TypeVar, ParamSpec, TypeGuard |
| [project-structure.md](references/foundations/project-structure.md) | Layout, config, entry points | src/ layout, namespace packages |
| [code-quality.md](references/foundations/code-quality.md) | Ruff, Black, pre-commit | mypy strict mode, pyproject.toml |

---

## Patterns

Advanced Python patterns for production code.

| File | Topics | Key Sections |
|------|--------|--------------|
| [async-programming.md](references/patterns/async-programming.md) | asyncio, TaskGroup | Semaphores, async generators, httpx |
| [error-handling.md](references/patterns/error-handling.md) | Exceptions, logging | Custom exceptions, Result type |
| [decorators.md](references/patterns/decorators.md) | Function/class decorators | functools.wraps, caching |
| [context-managers.md](references/patterns/context-managers.md) | with statement, contextlib | ExitStack, async context |
| [generators.md](references/patterns/generators.md) | yield, iterators | Pipelines, memory efficiency |

---

## Testing

Modern Python testing strategies.

| File | Topics | Key Sections |
|------|--------|--------------|
| [pytest-essentials.md](references/testing/pytest-essentials.md) | Fixtures, parametrize | Markers, conftest, plugins |
| [mocking-strategies.md](references/testing/mocking-strategies.md) | pytest-mock, patch | MagicMock, spies, async mocking |
| [property-testing.md](references/testing/property-testing.md) | Hypothesis strategies | Composite, stateful testing |

---

## Web APIs

Building modern web services.

| File | Topics | Key Sections |
|------|--------|--------------|
| [fastapi-patterns.md](references/web-apis/fastapi-patterns.md) | Routes, dependencies | Middleware, lifespan, versioning |
| [pydantic-validation.md](references/web-apis/pydantic-validation.md) | Models, validators | Settings, discriminated unions |
| [database-access.md](references/web-apis/database-access.md) | SQLAlchemy async | Repository pattern, Alembic |

---

## Packaging

Python packaging and distribution.

| File | Topics | Key Sections |
|------|--------|--------------|
| [poetry-workflow.md](references/packaging/poetry-workflow.md) | Dependencies, groups | Lock files, publishing |
| [pyproject-config.md](references/packaging/pyproject-config.md) | PEP 517/518/621 | Tool config, build backends |
| [docker-deployment.md](references/packaging/docker-deployment.md) | Multi-stage builds | Compose, Kubernetes, caching |

---

## Production

Production readiness and operations.

| File | Topics | Key Sections |
|------|--------|--------------|
| [ci-cd-pipelines.md](references/production/ci-cd-pipelines.md) | GitHub Actions | Matrix testing, CD pipelines |
| [monitoring.md](references/production/monitoring.md) | Logs, metrics, traces | Prometheus, OpenTelemetry |
| [security.md](references/production/security.md) | OWASP, auth, secrets | Argon2, JWT, dependency scanning |

---

## Sample CLI

Runnable example tools demonstrating patterns.

| File | Demonstrates | Reference |
|------|--------------|-----------|
| [README.md](sample-cli/README.md) | Installation and usage | - |
| [async_fetcher.py](sample-cli/async_fetcher.py) | Async HTTP with rate limiting | [async-programming.md](references/patterns/async-programming.md) |
| [config_loader.py](sample-cli/config_loader.py) | Pydantic settings + .env | [pydantic-validation.md](references/web-apis/pydantic-validation.md) |
| [db_cli.py](sample-cli/db_cli.py) | SQLAlchemy async CRUD | [database-access.md](references/web-apis/database-access.md) |
| [code_validator.py](sample-cli/code_validator.py) | Run→check→fix validation | [code-quality.md](references/foundations/code-quality.md) |

---

## Quick Topic Lookup

| I Need To... | Reference |
|--------------|-----------|
| Add type hints | [type-systems.md](references/foundations/type-systems.md) |
| Set up a new project | [project-structure.md](references/foundations/project-structure.md) |
| Configure linting | [code-quality.md](references/foundations/code-quality.md) |
| Write async code | [async-programming.md](references/patterns/async-programming.md) |
| Handle errors properly | [error-handling.md](references/patterns/error-handling.md) |
| Write a decorator | [decorators.md](references/patterns/decorators.md) |
| Manage resources | [context-managers.md](references/patterns/context-managers.md) |
| Process large data | [generators.md](references/patterns/generators.md) |
| Write pytest tests | [pytest-essentials.md](references/testing/pytest-essentials.md) |
| Mock dependencies | [mocking-strategies.md](references/testing/mocking-strategies.md) |
| Property-based testing | [property-testing.md](references/testing/property-testing.md) |
| Build a REST API | [fastapi-patterns.md](references/web-apis/fastapi-patterns.md) |
| Validate data | [pydantic-validation.md](references/web-apis/pydantic-validation.md) |
| Use SQLAlchemy async | [database-access.md](references/web-apis/database-access.md) |
| Manage with Poetry | [poetry-workflow.md](references/packaging/poetry-workflow.md) |
| Configure pyproject.toml | [pyproject-config.md](references/packaging/pyproject-config.md) |
| Containerize app | [docker-deployment.md](references/packaging/docker-deployment.md) |
| Set up CI/CD | [ci-cd-pipelines.md](references/production/ci-cd-pipelines.md) |
| Add monitoring | [monitoring.md](references/production/monitoring.md) |
| Secure my app | [security.md](references/production/security.md) |

---

## Quick Commands

```bash
# Virtual environment
python -m venv .venv && source .venv/bin/activate

# Poetry
poetry install && poetry add --group dev pytest ruff mypy

# Quality checks
ruff check . && ruff format . && mypy src/

# Testing
pytest -v --cov=src --cov-report=html

# Building
python -m build && twine check dist/*
```
