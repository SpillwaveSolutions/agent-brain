"""Integration tests for agent-brain config wizard command."""

from pathlib import Path

import yaml
from click.testing import CliRunner

from agent_brain_cli.commands.config import config_group


class TestConfigWizard:
    """Tests for config wizard sub-command."""

    def test_wizard_shows_ollama_prompts(self, tmp_path: Path) -> None:
        """Wizard shows batch_size and request_delay_ms when provider is ollama."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(
                config_group,
                ["wizard"],
                input=(
                    "ollama\n"
                    "nomic-embed-text\n"
                    "20\n"
                    "100\n"
                    "anthropic\n"
                    "claude-haiku-4-5-20251001\n"
                ),
            )
            assert result.exit_code == 0, result.output
            assert "Batch size" in result.output
            assert "Request delay" in result.output

            config_file = Path(".agent-brain") / "config.yaml"
            assert config_file.exists()
            config = yaml.safe_load(config_file.read_text(encoding="utf-8"))
            assert config["embedding"]["params"]["batch_size"] == 20
            assert config["embedding"]["params"]["request_delay_ms"] == 100

    def test_wizard_skips_prompts_for_openai_and_cohere(self, tmp_path: Path) -> None:
        """Wizard does not show batch_size/request_delay_ms for openai or cohere."""
        runner = CliRunner()
        for provider in ["openai", "cohere"]:
            with runner.isolated_filesystem(temp_dir=tmp_path):
                result = runner.invoke(
                    config_group,
                    ["wizard"],
                    input=(
                        f"{provider}\n"
                        "some-model\n"
                        "anthropic\n"
                        "claude-haiku-4-5-20251001\n"
                    ),
                )
                assert result.exit_code == 0, f"{provider}: {result.output}"
                assert "Batch size" not in result.output
                assert "Request delay" not in result.output

    def test_wizard_rejects_invalid_batch_size(self, tmp_path: Path) -> None:
        """Wizard rejects batch_size values not in [1, 5, 10, 20, 50, 100]."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(
                config_group,
                ["wizard"],
                input=(
                    "ollama\n"
                    "nomic-embed-text\n"
                    "7\n"
                    "10\n"
                    "0\n"
                    "anthropic\n"
                    "claude-haiku-4-5-20251001\n"
                ),
            )
            assert result.exit_code == 0, result.output
            assert "is not one of" in result.output.lower()

    def test_wizard_rejects_negative_request_delay(self, tmp_path: Path) -> None:
        """Wizard rejects negative request_delay_ms values."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(
                config_group,
                ["wizard"],
                input=(
                    "ollama\n"
                    "nomic-embed-text\n"
                    "10\n"
                    "-1\n"
                    "0\n"
                    "anthropic\n"
                    "claude-haiku-4-5-20251001\n"
                ),
            )
            assert result.exit_code == 0, result.output
            assert "x>=0" in result.output

            config_file = Path(".agent-brain") / "config.yaml"
            assert config_file.exists()
            config = yaml.safe_load(config_file.read_text(encoding="utf-8"))
            assert config["embedding"]["params"]["request_delay_ms"] >= 0
