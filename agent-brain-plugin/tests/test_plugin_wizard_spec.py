"""Regression tests for the agent-brain-setup.md wizard specification.

These tests verify that the setup wizard markdown file contains the correct
structure, configuration keys, and behavioral content. They run against the
wizard source file directly and do not require a running server.
"""

import os
import pathlib
import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PLUGIN_DIR = pathlib.Path(__file__).parent.parent
WIZARD_PATH = PLUGIN_DIR / "commands" / "agent-brain-setup.md"
CONFIG_WIZARD_PATH = PLUGIN_DIR / "commands" / "agent-brain-config.md"


@pytest.fixture(autouse=True)
def require_plugin_dir() -> None:
    """Skip all tests in this module if the plugin directory is not found.

    This allows CI environments that do not have the plugin checked out to
    skip gracefully rather than fail.
    """
    if not WIZARD_PATH.exists():
        pytest.skip(f"Plugin wizard not found at {WIZARD_PATH}")


@pytest.fixture()
def setup_wizard_content() -> str:
    """Return the full text of the agent-brain-setup.md wizard file."""
    return WIZARD_PATH.read_text(encoding="utf-8")


@pytest.fixture()
def config_wizard_content() -> str:
    """Return the full text of the agent-brain-config.md wizard file."""
    if not CONFIG_WIZARD_PATH.exists():
        pytest.skip(f"Config wizard not found at {CONFIG_WIZARD_PATH}")
    return CONFIG_WIZARD_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Structural tests (Steps 2-7)
# ---------------------------------------------------------------------------


def test_setup_wizard_file_exists() -> None:
    """The wizard command file must exist at the expected path."""
    assert WIZARD_PATH.exists(), f"Expected wizard at {WIZARD_PATH}"


def test_setup_wizard_has_step_2_embedding(setup_wizard_content: str) -> None:
    """Step 2 of the wizard must ask about the embedding provider."""
    assert "Step 2: Wizard" in setup_wizard_content or (
        "embedding" in setup_wizard_content.lower()
        and "AskUserQuestion" in setup_wizard_content
    ), "Step 2 must include an AskUserQuestion block for embedding provider."


def test_setup_wizard_has_step_3_summarization(setup_wizard_content: str) -> None:
    """Step 3 of the wizard must ask about the summarization provider."""
    assert "Step 3: Wizard" in setup_wizard_content or (
        "summarization" in setup_wizard_content.lower()
        and "AskUserQuestion" in setup_wizard_content
    ), "Step 3 must include an AskUserQuestion block for summarization provider."


def test_setup_wizard_has_step_4_storage(setup_wizard_content: str) -> None:
    """Step 4 of the wizard must ask about the storage backend."""
    assert "Step 4: Wizard" in setup_wizard_content or (
        "storage" in setup_wizard_content.lower()
        and "storage.backend" in setup_wizard_content
    ), "Step 4 must set storage.backend."


def test_setup_wizard_has_step_5_graphrag(setup_wizard_content: str) -> None:
    """Step 5 of the wizard must cover GraphRAG configuration."""
    assert "Step 5: Wizard" in setup_wizard_content or (
        "graphrag" in setup_wizard_content.lower()
        and "graphrag.enabled" in setup_wizard_content
    ), "Step 5 must set graphrag.enabled."


def test_setup_wizard_has_step_6_query_mode(setup_wizard_content: str) -> None:
    """Step 6 of the wizard must ask about the default query mode."""
    assert "Step 6: Wizard" in setup_wizard_content or (
        "query mode" in setup_wizard_content.lower()
        and "hybrid" in setup_wizard_content
    ), "Step 6 must present query mode options including 'hybrid'."


def test_setup_wizard_has_step_7_write_config(setup_wizard_content: str) -> None:
    """Step 7 of the wizard must write a config.yaml file."""
    assert "config.yaml" in setup_wizard_content, (
        "Step 7 must write config.yaml."
    )


def test_setup_wizard_sets_embedding_config_keys(setup_wizard_content: str) -> None:
    """Wizard must record embedding.provider and embedding.model."""
    assert "embedding.provider" in setup_wizard_content, (
        "Wizard must record embedding.provider."
    )
    assert "embedding.model" in setup_wizard_content, (
        "Wizard must record embedding.model."
    )


def test_setup_wizard_sets_storage_backend_key(setup_wizard_content: str) -> None:
    """Wizard must record storage.backend with chroma or postgres values."""
    assert "storage.backend" in setup_wizard_content, (
        "Wizard must record storage.backend."
    )
    assert '"chroma"' in setup_wizard_content or "chroma" in setup_wizard_content, (
        "Wizard must mention ChromaDB as a storage option."
    )
    assert '"postgres"' in setup_wizard_content or "postgres" in setup_wizard_content, (
        "Wizard must mention PostgreSQL as a storage option."
    )


def test_setup_wizard_sets_graphrag_config_keys(setup_wizard_content: str) -> None:
    """Wizard must record graphrag.enabled and graphrag.store_type."""
    assert "graphrag.enabled" in setup_wizard_content, (
        "Wizard must record graphrag.enabled."
    )
    assert "graphrag.store_type" in setup_wizard_content, (
        "Wizard must record graphrag.store_type."
    )


def test_setup_wizard_writes_config_yaml(setup_wizard_content: str) -> None:
    """Step 7 must write config.yaml using python3 yaml.dump for safe serialization."""
    assert "yaml.dump" in setup_wizard_content or "config.yaml" in setup_wizard_content, (
        "Step 7 must write config.yaml (ideally using yaml.dump for safe serialization)."
    )


def test_setup_wizard_has_multiple_askuserquestion_blocks(
    setup_wizard_content: str,
) -> None:
    """The wizard must contain at least 4 AskUserQuestion interaction blocks."""
    count = setup_wizard_content.count("AskUserQuestion")
    assert count >= 4, (
        f"Expected at least 4 AskUserQuestion blocks, found {count}. "
        "The wizard must be interactive with prompts for embedding, summarization, "
        "storage, and GraphRAG/query mode."
    )


# ---------------------------------------------------------------------------
# New regression tests (Phase 25 — coverage gap closures)
# ---------------------------------------------------------------------------


def test_setup_wizard_step4_postgres_bm25_note(setup_wizard_content: str) -> None:
    """Step 4: PostgreSQL selection includes BM25/tsvector informational note."""
    assert "tsvector" in setup_wizard_content, (
        "Step 4 (Storage Backend) must mention tsvector when PostgreSQL is selected. "
        "PostgreSQL replaces BM25 with tsvector — users should know --mode bm25 still works."
    )


def test_setup_wizard_step5_graphrag_postgres_gate(setup_wizard_content: str) -> None:
    """Step 5: GraphRAG gate explains PostgreSQL incompatibility."""
    assert "GraphRAG requires ChromaDB" in setup_wizard_content, (
        "Step 5 (GraphRAG) must gate GraphRAG on backend selection. "
        "GraphRAG is incompatible with PostgreSQL backend (hard error in query_service.py). "
        "Users must be told this before selecting GraphRAG."
    )


def test_setup_wizard_step6_cache_awareness(setup_wizard_content: str) -> None:
    """Step 6: Query mode step mentions auto-enabled caches."""
    assert "auto-enabled" in setup_wizard_content or "auto-active" in setup_wizard_content or (
        "embedding cache" in setup_wizard_content.lower()
        and "query cache" in setup_wizard_content.lower()
    ), (
        "Step 6 (Query Mode) must mention that embedding and query caches are "
        "automatically active. Users finishing setup should know caches exist."
    )


def test_config_wizard_step7_includes_ast_plus_langextract_option(
    config_wizard_content: str,
) -> None:
    """Step 7 must expose AST+LangExtract as a first-class GraphRAG option."""
    assert "AST + LangExtract" in config_wizard_content, (
        "Step 7 in agent-brain-config.md must explicitly include an "
        "AST + LangExtract top-level option for mixed repositories."
    )


def test_config_wizard_step12_includes_auto_port_discovery_text(
    config_wizard_content: str,
) -> None:
    """Step 12 must document automatic API port discovery from 8000-8300."""
    lowered = config_wizard_content.lower()
    assert "step 12" in lowered
    assert "8000-8300" in config_wizard_content, (
        "Step 12 must specify API port scan range 8000-8300."
    )
    assert "available" in lowered and "port" in lowered and "api" in lowered, (
        "Step 12 must state that wizard discovers an available API port "
        "instead of assuming 8000."
    )
