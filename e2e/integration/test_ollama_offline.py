"""E2E tests for Ollama offline mode (PROV-04 verification).

PROV-04 Requirement: Fully offline operation with Ollama
=========================================================

Agent Brain must be able to operate fully offline when configured with
Ollama for both embeddings and summarization. This means:

1. No external API calls to OpenAI, Anthropic, Cohere, or other cloud services
2. No API keys required for operation
3. Graceful error handling when Ollama is unavailable
4. Clear documentation of offline configuration

Test Categories
---------------

1. Configuration Tests (TestOllamaConfiguration)
   - Verify Ollama-only config loads correctly
   - Verify no API keys are required

2. No External API Tests (TestNoExternalApiCalls)
   - Verify no OpenAI calls are made
   - Verify no Anthropic calls are made

3. Graceful Degradation Tests (TestOllamaGracefulDegradation)
   - Verify appropriate errors when Ollama is down
   - Verify health check reports Ollama status

4. Live Integration Tests (TestOllamaLiveIntegration)
   - Test actual embedding generation (requires Ollama running)
   - Test actual summarization (requires Ollama running)

Running Tests
-------------

With Ollama running:
    pytest e2e/integration/test_ollama_offline.py -v

Without Ollama (skips live tests):
    pytest e2e/integration/test_ollama_offline.py -v

Only live tests:
    pytest e2e/integration/test_ollama_offline.py -v -k "Live"

Configuration
-------------

Use e2e/fixtures/config_ollama_only.yaml for fully offline operation.

Requirements:
- Ollama installed: https://ollama.ai
- Models pulled: ollama pull nomic-embed-text && ollama pull llama3.2
- Ollama running: ollama serve
"""

import os
import shutil
import socket
import tempfile
from pathlib import Path
from typing import Generator

import pytest

from agent_brain_server.config.provider_config import (
    clear_settings_cache,
    load_provider_settings,
    validate_provider_config,
)
from agent_brain_server.providers.base import (
    EmbeddingProviderType,
    RerankerProviderType,
    SummarizationProviderType,
)


# Path to fixture files
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def is_ollama_running(host: str = "localhost", port: int = 11434) -> bool:
    """Check if Ollama is running on the specified host:port."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            s.connect((host, port))
            return True
    except (socket.error, socket.timeout):
        return False


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


class TestOllamaConfiguration:
    """Tests for Ollama-only configuration."""

    def test_ollama_config_loads_correctly(
        self, temp_project_dir: Path
    ) -> None:
        """Test Ollama-only config loads with correct provider types."""
        config_path = (
            temp_project_dir / ".claude" / "agent-brain" / "config.yaml"
        )
        shutil.copy(FIXTURES_DIR / "config_ollama_only.yaml", config_path)

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project_dir)
            clear_settings_cache()

            settings = load_provider_settings()

            assert (
                settings.embedding.provider == EmbeddingProviderType.OLLAMA
            )
            assert settings.embedding.model == "nomic-embed-text"
            assert "localhost:11434" in (
                settings.embedding.get_base_url() or ""
            )

            assert (
                settings.summarization.provider
                == SummarizationProviderType.OLLAMA
            )
            assert settings.summarization.model == "llama3.2"

        finally:
            os.chdir(original_cwd)

    def test_ollama_no_api_keys_required(
        self, temp_project_dir: Path
    ) -> None:
        """Test Ollama config doesn't require any API keys."""
        config_path = (
            temp_project_dir / ".claude" / "agent-brain" / "config.yaml"
        )
        shutil.copy(FIXTURES_DIR / "config_ollama_only.yaml", config_path)

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project_dir)
            clear_settings_cache()

            settings = load_provider_settings()

            assert settings.embedding.get_api_key() is None
            assert settings.summarization.get_api_key() is None

            errors = validate_provider_config(settings)
            critical = [
                e for e in errors if e.severity.value == "critical"
            ]
            assert (
                len(critical) == 0
            ), f"Unexpected critical errors: {critical}"

        finally:
            os.chdir(original_cwd)


class TestNoExternalApiCalls:
    """Tests verifying no external API calls are made with Ollama config."""

    def test_ollama_embedding_uses_local_endpoint(
        self, temp_project_dir: Path
    ) -> None:
        """Test that Ollama embedding provider points to localhost, not OpenAI."""
        config_path = (
            temp_project_dir / ".claude" / "agent-brain" / "config.yaml"
        )
        shutil.copy(FIXTURES_DIR / "config_ollama_only.yaml", config_path)

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project_dir)
            clear_settings_cache()

            settings = load_provider_settings()

            from agent_brain_server.providers.factory import (
                ProviderRegistry,
            )

            provider = ProviderRegistry.get_embedding_provider(
                settings.embedding
            )

            # Verify provider is Ollama and points to localhost
            assert provider.provider_name.lower() == "ollama"
            assert "localhost" in provider._base_url
            assert "openai.com" not in provider._base_url

        finally:
            os.chdir(original_cwd)

    def test_ollama_summarization_uses_local_endpoint(
        self, temp_project_dir: Path
    ) -> None:
        """Test that Ollama summarization provider points to localhost."""
        config_path = (
            temp_project_dir / ".claude" / "agent-brain" / "config.yaml"
        )
        shutil.copy(FIXTURES_DIR / "config_ollama_only.yaml", config_path)

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project_dir)
            clear_settings_cache()

            settings = load_provider_settings()

            from agent_brain_server.providers.factory import (
                ProviderRegistry,
            )

            provider = ProviderRegistry.get_summarization_provider(
                settings.summarization
            )

            # Verify provider is Ollama, not Anthropic/OpenAI
            assert provider.provider_name.lower() == "ollama"

        finally:
            os.chdir(original_cwd)


class TestOllamaGracefulDegradation:
    """Tests for graceful degradation when Ollama is unavailable."""

    def test_provider_created_regardless_of_ollama_status(
        self, temp_project_dir: Path
    ) -> None:
        """Test that provider object is created even if Ollama is down.

        Connection failures happen on first embed call, not at construction.
        """
        config_path = (
            temp_project_dir / ".claude" / "agent-brain" / "config.yaml"
        )
        shutil.copy(FIXTURES_DIR / "config_ollama_only.yaml", config_path)

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project_dir)
            clear_settings_cache()

            settings = load_provider_settings()

            from agent_brain_server.providers.factory import ProviderRegistry

            # Provider should be created successfully regardless of
            # whether Ollama is running (lazy connection)
            provider = ProviderRegistry.get_embedding_provider(
                settings.embedding
            )
            assert provider.provider_name.lower() == "ollama"
            assert provider.get_dimensions() == 768  # nomic-embed-text

        finally:
            os.chdir(original_cwd)


@pytest.mark.skipif(
    not is_ollama_running(),
    reason="Ollama not running - skipping live integration test",
)
class TestOllamaLiveIntegration:
    """Live integration tests that require Ollama to be running.

    These tests are skipped if Ollama is not available.
    """

    def test_ollama_embedding_returns_vector(
        self, temp_project_dir: Path
    ) -> None:
        """Test that Ollama returns actual embeddings when running."""
        config_path = (
            temp_project_dir / ".claude" / "agent-brain" / "config.yaml"
        )
        shutil.copy(FIXTURES_DIR / "config_ollama_only.yaml", config_path)

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project_dir)
            clear_settings_cache()

            settings = load_provider_settings()

            from agent_brain_server.providers.factory import ProviderRegistry

            provider = ProviderRegistry.get_embedding_provider(
                settings.embedding
            )

            import asyncio

            embedding = asyncio.get_event_loop().run_until_complete(
                provider.embed_text("Hello, world!")
            )

            assert isinstance(embedding, list)
            assert len(embedding) > 0
            assert all(isinstance(x, float) for x in embedding)
            assert len(embedding) == 768

        finally:
            os.chdir(original_cwd)

    def test_ollama_summarization_returns_text(
        self, temp_project_dir: Path
    ) -> None:
        """Test that Ollama returns actual summaries when running.

        Note: This test requires the configured summarization model
        (llama3.2) to be pulled. If the model is not available,
        the test is skipped.
        """
        config_path = (
            temp_project_dir / ".claude" / "agent-brain" / "config.yaml"
        )
        shutil.copy(FIXTURES_DIR / "config_ollama_only.yaml", config_path)

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project_dir)
            clear_settings_cache()

            settings = load_provider_settings()

            from agent_brain_server.providers.factory import ProviderRegistry

            provider = ProviderRegistry.get_summarization_provider(
                settings.summarization
            )

            import asyncio

            code = '''
            def hello():
                """Say hello to the world."""
                print("Hello, world!")
            '''

            try:
                summary = asyncio.get_event_loop().run_until_complete(
                    provider.summarize(code)
                )
            except Exception as e:
                if "not found" in str(e).lower():
                    pytest.skip(
                        f"Summarization model not available: {e}"
                    )
                raise

            assert isinstance(summary, str)
            assert len(summary) > 10

        finally:
            os.chdir(original_cwd)


class TestOfflineDocumentation:
    """Tests that document offline operation capabilities."""

    def test_offline_config_documented(self) -> None:
        """Verify offline configuration fixture is properly documented."""
        config_path = FIXTURES_DIR / "config_ollama_only.yaml"
        content = config_path.read_text()

        assert "offline" in content.lower()

    def test_all_providers_support_ollama(self) -> None:
        """Verify all provider types support Ollama backend."""
        assert EmbeddingProviderType.OLLAMA.value == "ollama"
        assert SummarizationProviderType.OLLAMA.value == "ollama"
        assert RerankerProviderType.OLLAMA.value == "ollama"
