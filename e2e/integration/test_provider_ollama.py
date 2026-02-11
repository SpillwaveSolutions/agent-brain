"""E2E tests for Ollama provider (TEST-03).

This module extends test_ollama_offline.py with additional Ollama-specific
E2E tests for reranker config, registry checks, and full-stack validation.
"""

import asyncio
import os
import shutil
import tempfile
from pathlib import Path
from typing import Generator

import pytest

from agent_brain_server.config.provider_config import (
    clear_settings_cache,
    load_provider_settings,
)
from agent_brain_server.providers.factory import ProviderRegistry

# Import helper from test_ollama_offline
from .test_ollama_offline import is_ollama_running

# Path to fixture files
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"

pytestmark = pytest.mark.ollama


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


class TestOllamaRerankerConfig:
    """Tests for Ollama reranker configuration."""

    def test_ollama_reranker_config_loads(self, temp_project_dir: Path) -> None:
        """Test Ollama reranker config loads with correct model."""
        config_path = temp_project_dir / ".claude" / "agent-brain" / "config.yaml"
        shutil.copy(FIXTURES_DIR / "config_ollama_only.yaml", config_path)

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project_dir)
            clear_settings_cache()

            settings = load_provider_settings()

            assert settings.reranker is not None
            assert str(settings.reranker.provider) == "ollama"
            assert settings.reranker.model == "llama3.2"

        finally:
            os.chdir(original_cwd)

    def test_ollama_full_stack_no_api_keys(self, temp_project_dir: Path) -> None:
        """Test Ollama full stack requires no API keys."""
        config_path = temp_project_dir / ".claude" / "agent-brain" / "config.yaml"
        shutil.copy(FIXTURES_DIR / "config_ollama_only.yaml", config_path)

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project_dir)
            clear_settings_cache()

            settings = load_provider_settings()

            # Verify embedding and summarization providers have no API key requirement
            assert settings.embedding.get_api_key() is None
            assert settings.summarization.get_api_key() is None
            # Reranker doesn't have get_api_key() method, but Ollama reranker doesn't need API key

        finally:
            os.chdir(original_cwd)


class TestOllamaProviderRegistry:
    """Tests for Ollama provider registry checks."""

    def test_ollama_embedding_in_registry(self) -> None:
        """Test Ollama is available as embedding provider in registry."""
        available = ProviderRegistry.get_available_embedding_providers()
        assert "ollama" in available

    def test_ollama_summarization_in_registry(self) -> None:
        """Test Ollama is available as summarization provider in registry."""
        available = ProviderRegistry.get_available_summarization_providers()
        assert "ollama" in available


@pytest.mark.skipif(
    not is_ollama_running(),
    reason="Ollama not running - skipping live full stack test",
)
class TestOllamaLiveFullStack:
    """Live integration tests requiring Ollama to be running."""

    def test_ollama_embedding_and_summarization_together(
        self, temp_project_dir: Path
    ) -> None:
        """Test Ollama embedding and summarization work together in full stack."""
        config_path = temp_project_dir / ".claude" / "agent-brain" / "config.yaml"
        shutil.copy(FIXTURES_DIR / "config_ollama_only.yaml", config_path)

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project_dir)
            clear_settings_cache()

            settings = load_provider_settings()

            # Get both providers
            embedding_provider = ProviderRegistry.get_embedding_provider(
                settings.embedding
            )
            summarization_provider = ProviderRegistry.get_summarization_provider(
                settings.summarization
            )

            # Test embedding
            embedding = asyncio.get_event_loop().run_until_complete(
                embedding_provider.embed_text("Hello from Ollama!")
            )
            assert isinstance(embedding, list)
            assert len(embedding) == 768  # nomic-embed-text dimensions
            assert all(isinstance(x, float) for x in embedding)

            # Test summarization
            code = '''
def greet(name: str) -> str:
    """Return a greeting message."""
    return f"Hello, {name}!"
'''

            try:
                summary = asyncio.get_event_loop().run_until_complete(
                    summarization_provider.summarize(code)
                )
                assert isinstance(summary, str)
                assert len(summary) > 10
            except Exception as e:
                if "not found" in str(e).lower():
                    pytest.skip(f"Summarization model not available: {e}")
                raise

        finally:
            os.chdir(original_cwd)
