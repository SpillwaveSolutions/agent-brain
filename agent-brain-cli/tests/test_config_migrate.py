"""Tests for config migration engine and CLI migrate/diff commands."""

from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from agent_brain_cli.cli import cli


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


OLD_SCHEMA_CONFIG: dict = {
    "embedding": {"provider": "openai", "model": "text-embedding-3-large"},
    "summarization": {"provider": "anthropic", "model": "claude-haiku-4-5-20251001"},
    "graphrag": {
        "enabled": True,
        "store_type": "simple",
        "use_code_metadata": True,
        "use_llm_extraction": True,
    },
    "api": {"host": "127.0.0.1", "port": 8000},
}

OLD_SCHEMA_FALSE_CONFIG: dict = {
    "graphrag": {
        "enabled": True,
        "store_type": "simple",
        "use_code_metadata": True,
        "use_llm_extraction": False,
    },
}

CURRENT_SCHEMA_CONFIG: dict = {
    "embedding": {"provider": "openai", "model": "text-embedding-3-large"},
    "summarization": {"provider": "anthropic", "model": "claude-haiku-4-5-20251001"},
    "graphrag": {
        "enabled": True,
        "store_type": "simple",
        "use_code_metadata": True,
        "doc_extractor": "langextract",
    },
    "api": {"host": "127.0.0.1", "port": 8000},
}

EMPTY_CONFIG: dict = {}


# ---------------------------------------------------------------------------
# Unit tests: migrate_config (dict-level)
# ---------------------------------------------------------------------------


class TestMigrateConfigDict:
    """Tests for migrate_config() with dict inputs."""

    def test_migrate_use_llm_extraction_true(self) -> None:
        """migrate_config transforms use_llm_extraction=True -> doc_extractor=langextract."""
        from agent_brain_cli.config_migrate import migrate_config

        result = migrate_config(OLD_SCHEMA_CONFIG)

        assert result.already_current is False
        graphrag = result.migrated.get("graphrag", {})
        assert graphrag.get("doc_extractor") == "langextract"
        assert "use_llm_extraction" not in graphrag
        assert len(result.changes) >= 1

    def test_migrate_use_llm_extraction_false(self) -> None:
        """migrate_config removes use_llm_extraction=False (no doc_extractor added)."""
        from agent_brain_cli.config_migrate import migrate_config

        result = migrate_config(OLD_SCHEMA_FALSE_CONFIG)

        assert result.already_current is False
        graphrag = result.migrated.get("graphrag", {})
        assert "use_llm_extraction" not in graphrag
        assert "doc_extractor" not in graphrag
        assert len(result.changes) >= 1

    def test_migrate_already_current_config(self) -> None:
        """migrate_config on a current-schema dict returns already_current=True."""
        from agent_brain_cli.config_migrate import migrate_config

        result = migrate_config(CURRENT_SCHEMA_CONFIG)

        assert result.already_current is True
        assert result.changes == []

    def test_migrate_empty_config(self) -> None:
        """migrate_config on empty dict returns already_current=True with no changes."""
        from agent_brain_cli.config_migrate import migrate_config

        result = migrate_config(EMPTY_CONFIG)

        assert result.already_current is True
        assert result.changes == []

    def test_migrate_preserves_other_keys(self) -> None:
        """migrate_config leaves embedding, summarization, api sections untouched."""
        from agent_brain_cli.config_migrate import migrate_config

        result = migrate_config(OLD_SCHEMA_CONFIG)

        # These sections must be preserved exactly
        assert result.migrated["embedding"] == OLD_SCHEMA_CONFIG["embedding"]
        assert result.migrated["summarization"] == OLD_SCHEMA_CONFIG["summarization"]
        assert result.migrated["api"] == OLD_SCHEMA_CONFIG["api"]

    def test_migrate_does_not_mutate_input(self) -> None:
        """migrate_config must not mutate the original input dict."""
        from agent_brain_cli.config_migrate import migrate_config
        import copy

        original = copy.deepcopy(OLD_SCHEMA_CONFIG)
        migrate_config(OLD_SCHEMA_CONFIG)

        # Input should not have been modified
        assert OLD_SCHEMA_CONFIG == original


# ---------------------------------------------------------------------------
# Unit tests: diff_config (dict-level)
# ---------------------------------------------------------------------------


class TestDiffConfigDict:
    """Tests for diff_config() with dict inputs."""

    def test_diff_shows_use_llm_extraction(self) -> None:
        """diff_config shows removed use_llm_extraction and added doc_extractor."""
        from agent_brain_cli.config_migrate import diff_config

        result = diff_config(OLD_SCHEMA_CONFIG)

        assert isinstance(result, str)
        assert len(result) > 0
        # The diff should show the removed key in some form
        assert "use_llm_extraction" in result

    def test_diff_no_changes_returns_empty(self) -> None:
        """diff_config returns empty string for already-current config."""
        from agent_brain_cli.config_migrate import diff_config

        result = diff_config(CURRENT_SCHEMA_CONFIG)

        assert result == ""


# ---------------------------------------------------------------------------
# File-based tests
# ---------------------------------------------------------------------------


class TestMigrateConfigFile:
    """Tests for migrate_config_file() and diff_config_file()."""

    def test_migrate_config_file_writes_migrated_yaml(
        self, tmp_path: Path
    ) -> None:
        """migrate_config_file writes migrated YAML to disk."""
        from agent_brain_cli.config_migrate import migrate_config_file

        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.safe_dump(OLD_SCHEMA_CONFIG, default_flow_style=False),
            encoding="utf-8",
        )

        result = migrate_config_file(config_file)

        assert result.already_current is False
        # Re-read the file to verify it was actually written
        updated = yaml.safe_load(config_file.read_text(encoding="utf-8"))
        graphrag = updated.get("graphrag", {})
        assert graphrag.get("doc_extractor") == "langextract"
        assert "use_llm_extraction" not in graphrag

    def test_diff_config_file_shows_diff(self, tmp_path: Path) -> None:
        """diff_config_file returns non-empty diff for old-schema config."""
        from agent_brain_cli.config_migrate import diff_config_file

        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.safe_dump(OLD_SCHEMA_CONFIG, default_flow_style=False),
            encoding="utf-8",
        )

        result = diff_config_file(config_file)

        assert isinstance(result, str)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# CLI command tests
# ---------------------------------------------------------------------------


class TestMigrateCliCommand:
    """Tests for 'agent-brain config migrate' CLI command."""

    def test_migrate_updates_file(self, tmp_path: Path) -> None:
        """migrate command upgrades old-schema YAML in-place."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.safe_dump(OLD_SCHEMA_CONFIG, default_flow_style=False),
            encoding="utf-8",
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "migrate", "--file", str(config_file)])

        assert result.exit_code == 0
        updated_text = config_file.read_text(encoding="utf-8")
        assert "doc_extractor" in updated_text
        assert "use_llm_extraction" not in updated_text

    def test_migrate_already_current(self, tmp_path: Path) -> None:
        """migrate command reports 'already up to date' for current-schema config."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.safe_dump(CURRENT_SCHEMA_CONFIG, default_flow_style=False),
            encoding="utf-8",
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "migrate", "--file", str(config_file)])

        assert result.exit_code == 0
        assert "already up to date" in result.output.lower()

    def test_migrate_dry_run_does_not_modify_file(self, tmp_path: Path) -> None:
        """migrate --dry-run shows changes without modifying the file."""
        config_file = tmp_path / "config.yaml"
        original_content = yaml.safe_dump(
            OLD_SCHEMA_CONFIG, default_flow_style=False
        )
        config_file.write_text(original_content, encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(
            cli, ["config", "migrate", "--file", str(config_file), "--dry-run"]
        )

        assert result.exit_code == 0
        # File must remain unchanged
        assert config_file.read_text(encoding="utf-8") == original_content

    def test_migrate_no_config_found(self) -> None:
        """migrate exits 0 with informative message when no config file is found."""
        from unittest.mock import patch

        runner = CliRunner()
        with patch(
            "agent_brain_cli.commands.config._find_config_file", return_value=None
        ):
            result = runner.invoke(cli, ["config", "migrate"])

        assert result.exit_code == 0
        assert "No config file found" in result.output


class TestDiffCliCommand:
    """Tests for 'agent-brain config diff' CLI command."""

    def test_diff_shows_changes(self, tmp_path: Path) -> None:
        """diff command shows changes for old-schema config."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.safe_dump(OLD_SCHEMA_CONFIG, default_flow_style=False),
            encoding="utf-8",
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "diff", "--file", str(config_file)])

        assert result.exit_code == 0
        # The diff output should reference the deprecated key
        assert "use_llm_extraction" in result.output

    def test_diff_no_changes(self, tmp_path: Path) -> None:
        """diff command reports no changes for current-schema config."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.safe_dump(CURRENT_SCHEMA_CONFIG, default_flow_style=False),
            encoding="utf-8",
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "diff", "--file", str(config_file)])

        assert result.exit_code == 0
        assert "up to date" in result.output.lower()

    def test_diff_no_config_found(self) -> None:
        """diff exits 0 with informative message when no config file is found."""
        from unittest.mock import patch

        runner = CliRunner()
        with patch(
            "agent_brain_cli.commands.config._find_config_file", return_value=None
        ):
            result = runner.invoke(cli, ["config", "diff"])

        assert result.exit_code == 0
        assert "No config file found" in result.output


class TestWizardValidationIntegration:
    """Tests for validation integration in the config wizard."""

    def test_wizard_validates_output_and_warns(self, tmp_path: Path) -> None:
        """Wizard warns when validate_config_file returns errors after writing."""
        from unittest.mock import patch
        from agent_brain_cli.config_schema import ConfigValidationError

        # Patch validate_config_file to return a fake error
        fake_error = ConfigValidationError(
            field="embedding.provider",
            message="Invalid embedding provider: 'badprovider'",
            line_number=3,
            suggestion="Use one of: cohere, gemini, ollama, openai",
        )

        runner = CliRunner()
        # Supply all wizard prompts
        wizard_inputs = "\n".join(
            [
                "openai",  # embedding provider
                "text-embedding-3-large",  # embedding model
                "anthropic",  # summarization provider
                "claude-haiku-4-5-20251001",  # summarization model
                "1",  # graphrag mode: disabled
                "1",  # deployment mode: localhost
                "8000",  # api port
                "n",  # do NOT continue with invalid config
            ]
        )

        with (
            patch(
                "agent_brain_cli.commands.config._resolve_wizard_config_path",
                return_value=tmp_path / ".agent-brain" / "config.yaml",
            ),
            patch(
                "agent_brain_cli.commands.config.validate_config_file",
                return_value=[fake_error],
            ),
        ):
            result = runner.invoke(cli, ["config", "wizard"], input=wizard_inputs)

        # Warning should appear in output
        assert "Warning" in result.output or "warning" in result.output.lower()
