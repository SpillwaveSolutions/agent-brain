"""E2E tests for /health/providers endpoint (TEST-05).

This module tests the health providers endpoint that reports status
of all configured providers. Uses the module-level app from
agent_brain_server.api.main with mocked app.state dependencies,
following the same pattern as tests/integration/test_graph_query.py.
"""

import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from agent_brain_server.config.provider_config import clear_settings_cache

# Set test environment variables before importing app
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")

# Path to fixture files
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def temp_project_dir() -> Generator[Path, None, None]:
    """Create a temporary project directory with .claude/agent-brain structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        config_dir = project_dir / ".claude" / "agent-brain"
        config_dir.mkdir(parents=True)
        yield project_dir


@pytest.fixture(autouse=True)
def clear_config_cache() -> Generator[None, None, None]:
    """Clear the provider settings cache before and after each test."""
    clear_settings_cache()
    yield
    clear_settings_cache()


@contextmanager
def create_health_test_client(strict_mode: bool = False):
    """Create a test client using the real module-level app.

    Imports app from agent_brain_server.api.main and creates a TestClient
    that triggers the real lifespan. Patches heavy infrastructure classes
    (VectorStoreManager, BM25IndexManager, JobWorker) so the lifespan
    runs without real database initialization, while preserving config
    loading and app.state setup.

    This follows the same pattern as tests/integration/test_graph_query.py:
    import the real app, let the lifespan set up state, then override
    app.state as needed for testing.

    Args:
        strict_mode: Value to set for app.state.strict_mode
    """
    mock_vs = MagicMock()
    mock_vs.is_initialized = True
    mock_vs.initialize = AsyncMock()
    mock_vs.get_count = AsyncMock(return_value=0)
    mock_vs.get_embedding_metadata = AsyncMock(return_value=None)

    mock_bm25 = MagicMock()
    mock_bm25.is_initialized = True
    mock_bm25.initialize = MagicMock()

    mock_job_store = MagicMock()
    mock_job_store.initialize = AsyncMock()

    mock_job_worker = MagicMock()
    mock_job_worker.start = AsyncMock()
    mock_job_worker.stop = AsyncMock()

    with (
        patch(
            "agent_brain_server.api.main.VectorStoreManager",
            return_value=mock_vs,
        ),
        patch(
            "agent_brain_server.api.main.BM25IndexManager",
            return_value=mock_bm25,
        ),
        patch(
            "agent_brain_server.api.main.JobQueueStore",
            return_value=mock_job_store,
        ),
        patch("agent_brain_server.api.main.JobQueueService"),
        patch(
            "agent_brain_server.api.main.JobWorker",
            return_value=mock_job_worker,
        ),
        patch(
            "agent_brain_server.api.main.check_embedding_compatibility",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        from agent_brain_server.api.main import app

        with TestClient(app) as client:
            # Override app.state after lifespan runs
            app.state.strict_mode = strict_mode
            yield client


class TestHealthProvidersEndpoint:
    """Tests for /health/providers endpoint."""

    def test_providers_endpoint_returns_200(self, temp_project_dir: Path) -> None:
        """Test /health/providers endpoint returns 200 OK."""
        config_path = temp_project_dir / ".claude" / "agent-brain" / "config.yaml"
        shutil.copy(FIXTURES_DIR / "config_openai.yaml", config_path)

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project_dir)
            clear_settings_cache()

            with create_health_test_client() as client:
                response = client.get("/health/providers")
                assert response.status_code == 200

        finally:
            os.chdir(original_cwd)
            clear_settings_cache()

    def test_providers_response_has_required_fields(
        self, temp_project_dir: Path
    ) -> None:
        """Test response includes all required fields."""
        config_path = temp_project_dir / ".claude" / "agent-brain" / "config.yaml"
        shutil.copy(FIXTURES_DIR / "config_openai.yaml", config_path)

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project_dir)
            clear_settings_cache()

            with create_health_test_client() as client:
                response = client.get("/health/providers")
                data = response.json()

                # Check top-level required fields
                assert "config_source" in data
                assert "strict_mode" in data
                assert "validation_errors" in data
                assert "providers" in data
                assert "timestamp" in data

                # Validate types
                assert isinstance(data["strict_mode"], bool)
                assert isinstance(data["validation_errors"], list)
                assert isinstance(data["providers"], list)

        finally:
            os.chdir(original_cwd)
            clear_settings_cache()

    def test_providers_lists_embedding_and_summarization(
        self, temp_project_dir: Path
    ) -> None:
        """Test providers list includes embedding and summarization types."""
        config_path = temp_project_dir / ".claude" / "agent-brain" / "config.yaml"
        shutil.copy(FIXTURES_DIR / "config_openai.yaml", config_path)

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project_dir)
            clear_settings_cache()

            with create_health_test_client() as client:
                response = client.get("/health/providers")
                data = response.json()

                provider_types = [p["provider_type"] for p in data["providers"]]
                assert "embedding" in provider_types
                assert "summarization" in provider_types

        finally:
            os.chdir(original_cwd)
            clear_settings_cache()

    def test_providers_reports_status_for_each(
        self, temp_project_dir: Path
    ) -> None:
        """Test each provider entry has a status field."""
        config_path = temp_project_dir / ".claude" / "agent-brain" / "config.yaml"
        shutil.copy(FIXTURES_DIR / "config_openai.yaml", config_path)

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project_dir)
            clear_settings_cache()

            with create_health_test_client() as client:
                response = client.get("/health/providers")
                data = response.json()

                for provider in data["providers"]:
                    assert "status" in provider
                    assert provider["status"] in [
                        "healthy",
                        "degraded",
                        "unavailable",
                    ]
                    assert "provider_name" in provider
                    assert "model" in provider

        finally:
            os.chdir(original_cwd)
            clear_settings_cache()

    def test_providers_embedding_includes_dimensions(
        self, temp_project_dir: Path
    ) -> None:
        """Test embedding provider includes dimensions field when healthy."""
        config_path = temp_project_dir / ".claude" / "agent-brain" / "config.yaml"
        shutil.copy(FIXTURES_DIR / "config_openai.yaml", config_path)

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project_dir)
            clear_settings_cache()

            with create_health_test_client() as client:
                response = client.get("/health/providers")
                data = response.json()

                embedding_providers = [
                    p
                    for p in data["providers"]
                    if p["provider_type"] == "embedding"
                ]
                assert len(embedding_providers) > 0

                for provider in embedding_providers:
                    if provider["status"] == "healthy":
                        assert "dimensions" in provider
                        assert isinstance(provider["dimensions"], int)
                        assert provider["dimensions"] > 0

        finally:
            os.chdir(original_cwd)
            clear_settings_cache()


class TestProvidersWithAnthropicConfig:
    """Test /health/providers with Anthropic-focused config."""

    def test_providers_with_anthropic_summarization(
        self, temp_project_dir: Path
    ) -> None:
        """Test endpoint correctly reports Anthropic summarization provider."""
        config_path = temp_project_dir / ".claude" / "agent-brain" / "config.yaml"
        shutil.copy(FIXTURES_DIR / "config_anthropic.yaml", config_path)

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project_dir)
            clear_settings_cache()

            with create_health_test_client() as client:
                response = client.get("/health/providers")
                assert response.status_code == 200
                data = response.json()

                # Find summarization provider
                summ_providers = [
                    p
                    for p in data["providers"]
                    if p["provider_type"] == "summarization"
                ]
                assert len(summ_providers) > 0
                assert summ_providers[0]["provider_name"] == "anthropic"

        finally:
            os.chdir(original_cwd)
            clear_settings_cache()


class TestProvidersWithOllamaConfig:
    """Test /health/providers with Ollama-only config."""

    def test_providers_with_ollama_no_api_key_warnings(
        self, temp_project_dir: Path
    ) -> None:
        """Test Ollama config doesn't generate API key validation errors."""
        config_path = temp_project_dir / ".claude" / "agent-brain" / "config.yaml"
        shutil.copy(FIXTURES_DIR / "config_ollama_only.yaml", config_path)

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project_dir)
            clear_settings_cache()

            with create_health_test_client() as client:
                response = client.get("/health/providers")
                assert response.status_code == 200
                data = response.json()

                # Ollama config shouldn't have critical API key errors
                critical_errors = [
                    e
                    for e in data["validation_errors"]
                    if "CRITICAL" in e.upper() and "API" in e.upper()
                ]
                assert len(critical_errors) == 0

        finally:
            os.chdir(original_cwd)
            clear_settings_cache()
