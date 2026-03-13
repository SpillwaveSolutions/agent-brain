"""Regression tests for Agent Brain setup wizard content.

These tests ensure that required interactive wizard prompts remain present
in the plugin command markdown files. If a future refactor silently removes
a wizard step, these tests fail before merge.
"""
import re
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).parents[2] / "agent-brain-plugin"
SETUP_CMD = PLUGIN_ROOT / "commands" / "agent-brain-setup.md"
CONFIG_CMD = PLUGIN_ROOT / "commands" / "agent-brain-config.md"


@pytest.fixture(autouse=True)
def require_plugin_dir() -> None:
    """Skip all tests if the plugin directory does not exist.

    Graceful degradation for CI environments that only check out
    agent-brain-server without the plugin directory.
    """
    if not PLUGIN_ROOT.exists():
        pytest.skip(
            f"Plugin directory not found at {PLUGIN_ROOT} — "
            "skipping wizard regression tests"
        )


def _read(path: Path) -> str:
    """Read file content, failing with a descriptive error if missing."""
    if not path.exists():
        pytest.fail(
            f"Wizard regression: required file not found: {path}\n"
            "This file must exist for the wizard to work."
        )
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# agent-brain-setup.md — wizard content assertions
# ---------------------------------------------------------------------------


def test_setup_wizard_asks_embedding_provider() -> None:
    """Wizard must ask the user about embedding provider selection."""
    content = _read(SETUP_CMD)
    has_embedding = "embedding" in content.lower()
    has_ask = "AskUserQuestion" in content
    assert has_embedding and has_ask, (
        "Wizard regression detected — agent-brain-setup.md is missing required "
        "section: embedding provider prompt. "
        "Restore the embedding provider wizard step (Step 2)."
    )


def test_setup_wizard_asks_summarization_provider() -> None:
    """Wizard must ask the user about summarization provider selection."""
    content = _read(SETUP_CMD)
    assert re.search(r"summarization", content, re.IGNORECASE), (
        "Wizard regression detected — agent-brain-setup.md is missing required "
        "section: summarization provider prompt. "
        "Restore the summarization provider wizard step (Step 3)."
    )


def test_setup_wizard_asks_storage_backend() -> None:
    """Wizard must ask the user about storage backend (ChromaDB vs PostgreSQL)."""
    content = _read(SETUP_CMD)
    has_chroma = "ChromaDB" in content
    has_postgres = "PostgreSQL" in content
    assert has_chroma and has_postgres, (
        "Wizard regression detected — agent-brain-setup.md is missing required "
        "section: storage backend selection. "
        "Restore the storage backend wizard step (Step 4). "
        f"ChromaDB present: {has_chroma}, PostgreSQL present: {has_postgres}"
    )


def test_setup_wizard_asks_graphrag() -> None:
    """Wizard must ask the user about GraphRAG enablement."""
    content = _read(SETUP_CMD)
    assert re.search(r"graphrag", content, re.IGNORECASE), (
        "Wizard regression detected — agent-brain-setup.md is missing required "
        "section: GraphRAG configuration prompt. "
        "Restore the GraphRAG wizard step (Step 5)."
    )


def test_setup_wizard_asks_query_mode() -> None:
    """Wizard must ask the user about default query mode selection."""
    content = _read(SETUP_CMD)
    assert re.search(r"query mode", content, re.IGNORECASE), (
        "Wizard regression detected — agent-brain-setup.md is missing required "
        "section: query mode selection. "
        "Restore the query mode wizard step (Step 6)."
    )


def test_setup_wizard_has_multiple_ask_blocks() -> None:
    """Wizard must contain at least 5 AskUserQuestion blocks covering all dimensions."""
    content = _read(SETUP_CMD)
    count = content.count("AskUserQuestion")
    assert count >= 5, (
        f"Wizard regression detected — agent-brain-setup.md has only {count} "
        "AskUserQuestion block(s), expected >= 5. "
        "Restore wizard steps for: embedding provider, summarization provider, "
        "storage backend, GraphRAG, and query mode."
    )


def test_setup_wizard_writes_config_yaml() -> None:
    """Wizard must include a step to write config.yaml."""
    content = _read(SETUP_CMD)
    assert re.search(r"config\.yaml", content), (
        "Wizard regression detected — agent-brain-setup.md is missing required "
        "section: config.yaml write step. "
        "Restore the config.yaml write step (Step 7)."
    )


# ---------------------------------------------------------------------------
# agent-brain-config.md — provider selection assertions
# ---------------------------------------------------------------------------


def test_config_wizard_has_provider_selection() -> None:
    """Config command must contain AskUserQuestion for provider selection."""
    content = _read(CONFIG_CMD)
    assert "AskUserQuestion" in content, (
        "Wizard regression detected — agent-brain-config.md is missing required "
        "section: AskUserQuestion for provider selection. "
        "Restore the provider selection prompt in the config command."
    )


def test_config_wizard_mentions_chromadb() -> None:
    """Config command must mention ChromaDB as a storage option."""
    content = _read(CONFIG_CMD)
    assert "ChromaDB" in content, (
        "Wizard regression detected — agent-brain-config.md is missing required "
        "section: ChromaDB storage backend mention. "
        "Restore the storage backend section in the config command."
    )


def test_config_wizard_mentions_postgresql() -> None:
    """Config command must mention PostgreSQL as a storage option."""
    content = _read(CONFIG_CMD)
    assert "PostgreSQL" in content, (
        "Wizard regression detected — agent-brain-config.md is missing required "
        "section: PostgreSQL storage backend mention. "
        "Restore the storage backend section in the config command."
    )


def test_config_wizard_mentions_ollama() -> None:
    """Config command must mention Ollama as a free local provider option."""
    content = _read(CONFIG_CMD)
    assert "Ollama" in content, (
        "Wizard regression detected — agent-brain-config.md is missing required "
        "section: Ollama provider mention. "
        "Restore the Ollama provider option in the config command."
    )
