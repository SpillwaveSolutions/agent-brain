"""E2E tests for /health/providers endpoint (TEST-05).

This module tests the health providers endpoint that reports status
of all configured providers.
"""

import os
import shutil
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_brain_server.config.provider_config import clear_settings_cache

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


def create_test_app_with_config(config_file: str) -> FastAPI:
    """Create a minimal FastAPI app for testing /health/providers endpoint.

    Args:
        config_file: Name of the config fixture file to use

    Returns:
        FastAPI app with /health/providers endpoint
    """

    @asynccontextmanager
    async def minimal_lifespan(app: FastAPI):
        # Minimal app.state setup
        app.state.strict_mode = False
        yield

    app = FastAPI(lifespan=minimal_lifespan)

    # Import and include health router
    from agent_brain_server.api.routers import health_router

    app.include_router(health_router, prefix="/health", tags=["Health"])

    return app


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

            app = create_test_app_with_config("config_openai.yaml")

            with TestClient(app) as client:
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

            app = create_test_app_with_config("config_openai.yaml")

            with TestClient(app) as client:
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

            app = create_test_app_with_config("config_openai.yaml")

            with TestClient(app) as client:
                response = client.get("/health/providers")
                data = response.json()

                provider_types = [p["provider_type"] for p in data["providers"]]
                assert "embedding" in provider_types
                assert "summarization" in provider_types

        finally:
            os.chdir(original_cwd)
            clear_settings_cache()

    def test_providers_reports_status_for_each(self, temp_project_dir: Path) -> None:
        """Test each provider entry has a status field."""
        config_path = temp_project_dir / ".claude" / "agent-brain" / "config.yaml"
        shutil.copy(FIXTURES_DIR / "config_openai.yaml", config_path)

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project_dir)
            clear_settings_cache()

            app = create_test_app_with_config("config_openai.yaml")

            with TestClient(app) as client:
                response = client.get("/health/providers")
                data = response.json()

                for provider in data["providers"]:
                    assert "status" in provider
                    assert provider["status"] in ["healthy", "degraded", "unavailable"]
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

            app = create_test_app_with_config("config_openai.yaml")

            with TestClient(app) as client:
                response = client.get("/health/providers")
                data = response.json()

                embedding_providers = [
                    p for p in data["providers"] if p["provider_type"] == "embedding"
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

            app = create_test_app_with_config("config_anthropic.yaml")

            with TestClient(app) as client:
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

            app = create_test_app_with_config("config_ollama_only.yaml")

            with TestClient(app) as client:
                response = client.get("/health/providers")
                assert response.status_code == 200
                data = response.json()

                # Ollama config shouldn't have critical validation errors for missing keys
                critical_errors = [
                    e
                    for e in data["validation_errors"]
                    if "CRITICAL" in e.upper() and "API" in e.upper()
                ]
                # Should have no critical API key errors for Ollama
                assert len(critical_errors) == 0

        finally:
            os.chdir(original_cwd)
            clear_settings_cache()
