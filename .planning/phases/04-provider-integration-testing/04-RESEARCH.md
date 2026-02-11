# Phase 4: Provider Integration Testing - Research

**Researched:** 2026-02-10
**Domain:** E2E testing, provider integration, health check endpoints, CI/CD test matrix
**Confidence:** HIGH

## Summary

Phase 4 requires comprehensive E2E testing of all provider combinations (OpenAI, Anthropic, Ollama, Cohere) plus enhanced health check endpoints. Research reveals a mature testing ecosystem with well-established patterns for pytest parametrization, provider testing matrices, and FastAPI health monitoring.

**Key insight:** The project already has 505+ tests with 70% coverage, existing E2E infrastructure (conftest.py, CLIRunner, server fixtures), and 4 YAML config fixtures for provider combinations. The primary work is extending existing patterns rather than building new infrastructure.

**Primary recommendation:** Use pytest parametrization with indirect fixtures to create a test matrix across provider combinations, implement /health/providers endpoint for runtime validation, and leverage GitHub Actions matrix strategy for CI testing with optional API keys.

## Standard Stack

### Core Testing Libraries

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | 7.4+ | Test framework | Industry standard for Python testing with async support |
| pytest-asyncio | 0.21+ | Async test support | Required for FastAPI integration tests |
| httpx | 0.24+ | HTTP client | Used by FastAPI TestClient, supports async |
| respx | 0.20+ | Mock HTTPX requests | Modern alternative to responses for async HTTP mocking |
| pytest-cov | 4.1+ | Coverage reporting | Standard coverage plugin for pytest |
| python-dotenv | 1.0+ | Environment loading | Standard for .env file loading in tests |

### Supporting (Already in Project)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| FastAPI TestClient | 0.104+ | Sync API testing | Unit/integration tests without server process |
| AsyncClient | httpx 0.24+ | Async API testing | Integration tests requiring async operations |
| unittest.mock | stdlib | Mocking | Unit tests, provider mocking |
| MagicMock/AsyncMock | stdlib | Async mocking | FastAPI async endpoint testing |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pytest | unittest | Pytest has better fixtures, parametrization, and async support |
| respx | responses | respx supports httpx/async, responses is for requests/sync only |
| pytest-cov | coverage.py | pytest-cov integrates seamlessly with pytest workflow |
| YAML fixtures | Python fixtures | YAML allows non-developers to add configs, easier to version |

**Installation:**

```bash
# Already installed in project
cd agent-brain-server
poetry add --group dev pytest pytest-asyncio pytest-cov httpx respx
```

## Architecture Patterns

### Recommended E2E Test Structure

```
e2e/
├── fixtures/               # Test data and configs
│   ├── config_openai.yaml
│   ├── config_cohere.yaml
│   ├── config_ollama_only.yaml
│   └── test_docs/
├── integration/            # E2E integration tests
│   ├── conftest.py        # Session fixtures for server/CLI
│   ├── test_full_workflow.py
│   ├── test_provider_openai.py     # NEW
│   ├── test_provider_anthropic.py  # NEW
│   ├── test_provider_ollama.py     # NEW (exists partially)
│   └── test_provider_cohere.py     # NEW
└── scripts/                # Helper scripts
```

### Pattern 1: Parametrized Provider Tests with Indirect Fixtures

**What:** Use pytest.mark.parametrize with indirect=True to run the same E2E test suite across multiple provider configurations.

**When to use:** Testing provider combinations where the test logic is identical but the configuration changes.

**Example:**

```python
# Source: pytest official docs - https://docs.pytest.org/en/stable/how-to/parametrize.html
import pytest
from pathlib import Path

# Fixture that loads provider config based on parameter
@pytest.fixture
def provider_config(request):
    """Load provider configuration from YAML fixture."""
    config_file = Path(__file__).parent.parent / "fixtures" / request.param
    os.environ["AGENT_BRAIN_CONFIG"] = str(config_file)
    yield config_file
    # Cleanup
    os.environ.pop("AGENT_BRAIN_CONFIG", None)
    clear_settings_cache()

# Parametrize test with config files
@pytest.mark.parametrize(
    "provider_config",
    [
        "config_openai.yaml",
        "config_cohere.yaml",
        pytest.param("config_ollama_only.yaml", marks=pytest.mark.ollama),
    ],
    indirect=True,  # Pass parameter to fixture instead of test
)
def test_provider_e2e_workflow(provider_config, cli, indexed_docs):
    """Test full workflow with different providers."""
    # Test indexing
    assert indexed_docs["total_documents"] >= 5

    # Test query
    result = cli.query("espresso brewing")
    assert len(result["results"]) >= 1
    assert result["results"][0]["score"] > 0.5
```

### Pattern 2: Session-Scoped Server with Provider Switching

**What:** Start server once per test session, but switch provider configs between test classes using function-scoped fixtures.

**When to use:** Reducing test execution time by avoiding server restarts while still testing multiple providers.

**Example:**

```python
# Source: existing e2e/integration/conftest.py pattern
@pytest.fixture(scope="session")
def server_process() -> Generator[subprocess.Popen, None, None]:
    """Start server once for entire test session."""
    # Server startup logic
    yield process
    # Server teardown

@pytest.fixture(scope="function")
def switch_provider_config(request):
    """Switch provider config for a single test."""
    config_path = Path(__file__).parent.parent / "fixtures" / request.param
    os.environ["AGENT_BRAIN_CONFIG"] = str(config_path)
    clear_settings_cache()
    # Trigger provider reload on server side
    yield
    # Cleanup
    os.environ.pop("AGENT_BRAIN_CONFIG", None)
```

### Pattern 3: Health Check Endpoint with Provider Status

**What:** Dedicated /health/providers endpoint that validates all configured providers and returns structured status.

**When to use:** Debugging provider configuration issues, CI health checks, runtime monitoring.

**Example:**

```python
# Source: existing agent_brain_server/api/routers/health.py pattern
from agent_brain_server.models.health import ProviderHealth, ProvidersStatus

@router.get(
    "/providers",
    response_model=ProvidersStatus,
    summary="Provider Status",
    description="Returns status of all configured providers with health checks.",
)
async def providers_status(request: Request) -> ProvidersStatus:
    """Get detailed status of all configured providers.

    Returns:
        ProvidersStatus with configuration source, validation errors,
        and health status of each provider.
    """
    # Get config source
    config_file = _find_config_file()
    config_source = str(config_file) if config_file else None

    # Load and validate settings
    settings = load_provider_settings()
    validation_errors = validate_provider_config(settings)

    providers: list[ProviderHealth] = []

    # Check embedding provider
    try:
        embedding_provider = ProviderRegistry.get_embedding_provider(settings.embedding)
        embedding_dimensions = embedding_provider.get_dimensions()
        providers.append(ProviderHealth(
            provider_type="embedding",
            provider_name=str(settings.embedding.provider),
            model=settings.embedding.model,
            status="healthy",
            dimensions=embedding_dimensions,
        ))
    except Exception as e:
        providers.append(ProviderHealth(
            provider_type="embedding",
            status="unavailable",
            message=str(e),
        ))

    # Repeat for summarization, reranker

    return ProvidersStatus(
        config_source=config_source,
        strict_mode=getattr(request.app.state, "strict_mode", False),
        validation_errors=[str(e) for e in validation_errors],
        providers=providers,
        timestamp=datetime.now(timezone.utc),
    )
```

### Pattern 4: CI Matrix Strategy for Provider Testing

**What:** GitHub Actions matrix build that runs E2E tests against multiple provider configurations, skipping providers with missing API keys.

**When to use:** CI/CD pipeline testing where not all API keys are available in all environments.

**Example:**

```yaml
# Source: GitHub Actions matrix documentation - https://oneuptime.com/blog/post/2026-01-25-github-actions-matrix-builds/view
name: Provider E2E Tests

on:
  pull_request:
  push:
    branches: [main]

jobs:
  test-providers:
    name: Test ${{ matrix.provider }} Provider
    runs-on: ubuntu-latest

    strategy:
      matrix:
        provider:
          - name: openai
            config: config_openai.yaml
            required_keys: OPENAI_API_KEY,ANTHROPIC_API_KEY
          - name: cohere
            config: config_cohere.yaml
            required_keys: COHERE_API_KEY,ANTHROPIC_API_KEY
          - name: ollama
            config: config_ollama_only.yaml
            required_keys: ""  # No API keys needed
      fail-fast: false  # Continue testing other providers if one fails

    steps:
      - uses: actions/checkout@v4

      - name: Check API keys
        id: check_keys
        run: |
          REQUIRED_KEYS="${{ matrix.provider.required_keys }}"
          if [ -z "$REQUIRED_KEYS" ]; then
            echo "skip=false" >> $GITHUB_OUTPUT
            exit 0
          fi

          IFS=',' read -ra KEYS <<< "$REQUIRED_KEYS"
          for key in "${KEYS[@]}"; do
            if [ -z "${!key}" ]; then
              echo "Missing $key, skipping ${{ matrix.provider.name }}"
              echo "skip=true" >> $GITHUB_OUTPUT
              exit 0
            fi
          done
          echo "skip=false" >> $GITHUB_OUTPUT
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          COHERE_API_KEY: ${{ secrets.COHERE_API_KEY }}

      - name: Run E2E tests
        if: steps.check_keys.outputs.skip == 'false'
        run: |
          export AGENT_BRAIN_CONFIG=e2e/fixtures/${{ matrix.provider.config }}
          task test:e2e
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          COHERE_API_KEY: ${{ secrets.COHERE_API_KEY }}
```

### Anti-Patterns to Avoid

- **Hardcoded API keys in tests:** Always use environment variables and .env files
- **Provider-specific test logic duplication:** Use parametrization to share test logic across providers
- **Blocking E2E tests on all providers:** Use pytest markers to allow selective provider testing
- **Restarting server per test:** Use session-scoped fixtures to amortize startup cost
- **Ignoring provider health check failures:** Fail fast when provider configuration is invalid

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP mocking for async clients | Custom httpx patching | `respx` library | Handles async HTTPX automatically, supports route patterns, response side effects |
| Test parametrization with fixtures | Manual loop over configs | `@pytest.mark.parametrize` with `indirect=True` | Pytest natively supports fixture parametrization, better test discovery |
| Provider health checks | Custom validation functions | Existing `validate_provider_config()` + new endpoint | Already has validation logic, just needs HTTP exposure |
| CI test matrix | Multiple workflow files | GitHub Actions `strategy.matrix` | Single workflow definition, automatic parallelization |
| Config file loading | Custom YAML parsing | Existing `load_provider_settings()` | Already implemented with caching and fallback logic |
| API key management in tests | Hardcoded/checked-in keys | pytest fixtures + environment variables | Secure, flexible, already pattern in conftest.py |

**Key insight:** Phase 2 already implemented provider switching infrastructure (ProviderRegistry, config validation, YAML loading). Phase 4 extends this with E2E validation, not reimplementation.

## Common Pitfalls

### Pitfall 1: Provider Tests Failing Due to Missing API Keys

**What goes wrong:** E2E tests fail in CI or local environments when required API keys aren't set, blocking all testing.

**Why it happens:** Different developers have different API keys available, CI environments may only have a subset.

**How to avoid:**
- Use pytest markers to tag tests requiring specific providers (`@pytest.mark.openai`, `@pytest.mark.cohere`)
- Implement skip logic in conftest.py that checks for API keys before running provider-specific tests
- Document which environment variables are required for which test suites

**Warning signs:**
- Tests pass locally but fail in CI with "Missing API key" errors
- New contributors can't run E2E tests without purchasing all API subscriptions
- Test suite becomes all-or-nothing (all providers or none)

**Implementation:**

```python
# e2e/integration/conftest.py
@pytest.fixture(scope="session")
def check_openai_key():
    """Skip tests if OpenAI API key not available."""
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set - skipping OpenAI tests")

@pytest.fixture(scope="session")
def check_cohere_key():
    """Skip tests if Cohere API key not available."""
    if not os.environ.get("COHERE_API_KEY"):
        pytest.skip("COHERE_API_KEY not set - skipping Cohere tests")

# Use in tests
@pytest.mark.openai
def test_openai_embedding_e2e(check_openai_key, cli):
    """Test OpenAI embeddings end-to-end."""
    # Test logic
```

### Pitfall 2: Server State Pollution Between Provider Tests

**What goes wrong:** Testing provider A modifies server state (cached providers, vector store metadata), causing provider B tests to fail or produce incorrect results.

**Why it happens:** ProviderRegistry caches provider instances, ChromaDB stores embedding metadata, BM25 index persists between tests.

**How to avoid:**
- Call `ProviderRegistry.clear_cache()` in function-scoped fixtures when switching providers
- Use separate ChromaDB persistence directories per provider test class
- Clear vector store between provider switches or use session-scoped `indexed_docs` fixture per provider

**Warning signs:**
- Test order dependency (tests pass individually but fail when run together)
- Dimension mismatch errors when switching between providers with different embedding dimensions
- Cached embeddings from previous provider used in subsequent tests

**Implementation:**

```python
# e2e/integration/conftest.py
@pytest.fixture(scope="function")
def clean_provider_state():
    """Clean provider state before test."""
    from agent_brain_server.providers.factory import ProviderRegistry
    from agent_brain_server.config.provider_config import clear_settings_cache

    ProviderRegistry.clear_cache()
    clear_settings_cache()
    yield
    # Cleanup after test
    ProviderRegistry.clear_cache()
    clear_settings_cache()
```

### Pitfall 3: Long E2E Test Execution Times

**What goes wrong:** E2E test suite takes 10+ minutes to run, blocking development iteration.

**Why it happens:** Starting/stopping server per test, re-indexing documents for each provider, sequential execution.

**How to avoid:**
- Use session-scoped server fixture (start once, use for all tests)
- Use session-scoped indexed_docs fixture per provider (index once per provider)
- Run provider tests in parallel using pytest-xdist
- Use pytest markers to run only relevant tests during development

**Warning signs:**
- Developers skip running E2E tests locally because they're too slow
- CI E2E job takes longer than all unit tests combined
- Each test includes server startup logs

**Implementation:**

```python
# Run E2E tests in parallel
pytest e2e/integration/ -n auto --dist loadgroup

# Run only Ollama tests (local, fast)
pytest e2e/integration/ -m ollama

# Run only OpenAI tests
pytest e2e/integration/ -m openai
```

### Pitfall 4: Health Check Endpoint Doesn't Validate Providers

**What goes wrong:** /health returns "healthy" even when providers are misconfigured or unavailable, leading to runtime failures.

**Why it happens:** Basic health checks only verify server process is running, not that dependencies work.

**How to avoid:**
- Implement /health/providers endpoint that actually calls provider APIs or checks configuration
- Include provider validation in readiness checks (for Kubernetes/load balancer routing)
- Return structured errors with provider-specific details
- Use timeout on provider checks to prevent health endpoint from hanging

**Warning signs:**
- Server reports "healthy" but queries fail with provider errors
- No way to debug provider configuration without reading logs
- Load balancer routes traffic to instances with invalid provider config

**Implementation:**

```python
# Separate liveness (process running) from readiness (providers available)
@router.get("/health/live")
async def liveness_check():
    """Liveness probe - is process running?"""
    return {"status": "alive"}

@router.get("/health/ready")
async def readiness_check():
    """Readiness probe - can handle traffic?"""
    settings = load_provider_settings()
    validation_errors = validate_provider_config(settings)

    if validation_errors:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "not_ready",
                "errors": [str(e) for e in validation_errors],
            },
        )

    return {"status": "ready"}
```

### Pitfall 5: CI Matrix Tests Creating Excessive Cost

**What goes wrong:** GitHub Actions matrix creates 20+ parallel jobs, consuming all CI minutes in a single PR.

**Why it happens:** Matrix dimensions multiply (3 OS × 4 providers × 2 Python versions = 24 jobs).

**How to avoid:**
- Use `max-parallel` to limit concurrent jobs
- Use `fail-fast: false` to continue testing even if one provider fails
- Only test provider matrix on `main` branch or with label, not every PR
- Use `if: contains(github.event.pull_request.labels.*.name, 'test-providers')` for opt-in testing

**Warning signs:**
- CI cost spikes after adding matrix
- PR checks take >30 minutes
- Multiple identical tests running in parallel

**Implementation:**

```yaml
# Limit parallelism and only run on specific events
jobs:
  test-providers:
    if: github.event_name == 'push' || contains(github.event.pull_request.labels.*.name, 'test-providers')
    strategy:
      matrix:
        provider: [openai, cohere, ollama]
      max-parallel: 2  # Only 2 at a time
      fail-fast: false
```

## Code Examples

Verified patterns from official sources and existing codebase:

### E2E Provider Test with Parametrization

```python
# Source: e2e/integration/test_full_workflow.py + pytest docs
import pytest
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"

@pytest.fixture
def provider_config(request):
    """Load provider config and set environment."""
    import os
    from agent_brain_server.config.provider_config import clear_settings_cache

    config_file = FIXTURES_DIR / request.param
    os.environ["AGENT_BRAIN_CONFIG"] = str(config_file)
    clear_settings_cache()
    yield config_file
    os.environ.pop("AGENT_BRAIN_CONFIG", None)
    clear_settings_cache()

@pytest.mark.parametrize(
    "provider_config",
    [
        "config_openai.yaml",
        pytest.param("config_cohere.yaml", marks=pytest.mark.skipif(
            not os.environ.get("COHERE_API_KEY"),
            reason="COHERE_API_KEY not set"
        )),
        pytest.param("config_ollama_only.yaml", marks=pytest.mark.ollama),
    ],
    indirect=True,
)
class TestProviderWorkflows:
    """E2E tests running against multiple provider configurations."""

    def test_indexing_creates_chunks(self, provider_config, cli, indexed_docs):
        """Test document indexing with different providers."""
        assert indexed_docs["total_documents"] >= 5
        assert indexed_docs["total_chunks"] >= 5

    def test_semantic_query_returns_results(self, provider_config, cli, indexed_docs):
        """Test semantic search with different providers."""
        result = cli.query("How do I make espresso?")
        assert len(result["results"]) >= 1
        assert result["results"][0]["score"] > 0.3

    def test_hybrid_search_combines_results(self, provider_config, cli, indexed_docs):
        """Test hybrid search with different providers."""
        result = cli.query("espresso", mode="hybrid", alpha=0.5)
        assert len(result["results"]) >= 1
```

### Health Check Endpoint Implementation

```python
# Source: agent_brain_server/api/routers/health.py (existing pattern)
from datetime import datetime, timezone
from fastapi import APIRouter, Request
from agent_brain_server.models.health import ProviderHealth, ProvidersStatus
from agent_brain_server.providers.factory import ProviderRegistry
from agent_brain_server.config.provider_config import (
    load_provider_settings,
    validate_provider_config,
    _find_config_file,
)

router = APIRouter()

@router.get(
    "/providers",
    response_model=ProvidersStatus,
    summary="Provider Status",
    description="Returns status of all configured providers with health checks.",
)
async def providers_status(request: Request) -> ProvidersStatus:
    """Get detailed status of all configured providers."""
    # Get config source
    config_file = _find_config_file()
    config_source = str(config_file) if config_file else None

    # Get strict mode from app state
    strict_mode = getattr(request.app.state, "strict_mode", False)

    # Load settings and validate
    settings = load_provider_settings()
    validation_errors = validate_provider_config(settings)
    error_messages = [str(e) for e in validation_errors]

    providers: list[ProviderHealth] = []

    # Check embedding provider
    try:
        embedding_provider = ProviderRegistry.get_embedding_provider(settings.embedding)
        embedding_status = "healthy"
        embedding_message = None
        embedding_dimensions = embedding_provider.get_dimensions()
    except Exception as e:
        embedding_status = "unavailable"
        embedding_message = str(e)
        embedding_dimensions = None

    providers.append(
        ProviderHealth(
            provider_type="embedding",
            provider_name=str(settings.embedding.provider),
            model=settings.embedding.model,
            status=embedding_status,
            message=embedding_message,
            dimensions=embedding_dimensions,
        )
    )

    # Check summarization provider (similar pattern)

    # Check reranker provider if enabled
    from agent_brain_server.config import settings as app_settings
    if app_settings.ENABLE_RERANKING:
        # Similar pattern for reranker
        pass

    return ProvidersStatus(
        config_source=config_source,
        strict_mode=strict_mode,
        validation_errors=error_messages,
        providers=providers,
        timestamp=datetime.now(timezone.utc),
    )
```

### Pydantic Models for Health Response

```python
# Source: agent_brain_server/models/health.py pattern
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field

class ProviderHealth(BaseModel):
    """Health status of a single provider."""

    provider_type: Literal["embedding", "summarization", "reranker"] = Field(
        description="Type of provider"
    )
    provider_name: str = Field(description="Provider name (e.g., 'openai', 'anthropic')")
    model: str = Field(description="Model name")
    status: Literal["healthy", "unavailable", "degraded"] = Field(
        description="Provider status"
    )
    message: Optional[str] = Field(
        default=None,
        description="Error message if unavailable",
    )
    dimensions: Optional[int] = Field(
        default=None,
        description="Embedding dimensions (for embedding providers only)",
    )

class ProvidersStatus(BaseModel):
    """Overall provider status response."""

    config_source: Optional[str] = Field(
        default=None,
        description="Path to config file or None if using defaults",
    )
    strict_mode: bool = Field(
        default=False,
        description="Whether strict validation is enabled",
    )
    validation_errors: list[str] = Field(
        default_factory=list,
        description="Configuration validation errors",
    )
    providers: list[ProviderHealth] = Field(
        description="Health status of each provider",
    )
    timestamp: datetime = Field(description="Response timestamp")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| responses library for HTTP mocking | respx for httpx/async | 2021 | respx supports async HTTPX, responses only supports sync requests |
| Manual provider switching in tests | pytest parametrization with indirect=True | Pytest 3.0+ (2016) | Single test definition runs against multiple configs |
| Single health endpoint | Separate liveness/readiness probes | Kubernetes era (2018+) | Allows load balancers to route only to ready instances |
| Sequential CI jobs | GitHub Actions matrix strategy | GitHub Actions v1 (2019) | Parallel testing reduces CI time |
| Hardcoded test configs | YAML fixtures with env var override | Modern testing (2020+) | Non-developers can add configs, easier CI integration |

**Deprecated/outdated:**
- **responses library for async:** Use respx instead, responses doesn't support httpx
- **TestClient for E2E:** Use subprocess + real server for true E2E (existing pattern is correct)
- **Single /health endpoint:** Modern pattern separates liveness (alive?) from readiness (can serve traffic?)
- **pytest.ini configuration:** pyproject.toml is now standard for pytest config (already in use)

## Open Questions

1. **Should E2E tests run against real external APIs or use mocked responses?**
   - What we know: Current E2E tests use real APIs with environment-provided keys
   - What's unclear: Trade-off between test authenticity vs. CI cost/reliability
   - Recommendation: Keep real API tests but make them optional (pytest markers), use mocks for basic provider tests

2. **How should provider health checks handle network timeouts?**
   - What we know: Provider instantiation can hang on network issues
   - What's unclear: Should health endpoint fail fast or wait for timeout?
   - Recommendation: Add timeout wrapper (5 seconds) to provider checks in /health/providers

3. **Should provider dimension mismatches be tested in E2E or unit tests?**
   - What we know: Phase 2 implemented dimension validation (PROV-07)
   - What's unclear: E2E tests would require real vector store persistence
   - Recommendation: E2E test covers happy path, unit tests cover dimension mismatch edge cases

4. **How to handle Ollama availability in CI?**
   - What we know: Ollama requires separate service, not always available in GitHub Actions
   - What's unclear: Should CI run Ollama in Docker, or skip Ollama tests?
   - Recommendation: Skip Ollama in CI by default, provide opt-in workflow that starts Ollama service

## Sources

### Primary (HIGH confidence)

- Existing codebase: e2e/integration/conftest.py, test_full_workflow.py - Current E2E patterns
- Existing codebase: agent_brain_server/api/routers/health.py - Health endpoint implementation
- Existing codebase: agent_brain_server/config/provider_config.py - Provider validation logic
- Existing codebase: e2e/fixtures/*.yaml - Provider configuration fixtures
- pytest official docs (https://docs.pytest.org/en/stable/how-to/parametrize.html) - Parametrization and fixtures
- FastAPI health pattern (https://www.index.dev/blog/how-to-implement-health-check-in-python) - Liveness vs readiness

### Secondary (MEDIUM confidence)

- GitHub Actions matrix strategy (https://oneuptime.com/blog/post/2026-01-25-github-actions-matrix-builds/view) - CI matrix builds
- pytest parametrize guide (https://oneuptime.com/blog/post/2026-02-02-pytest-parametrize-guide/view) - Recent parametrization patterns
- respx documentation (https://lundberg.github.io/respx/guide/) - HTTPX mocking for async
- pytest fixtures guide (https://www.testmu.ai/blog/end-to-end-tutorial-for-pytest-fixtures-with-examples/) - E2E fixture patterns
- GitHub Actions environment variables (https://oneuptime.com/blog/post/2025-12-20-github-actions-environment-variables/view) - Managing secrets in CI

### Tertiary (LOW confidence)

- None - all research verified with official docs or existing codebase

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH - All libraries already in use, verified in pyproject.toml and existing tests
- Architecture: HIGH - Existing e2e/integration/ structure provides clear pattern to extend
- Pitfalls: HIGH - Based on existing codebase patterns and documented pytest/FastAPI best practices
- CI matrix: MEDIUM - GitHub Actions matrix is standard, but provider-specific API key handling needs testing

**Research date:** 2026-02-10

**Valid until:** 30 days (stable technology stack, minor pytest/FastAPI updates expected)

**Key findings for planner:**

1. **Infrastructure exists:** 505+ tests, E2E conftest.py, CLIRunner, 4 YAML config fixtures
2. **Extend, don't rebuild:** Use existing patterns (parametrization, session fixtures, provider validation)
3. **Provider health endpoint:** Implement /health/providers using existing validation logic
4. **CI strategy:** Use GitHub Actions matrix with API key checks, skip providers with missing keys
5. **Test organization:** One test file per provider (test_provider_openai.py, etc.) using parametrized base tests
6. **Markers required:** Add @pytest.mark.openai, @pytest.mark.cohere, @pytest.mark.anthropic to pyproject.toml
