"""E2E tests for Cohere provider (TEST-04).

This module tests Cohere embedding provider configuration, instantiation,
and live API integration when COHERE_API_KEY is available.
"""

import asyncio
import os
import shutil
import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import patch

import pytest

from agent_brain_server.config.provider_config import (
    clear_settings_cache,
    load_provider_settings,
    validate_provider_config,
)
from agent_brain_server.providers.base import EmbeddingProviderType
from agent_brain_server.providers.factory import ProviderRegistry

# Path to fixture files
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"

pytestmark = pytest.mark.cohere


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


class TestCohereConfiguration:
    """Tests for Cohere provider configuration."""

    def test_cohere_config_loads_correctly(self, temp_project_dir: Path) -> None:
        """Test Cohere config loads with correct provider types and model."""
        config_path = temp_project_dir / ".claude" / "agent-brain" / "config.yaml"
        shutil.copy(FIXTURES_DIR / "config_cohere.yaml", config_path)

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project_dir)
            clear_settings_cache()

            settings = load_provider_settings()

            assert settings.embedding.provider == EmbeddingProviderType.COHERE
            assert settings.embedding.model == "embed-english-v3.0"
            assert settings.embedding.api_key_env == "COHERE_API_KEY"

        finally:
            os.chdir(original_cwd)

    def test_cohere_requires_api_key(self, temp_project_dir: Path) -> None:
        """Test config validation reports CRITICAL error if COHERE_API_KEY missing."""
        config_path = temp_project_dir / ".claude" / "agent-brain" / "config.yaml"
        shutil.copy(FIXTURES_DIR / "config_cohere.yaml", config_path)

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project_dir)
            clear_settings_cache()

            # Temporarily unset COHERE_API_KEY
            with patch.dict(os.environ, {"COHERE_API_KEY": ""}, clear=False):
                settings = load_provider_settings()
                errors = validate_provider_config(settings)

                critical = [e for e in errors if e.severity.value == "critical"]
                assert (
                    len(critical) > 0
                ), "Expected CRITICAL error when COHERE_API_KEY missing"
                assert any("COHERE_API_KEY" in str(e) for e in critical)

        finally:
            os.chdir(original_cwd)

    def test_cohere_provider_instantiates(
        self, temp_project_dir: Path, check_cohere_key: None
    ) -> None:
        """Test Cohere provider instantiates correctly (requires API key)."""
        config_path = temp_project_dir / ".claude" / "agent-brain" / "config.yaml"
        shutil.copy(FIXTURES_DIR / "config_cohere.yaml", config_path)

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project_dir)
            clear_settings_cache()

            settings = load_provider_settings()
            provider = ProviderRegistry.get_embedding_provider(settings.embedding)

            assert provider.provider_name == "Cohere"

        finally:
            os.chdir(original_cwd)

    def test_cohere_dimensions(
        self, temp_project_dir: Path, check_cohere_key: None
    ) -> None:
        """Test Cohere provider returns correct dimensions for embed-english-v3.0."""
        config_path = temp_project_dir / ".claude" / "agent-brain" / "config.yaml"
        shutil.copy(FIXTURES_DIR / "config_cohere.yaml", config_path)

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project_dir)
            clear_settings_cache()

            settings = load_provider_settings()
            provider = ProviderRegistry.get_embedding_provider(settings.embedding)

            assert provider.get_dimensions() == 1024  # embed-english-v3.0

        finally:
            os.chdir(original_cwd)


class TestCohereLiveIntegration:
    """Live integration tests requiring COHERE_API_KEY."""

    def test_cohere_embedding_returns_vector(
        self, temp_project_dir: Path, check_cohere_key: None
    ) -> None:
        """Test Cohere returns actual embeddings when API key is available."""
        config_path = temp_project_dir / ".claude" / "agent-brain" / "config.yaml"
        shutil.copy(FIXTURES_DIR / "config_cohere.yaml", config_path)

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project_dir)
            clear_settings_cache()

            settings = load_provider_settings()
            provider = ProviderRegistry.get_embedding_provider(settings.embedding)

            embedding = asyncio.get_event_loop().run_until_complete(
                provider.embed_text("Hello, world!")
            )

            assert isinstance(embedding, list)
            assert len(embedding) == 1024  # embed-english-v3.0 dimensions
            assert all(isinstance(x, float) for x in embedding)

        finally:
            os.chdir(original_cwd)
