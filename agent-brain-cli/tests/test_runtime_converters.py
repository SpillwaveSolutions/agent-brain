"""Tests for runtime converters (Claude, OpenCode, Gemini)."""

import json
from pathlib import Path

import pytest
import yaml

from agent_brain_cli.runtime.claude_converter import ClaudeConverter
from agent_brain_cli.runtime.gemini_converter import GeminiConverter
from agent_brain_cli.runtime.opencode_converter import (
    OpenCodeConverter,
    _color_to_hex,
    _tools_to_bool_object,
)
from agent_brain_cli.runtime.parser import parse_plugin_dir
from agent_brain_cli.runtime.types import (
    PluginAgent,
    PluginBundle,
    PluginCommand,
    PluginManifest,
    PluginParameter,
    PluginSkill,
    RuntimeType,
    Scope,
    TriggerPattern,
)


@pytest.fixture
def sample_command() -> PluginCommand:
    return PluginCommand(
        name="test-search",
        description="Search docs",
        parameters=[
            PluginParameter(name="query", description="Search query", required=True),
            PluginParameter(
                name="top-k",
                description="Results count",
                required=False,
                default="5",
            ),
        ],
        skills=["using-agent-brain"],
        body="Run search against .claude/agent-brain data.",
    )


@pytest.fixture
def sample_agent() -> PluginAgent:
    return PluginAgent(
        name="search-helper",
        description="Helps search",
        triggers=[
            TriggerPattern(pattern="search.*docs", type="message_pattern"),
            TriggerPattern(pattern="find docs", type="keyword"),
        ],
        skills=["using-agent-brain"],
        body="Agent uses .claude/agent-brain for data.",
    )


@pytest.fixture
def sample_skill() -> PluginSkill:
    return PluginSkill(
        name="using-agent-brain",
        description="Search skill",
        allowed_tools=["Bash", "Read"],
        metadata={"version": "1.0.0", "category": "tools"},
        body="Skill references .claude/agent-brain/data.",
        license="MIT",
    )


@pytest.fixture
def sample_bundle(
    sample_command: PluginCommand,
    sample_agent: PluginAgent,
    sample_skill: PluginSkill,
) -> PluginBundle:
    return PluginBundle(
        commands=[sample_command],
        agents=[sample_agent],
        skills=[sample_skill],
        manifest=PluginManifest(name="test", version="1.0.0"),
    )


class TestClaudeConverter:
    """Tests for Claude runtime converter."""

    def test_runtime_type(self) -> None:
        converter = ClaudeConverter()
        assert converter.runtime_type == RuntimeType.CLAUDE

    def test_convert_command_replaces_paths(
        self, sample_command: PluginCommand
    ) -> None:
        converter = ClaudeConverter()
        result = converter.convert_command(sample_command)
        assert ".agent-brain" in result
        assert ".claude/agent-brain" not in result

    def test_convert_agent_replaces_paths(self, sample_agent: PluginAgent) -> None:
        converter = ClaudeConverter()
        result = converter.convert_agent(sample_agent)
        assert ".agent-brain" in result
        assert ".claude/agent-brain" not in result

    def test_convert_skill_replaces_paths(self, sample_skill: PluginSkill) -> None:
        converter = ClaudeConverter()
        result = converter.convert_skill(sample_skill)
        assert ".agent-brain" in result
        assert ".claude/agent-brain" not in result

    def test_install_creates_structure(
        self,
        tmp_path: Path,
        sample_bundle: PluginBundle,
    ) -> None:
        converter = ClaudeConverter()
        target = tmp_path / "output"
        files = converter.install(sample_bundle, target, Scope.PROJECT)
        assert len(files) > 0
        assert (target / "commands" / "test-search.md").exists()
        assert (target / "agents" / "search-helper.md").exists()
        assert (target / "skills" / "using-agent-brain" / "SKILL.md").exists()

    def test_install_copies_plugin_json(self, tmp_path: Path) -> None:
        """Test that plugin.json is copied when source dir exists."""
        source = tmp_path / "source"
        source.mkdir()
        manifest_dir = source / ".claude-plugin"
        manifest_dir.mkdir()
        (manifest_dir / "plugin.json").write_text(
            json.dumps({"name": "test", "version": "1.0.0"})
        )
        cmds = source / "commands"
        cmds.mkdir()
        (cmds / "cmd.md").write_text(
            "---\nname: cmd\ndescription: Test\n"
            "parameters: []\nskills: []\n---\nBody."
        )

        bundle = parse_plugin_dir(source)
        converter = ClaudeConverter()
        target = tmp_path / "output"
        files = converter.install(bundle, target, Scope.PROJECT)

        manifest_out = target / ".claude-plugin" / "plugin.json"
        assert manifest_out.exists()
        assert manifest_out in files


class TestOpenCodeConverter:
    """Tests for OpenCode runtime converter."""

    def test_runtime_type(self) -> None:
        converter = OpenCodeConverter()
        assert converter.runtime_type == RuntimeType.OPENCODE

    def test_tools_to_bool_object(self) -> None:
        result = _tools_to_bool_object(["Bash", "Read"])
        assert result == {"bash": True, "read": True}

    def test_color_to_hex(self) -> None:
        assert _color_to_hex("red") == "#FF0000"
        assert _color_to_hex("green") == "#00FF00"
        assert _color_to_hex("#ABC123") == "#ABC123"
        assert _color_to_hex("unknown_color") == "unknown_color"

    def test_convert_skill_uses_tools_object(self, sample_skill: PluginSkill) -> None:
        converter = OpenCodeConverter()
        result = converter.convert_skill(sample_skill)
        # Parse back to verify structure
        _, fm_text = result.split("---\n", 1)
        fm_text = fm_text.split("---\n", 1)[0]
        parsed = yaml.safe_load(fm_text)
        assert "tools" in parsed
        assert parsed["tools"] == {"bash": True, "read": True}
        assert "allowed-tools" not in parsed

    def test_convert_command_replaces_paths(
        self, sample_command: PluginCommand
    ) -> None:
        converter = OpenCodeConverter()
        result = converter.convert_command(sample_command)
        assert ".agent-brain" in result
        assert ".claude/agent-brain" not in result

    def test_install_creates_files(
        self, tmp_path: Path, sample_bundle: PluginBundle
    ) -> None:
        converter = OpenCodeConverter()
        target = tmp_path / "output"
        files = converter.install(sample_bundle, target, Scope.PROJECT)
        assert len(files) > 0
        assert (target / "commands" / "test-search.md").exists()
        assert (target / "agents" / "search-helper.md").exists()


class TestGeminiConverter:
    """Tests for Gemini runtime converter."""

    def test_runtime_type(self) -> None:
        converter = GeminiConverter()
        assert converter.runtime_type == RuntimeType.GEMINI

    def test_convert_skill_maps_tools(self, sample_skill: PluginSkill) -> None:
        converter = GeminiConverter()
        result = converter.convert_skill(sample_skill)
        _, fm_text = result.split("---\n", 1)
        fm_text = fm_text.split("---\n", 1)[0]
        parsed = yaml.safe_load(fm_text)
        tools = parsed["allowed-tools"]
        assert "run_shell_command" in tools  # Bash -> run_shell_command
        assert "read_file" in tools  # Read -> read_file

    def test_convert_skill_removes_color(self) -> None:
        skill = PluginSkill(
            name="test",
            description="Test",
            allowed_tools=["Bash"],
            metadata={"version": "1.0", "color": "red"},
            body="Content",
        )
        converter = GeminiConverter()
        result = converter.convert_skill(skill)
        _, fm_text = result.split("---\n", 1)
        fm_text = fm_text.split("---\n", 1)[0]
        parsed = yaml.safe_load(fm_text)
        assert "color" not in parsed.get("metadata", {})

    def test_convert_command_replaces_paths(
        self, sample_command: PluginCommand
    ) -> None:
        converter = GeminiConverter()
        result = converter.convert_command(sample_command)
        assert ".agent-brain" in result
        assert ".claude/agent-brain" not in result

    def test_install_creates_files(
        self, tmp_path: Path, sample_bundle: PluginBundle
    ) -> None:
        converter = GeminiConverter()
        target = tmp_path / "output"
        files = converter.install(sample_bundle, target, Scope.PROJECT)
        assert len(files) > 0
        assert (target / "commands" / "test-search.md").exists()
        assert (target / "agents" / "search-helper.md").exists()
        assert (target / "skills" / "using-agent-brain" / "SKILL.md").exists()


class TestRoundTrip:
    """Round-trip tests: parse canonical → convert → verify structure."""

    @pytest.fixture
    def real_plugin_dir(self) -> Path | None:
        path = Path(__file__).parent.parent.parent / "agent-brain-plugin"
        if path.is_dir():
            return path
        return None

    def test_claude_round_trip(self, real_plugin_dir: Path | None) -> None:
        if real_plugin_dir is None:
            pytest.skip("Real plugin dir not found")
        bundle = parse_plugin_dir(real_plugin_dir)
        converter = ClaudeConverter()
        for cmd in bundle.commands:
            result = converter.convert_command(cmd)
            assert ".claude/agent-brain" not in result

    def test_opencode_round_trip(self, real_plugin_dir: Path | None) -> None:
        if real_plugin_dir is None:
            pytest.skip("Real plugin dir not found")
        bundle = parse_plugin_dir(real_plugin_dir)
        converter = OpenCodeConverter()
        for skill in bundle.skills:
            result = converter.convert_skill(skill)
            assert "tools:" in result

    def test_gemini_round_trip(self, real_plugin_dir: Path | None) -> None:
        if real_plugin_dir is None:
            pytest.skip("Real plugin dir not found")
        bundle = parse_plugin_dir(real_plugin_dir)
        converter = GeminiConverter()
        for skill in bundle.skills:
            result = converter.convert_skill(skill)
            # Bash should become run_shell_command
            assert "run_shell_command" in result
