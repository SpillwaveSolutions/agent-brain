"""Tests for types CLI commands."""

import json

import pytest
from click.testing import CliRunner

from agent_brain_cli.cli import cli
from agent_brain_cli.commands.types import FILE_TYPE_PRESETS


@pytest.fixture
def runner() -> CliRunner:
    """Create CLI test runner."""
    return CliRunner()


class TestTypesListCommand:
    """Tests for 'agent-brain types list' command."""

    def test_types_list_shows_table(self, runner: CliRunner) -> None:
        """Test that types list renders a table with presets."""
        result = runner.invoke(cli, ["types", "list"])

        assert result.exit_code == 0
        # Verify some known presets appear
        assert "python" in result.output
        assert "docs" in result.output
        assert "typescript" in result.output

    def test_types_list_shows_extensions(self, runner: CliRunner) -> None:
        """Test that types list shows file extensions for each preset."""
        result = runner.invoke(cli, ["types", "list"])

        assert result.exit_code == 0
        # Python preset should show *.py
        assert "*.py" in result.output
        # Docs preset should show *.md
        assert "*.md" in result.output

    def test_types_list_json_output(self, runner: CliRunner) -> None:
        """Test that types list --json outputs valid JSON."""
        result = runner.invoke(cli, ["types", "list", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, dict)
        assert "python" in data
        assert isinstance(data["python"], list)
        assert "*.py" in data["python"]

    def test_types_list_json_all_presets(self, runner: CliRunner) -> None:
        """Test that JSON output contains all defined presets."""
        result = runner.invoke(cli, ["types", "list", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)

        for preset_name in FILE_TYPE_PRESETS:
            assert (
                preset_name in data
            ), f"Preset '{preset_name}' missing from JSON output"
            assert data[preset_name] == FILE_TYPE_PRESETS[preset_name]

    def test_types_list_no_server_needed(self, runner: CliRunner) -> None:
        """Test that types list works without a server connection."""
        # This test verifies the command is purely local — no mocking needed
        result = runner.invoke(cli, ["types", "list"])
        assert result.exit_code == 0

    def test_types_list_shows_code_preset(self, runner: CliRunner) -> None:
        """Test that the 'code' meta-preset appears in the output."""
        result = runner.invoke(cli, ["types", "list"])

        assert result.exit_code == 0
        assert "code" in result.output

    def test_types_list_shows_usage_hint(self, runner: CliRunner) -> None:
        """Test that types list shows a usage hint."""
        result = runner.invoke(cli, ["types", "list"])

        assert result.exit_code == 0
        # Should show a hint about --include-type usage
        assert "--include-type" in result.output


class TestTypesHelp:
    """Tests for types --help output."""

    def test_types_help(self, runner: CliRunner) -> None:
        """Test 'agent-brain types --help' output."""
        result = runner.invoke(cli, ["types", "--help"])

        assert result.exit_code == 0
        assert "list" in result.output

    def test_types_list_help(self, runner: CliRunner) -> None:
        """Test 'agent-brain types list --help' output."""
        result = runner.invoke(cli, ["types", "list", "--help"])

        assert result.exit_code == 0
        assert "--json" in result.output
        assert "--include-type" in result.output


class TestFileTypePresets:
    """Tests for FILE_TYPE_PRESETS data integrity."""

    def test_all_expected_presets_exist(self) -> None:
        """Test that all expected presets are defined."""
        expected = {
            "python",
            "javascript",
            "typescript",
            "go",
            "rust",
            "java",
            "csharp",
            "c",
            "cpp",
            "web",
            "docs",
            "text",
            "pdf",
            "code",
        }
        assert expected.issubset(set(FILE_TYPE_PRESETS.keys()))

    def test_python_preset_patterns(self) -> None:
        """Test Python preset includes expected patterns."""
        assert "*.py" in FILE_TYPE_PRESETS["python"]
        assert "*.pyi" in FILE_TYPE_PRESETS["python"]

    def test_docs_preset_patterns(self) -> None:
        """Test docs preset includes expected patterns."""
        assert "*.md" in FILE_TYPE_PRESETS["docs"]
        assert "*.pdf" in FILE_TYPE_PRESETS["docs"]

    def test_code_preset_is_superset(self) -> None:
        """Test that 'code' preset contains all language patterns."""
        code_patterns = set(FILE_TYPE_PRESETS["code"])
        # code should include Python patterns
        for pat in FILE_TYPE_PRESETS["python"]:
            assert pat in code_patterns, f"code preset missing: {pat}"
        # code should include TypeScript patterns
        for pat in FILE_TYPE_PRESETS["typescript"]:
            assert pat in code_patterns, f"code preset missing: {pat}"

    def test_presets_have_non_empty_patterns(self) -> None:
        """Test that all presets have at least one pattern."""
        for name, patterns in FILE_TYPE_PRESETS.items():
            assert len(patterns) > 0, f"Preset '{name}' has no patterns"
            for pat in patterns:
                assert pat.startswith(
                    "*."
                ), f"Pattern '{pat}' in preset '{name}' should start with '*.' "
