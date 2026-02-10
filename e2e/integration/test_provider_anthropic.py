"""E2E tests for Anthropic provider (TEST-02).

This module tests Anthropic summarization provider configuration, instantiation,
and live API integration when ANTHROPIC_API_KEY is available.
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
from agent_brain_server.providers.base import SummarizationProviderType
from agent_brain_server.providers.factory import ProviderRegistry

# Path to fixture files
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"

pytestmark = pytest.mark.anthropic


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


class TestAnthropicConfiguration:
    """Tests for Anthropic provider configuration."""

    def test_anthropic_config_loads_correctly(self, temp_project_dir: Path) -> None:
        """Test Anthropic config loads with correct provider and model."""
        config_path = temp_project_dir / ".claude" / "agent-brain" / "config.yaml"
        shutil.copy(FIXTURES_DIR / "config_anthropic.yaml", config_path)

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project_dir)
            clear_settings_cache()

            settings = load_provider_settings()

            assert (
                settings.summarization.provider == SummarizationProviderType.ANTHROPIC
            )
            assert settings.summarization.model == "claude-haiku-4-5-20251001"
            assert settings.summarization.api_key_env == "ANTHROPIC_API_KEY"

        finally:
            os.chdir(original_cwd)

    def test_anthropic_requires_api_key(self, temp_project_dir: Path) -> None:
        """Test config validation reports CRITICAL error if ANTHROPIC_API_KEY missing."""
        config_path = temp_project_dir / ".claude" / "agent-brain" / "config.yaml"
        shutil.copy(FIXTURES_DIR / "config_anthropic.yaml", config_path)

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project_dir)
            clear_settings_cache()

            # Temporarily unset ANTHROPIC_API_KEY
            with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}, clear=False):
                settings = load_provider_settings()
                errors = validate_provider_config(settings)

                critical = [e for e in errors if e.severity.value == "critical"]
                assert (
                    len(critical) > 0
                ), "Expected CRITICAL error when ANTHROPIC_API_KEY missing"
                assert any("ANTHROPIC_API_KEY" in str(e) for e in critical)

        finally:
            os.chdir(original_cwd)

    def test_anthropic_provider_instantiates(self, temp_project_dir: Path) -> None:
        """Test Anthropic provider instantiates correctly."""
        config_path = temp_project_dir / ".claude" / "agent-brain" / "config.yaml"
        shutil.copy(FIXTURES_DIR / "config_anthropic.yaml", config_path)

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project_dir)
            clear_settings_cache()

            settings = load_provider_settings()
            provider = ProviderRegistry.get_summarization_provider(
                settings.summarization
            )

            assert provider.provider_name == "Anthropic"

        finally:
            os.chdir(original_cwd)


class TestAnthropicLiveIntegration:
    """Live integration tests requiring ANTHROPIC_API_KEY."""

    def test_anthropic_summarization_returns_text(
        self, temp_project_dir: Path, check_anthropic_key: None
    ) -> None:
        """Test Anthropic returns actual summaries when API key is available."""
        config_path = temp_project_dir / ".claude" / "agent-brain" / "config.yaml"
        shutil.copy(FIXTURES_DIR / "config_anthropic.yaml", config_path)

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project_dir)
            clear_settings_cache()

            settings = load_provider_settings()
            provider = ProviderRegistry.get_summarization_provider(
                settings.summarization
            )

            code = '''
def calculate_sum(a: int, b: int) -> int:
    """Calculate the sum of two integers."""
    return a + b
'''

            summary = asyncio.get_event_loop().run_until_complete(
                provider.summarize(code)
            )

            assert isinstance(summary, str)
            assert len(summary) > 10, "Summary should be non-trivial"

        finally:
            os.chdir(original_cwd)
