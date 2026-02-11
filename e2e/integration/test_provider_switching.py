"""E2E tests for provider switching (PROV-03 verification).

These tests verify that changing config.yaml and restarting the server
results in using the new provider configuration.
"""

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_brain_server.config.provider_config import (
    clear_settings_cache,
    load_provider_settings,
    _find_config_file,
)
from agent_brain_server.providers.base import EmbeddingProviderType


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


class TestConfigFileDiscovery:
    """Tests for configuration file discovery."""

    def test_finds_config_in_project_dir(self, temp_project_dir: Path) -> None:
        """Test that config is found in .claude/agent-brain/config.yaml."""
        # Copy OpenAI config to project directory
        config_path = temp_project_dir / ".claude" / "agent-brain" / "config.yaml"
        shutil.copy(FIXTURES_DIR / "config_openai.yaml", config_path)

        # Set CWD to project directory
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project_dir)
            found = _find_config_file()
            assert found is not None
            # Resolve both paths to handle /private/var vs /var symlinks
            assert found.resolve() == config_path.resolve()
        finally:
            os.chdir(original_cwd)

    def test_env_var_override(self, temp_project_dir: Path) -> None:
        """Test AGENT_BRAIN_CONFIG env var overrides file search."""
        config_path = temp_project_dir / "custom_config.yaml"
        shutil.copy(FIXTURES_DIR / "config_ollama.yaml", config_path)

        with patch.dict(os.environ, {"AGENT_BRAIN_CONFIG": str(config_path)}):
            clear_settings_cache()
            found = _find_config_file()
            assert found == config_path


class TestProviderSwitching:
    """Tests for provider switching behavior (PROV-03)."""

    def test_switch_from_openai_to_ollama(self, temp_project_dir: Path) -> None:
        """Test switching from OpenAI to Ollama provider."""
        config_path = temp_project_dir / ".claude" / "agent-brain" / "config.yaml"

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project_dir)

            # Start with OpenAI config
            shutil.copy(FIXTURES_DIR / "config_openai.yaml", config_path)
            clear_settings_cache()

            settings1 = load_provider_settings()
            assert settings1.embedding.provider == EmbeddingProviderType.OPENAI
            assert settings1.embedding.model == "text-embedding-3-large"

            # Switch to Ollama config
            shutil.copy(FIXTURES_DIR / "config_ollama.yaml", config_path)
            clear_settings_cache()

            settings2 = load_provider_settings()
            assert settings2.embedding.provider == EmbeddingProviderType.OLLAMA
            assert settings2.embedding.model == "nomic-embed-text"

        finally:
            os.chdir(original_cwd)

    def test_dimension_mismatch_detection(self, temp_project_dir: Path) -> None:
        """Test that dimension mismatch is detected after provider switch."""
        from agent_brain_server.storage.vector_store import (
            EmbeddingMetadata,
            VectorStoreManager,
        )
        from agent_brain_server.providers.exceptions import ProviderMismatchError

        store = VectorStoreManager()

        # Simulate existing OpenAI index (3072 dimensions)
        stored_metadata = EmbeddingMetadata(
            provider="openai",
            model="text-embedding-3-large",
            dimensions=3072,
        )

        # Try to use Ollama (768 dimensions) - should raise
        with pytest.raises(ProviderMismatchError) as exc_info:
            store.validate_embedding_compatibility(
                provider="ollama",
                model="nomic-embed-text",
                dimensions=768,
                stored_metadata=stored_metadata,
            )

        error = exc_info.value
        assert "openai" in str(error)
        assert "ollama" in str(error)
        assert "text-embedding-3-large" in str(error)


class TestProviderInstantiation:
    """Tests for provider instantiation from config."""

    def test_ollama_provider_no_api_key_needed(self, temp_project_dir: Path) -> None:
        """Test Ollama provider doesn't require API key."""
        config_path = temp_project_dir / ".claude" / "agent-brain" / "config.yaml"
        shutil.copy(FIXTURES_DIR / "config_ollama.yaml", config_path)

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project_dir)
            clear_settings_cache()

            settings = load_provider_settings()

            # Ollama config should not need API key
            assert settings.embedding.get_api_key() is None
            assert settings.summarization.get_api_key() is None

        finally:
            os.chdir(original_cwd)
