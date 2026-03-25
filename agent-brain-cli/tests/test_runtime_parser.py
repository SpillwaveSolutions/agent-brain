"""Tests for the plugin parser and runtime converter infrastructure."""

import json
from pathlib import Path

import pytest

from agent_brain_cli.runtime.parser import (
    parse_agent,
    parse_command,
    parse_frontmatter,
    parse_manifest,
    parse_plugin_dir,
    parse_skill,
)
from agent_brain_cli.runtime.tool_maps import (
    CLAUDE_TOOLS,
    GEMINI_TOOLS,
    OPENCODE_TOOLS,
    map_tool_name,
    map_tools,
)
from agent_brain_cli.runtime.types import (
    RuntimeType,
    Scope,
)


class TestParseFrontmatter:
    """Tests for YAML frontmatter parsing."""

    def test_basic_frontmatter(self) -> None:
        text = "---\nname: test\ndescription: A test\n---\nBody content"
        fm, body = parse_frontmatter(text)
        assert fm["name"] == "test"
        assert fm["description"] == "A test"
        assert body == "Body content"

    def test_multiline_body(self) -> None:
        text = "---\nname: cmd\n---\nLine 1\n\nLine 2"
        fm, body = parse_frontmatter(text)
        assert fm["name"] == "cmd"
        assert "Line 1" in body
        assert "Line 2" in body

    def test_missing_opening_delimiter(self) -> None:
        with pytest.raises(ValueError, match="does not start with"):
            parse_frontmatter("name: test\n---\nbody")

    def test_missing_closing_delimiter(self) -> None:
        with pytest.raises(ValueError, match="Missing closing"):
            parse_frontmatter("---\nname: test\nbody without closing")

    def test_invalid_yaml(self) -> None:
        with pytest.raises(ValueError, match="Invalid YAML"):
            parse_frontmatter("---\n: :\n  bad: [yaml\n---\nbody")

    def test_non_mapping_frontmatter(self) -> None:
        with pytest.raises(ValueError, match="must be a YAML mapping"):
            parse_frontmatter("---\n- item1\n- item2\n---\nbody")

    def test_empty_body(self) -> None:
        fm, body = parse_frontmatter("---\nname: x\n---\n")
        assert fm["name"] == "x"
        assert body == ""

    def test_whitespace_handling(self) -> None:
        text = "\n---\nname: x\n---\n\n  Body  \n\n"
        fm, body = parse_frontmatter(text)
        assert fm["name"] == "x"
        assert body == "Body"


class TestParseCommand:
    """Tests for command file parsing."""

    def test_basic_command(self, tmp_path: Path) -> None:
        cmd_file = tmp_path / "test-cmd.md"
        cmd_file.write_text(
            "---\n"
            "name: test-cmd\n"
            "description: A test command\n"
            "parameters: []\n"
            "skills:\n"
            "  - my-skill\n"
            "---\n"
            "Do something."
        )
        cmd = parse_command(cmd_file)
        assert cmd.name == "test-cmd"
        assert cmd.description == "A test command"
        assert cmd.skills == ["my-skill"]
        assert cmd.parameters == []
        assert "Do something" in cmd.body

    def test_command_with_parameters(self, tmp_path: Path) -> None:
        cmd_file = tmp_path / "search.md"
        cmd_file.write_text(
            "---\n"
            "name: search\n"
            "description: Search docs\n"
            "parameters:\n"
            "  - name: query\n"
            "    description: Search query\n"
            "    required: true\n"
            "  - name: top-k\n"
            "    description: Number of results\n"
            "    required: false\n"
            "    default: 5\n"
            "skills: []\n"
            "---\n"
            "Search body."
        )
        cmd = parse_command(cmd_file)
        assert len(cmd.parameters) == 2
        assert cmd.parameters[0].name == "query"
        assert cmd.parameters[0].required is True
        assert cmd.parameters[0].default is None
        assert cmd.parameters[1].name == "top-k"
        assert cmd.parameters[1].required is False
        assert cmd.parameters[1].default == "5"

    def test_command_name_fallback_to_stem(self, tmp_path: Path) -> None:
        cmd_file = tmp_path / "my-fallback.md"
        cmd_file.write_text("---\ndescription: No name field\n---\nBody.")
        cmd = parse_command(cmd_file)
        assert cmd.name == "my-fallback"


class TestParseAgent:
    """Tests for agent file parsing."""

    def test_basic_agent(self, tmp_path: Path) -> None:
        agent_file = tmp_path / "search-assistant.md"
        agent_file.write_text(
            "---\n"
            "name: search-assistant\n"
            "description: Helps search docs\n"
            "triggers:\n"
            "  - pattern: search.*docs\n"
            "    type: message_pattern\n"
            "  - pattern: find docs\n"
            "    type: keyword\n"
            "skills:\n"
            "  - using-agent-brain\n"
            "---\n"
            "Agent instructions."
        )
        agent = parse_agent(agent_file)
        assert agent.name == "search-assistant"
        assert len(agent.triggers) == 2
        assert agent.triggers[0].pattern == "search.*docs"
        assert agent.triggers[0].type == "message_pattern"
        assert agent.triggers[1].type == "keyword"
        assert agent.skills == ["using-agent-brain"]


class TestParseSkill:
    """Tests for skill file parsing."""

    def test_basic_skill(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(
            "---\n"
            "name: my-skill\n"
            "description: A skill\n"
            "license: MIT\n"
            "allowed-tools:\n"
            "  - Bash\n"
            "  - Read\n"
            "metadata:\n"
            "  version: 1.0.0\n"
            "  category: tools\n"
            "---\n"
            "Skill content."
        )
        skill = parse_skill(skill_file)
        assert skill.name == "my-skill"
        assert skill.allowed_tools == ["Bash", "Read"]
        assert skill.metadata["version"] == "1.0.0"
        assert skill.license == "MIT"
        assert skill.references == []

    def test_skill_with_references(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "docs-skill"
        skill_dir.mkdir()
        refs_dir = skill_dir / "references"
        refs_dir.mkdir()
        (refs_dir / "guide.md").write_text("# Guide")
        (refs_dir / "api.md").write_text("# API")
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("---\nname: docs-skill\ndescription: Docs\n---\nBody.")
        skill = parse_skill(skill_file)
        assert len(skill.references) == 2
        assert "references/api.md" in skill.references
        assert "references/guide.md" in skill.references


class TestParseManifest:
    """Tests for plugin.json manifest parsing."""

    def test_basic_manifest(self, tmp_path: Path) -> None:
        manifest_file = tmp_path / "plugin.json"
        manifest_file.write_text(
            json.dumps(
                {
                    "name": "agent-brain",
                    "description": "Search plugin",
                    "version": "8.0.0",
                    "author": {
                        "name": "Test",
                        "email": "test@test.com",
                    },
                    "license": "MIT",
                }
            )
        )
        manifest = parse_manifest(manifest_file)
        assert manifest.name == "agent-brain"
        assert manifest.version == "8.0.0"
        assert manifest.author_name == "Test"
        assert manifest.license == "MIT"


class TestParsePluginDir:
    """Tests for full plugin directory parsing."""

    @pytest.fixture
    def plugin_dir(self, tmp_path: Path) -> Path:
        """Create a minimal plugin directory structure."""
        root = tmp_path / "plugin"
        root.mkdir()

        # Manifest
        manifest_dir = root / ".claude-plugin"
        manifest_dir.mkdir()
        (manifest_dir / "plugin.json").write_text(
            json.dumps(
                {
                    "name": "test-plugin",
                    "version": "1.0.0",
                    "description": "Test",
                }
            )
        )

        # Commands
        cmds_dir = root / "commands"
        cmds_dir.mkdir()
        (cmds_dir / "cmd-a.md").write_text(
            "---\nname: cmd-a\ndescription: Command A\n"
            "parameters: []\nskills: []\n---\nBody A."
        )
        (cmds_dir / "cmd-b.md").write_text(
            "---\nname: cmd-b\ndescription: Command B\n"
            "parameters: []\nskills: []\n---\nBody B."
        )

        # Agents
        agents_dir = root / "agents"
        agents_dir.mkdir()
        (agents_dir / "helper.md").write_text(
            "---\nname: helper\ndescription: Helper agent\n"
            "triggers: []\nskills: []\n---\nAgent body."
        )

        # Skills
        skills_dir = root / "skills"
        skill_a = skills_dir / "skill-a"
        skill_a.mkdir(parents=True)
        (skill_a / "SKILL.md").write_text(
            "---\nname: skill-a\ndescription: Skill A\n"
            "allowed-tools:\n  - Bash\n---\nSkill body."
        )

        return root

    def test_parses_full_directory(self, plugin_dir: Path) -> None:
        bundle = parse_plugin_dir(plugin_dir)
        assert len(bundle.commands) == 2
        assert len(bundle.agents) == 1
        assert len(bundle.skills) == 1
        assert bundle.manifest.name == "test-plugin"
        assert bundle.manifest.version == "1.0.0"

    def test_command_names(self, plugin_dir: Path) -> None:
        bundle = parse_plugin_dir(plugin_dir)
        names = [c.name for c in bundle.commands]
        assert "cmd-a" in names
        assert "cmd-b" in names

    def test_nonexistent_dir_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            parse_plugin_dir(Path("/nonexistent/plugin"))

    def test_empty_dir(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty-plugin"
        empty.mkdir()
        bundle = parse_plugin_dir(empty)
        assert len(bundle.commands) == 0
        assert len(bundle.agents) == 0
        assert len(bundle.skills) == 0


class TestParseRealPluginDir:
    """Integration test against the actual plugin directory."""

    @pytest.fixture
    def real_plugin_dir(self) -> Path | None:
        """Return path to real plugin dir if available."""
        path = Path(__file__).parent.parent.parent / "agent-brain-plugin"
        if path.is_dir():
            return path
        return None

    def test_parse_real_plugin(self, real_plugin_dir: Path | None) -> None:
        if real_plugin_dir is None:
            pytest.skip("Real plugin dir not found")
        bundle = parse_plugin_dir(real_plugin_dir)
        assert len(bundle.commands) >= 29
        assert len(bundle.agents) == 3
        assert len(bundle.skills) == 2
        assert bundle.manifest.name == "agent-brain"


class TestToolMaps:
    """Tests for tool name mapping."""

    def test_claude_identity_mapping(self) -> None:
        assert map_tool_name("Bash", "claude") == "Bash"
        assert map_tool_name("Read", "claude") == "Read"

    def test_opencode_lowercase(self) -> None:
        assert map_tool_name("Bash", "opencode") == "bash"
        assert map_tool_name("Read", "opencode") == "read"
        assert map_tool_name("WebFetch", "opencode") == "web_fetch"

    def test_gemini_mapping(self) -> None:
        assert map_tool_name("Bash", "gemini") == "run_shell_command"
        assert map_tool_name("Read", "gemini") == "read_file"
        assert map_tool_name("Write", "gemini") == "write_file"
        assert map_tool_name("Edit", "gemini") == "replace"

    def test_unknown_tool_passthrough(self) -> None:
        # Unknown tools are lowercased (fallback behavior)
        assert map_tool_name("CustomTool", "claude") == "customtool"
        assert map_tool_name("CustomTool", "gemini") == "customtool"
        # MCP tools pass through unchanged
        assert map_tool_name("mcp__server__tool", "opencode") == "mcp__server__tool"

    def test_unknown_runtime_uses_claude(self) -> None:
        assert map_tool_name("Bash", "unknown") == "Bash"

    def test_map_tools_list(self) -> None:
        result = map_tools(["Bash", "Read"], "gemini")
        assert result == ["run_shell_command", "read_file"]

    def test_all_maps_have_same_keys(self) -> None:
        # OPENCODE_TOOLS has extra Claude-specific tools
        # (AskUserQuestion, SkillTool, TodoWrite) not in other runtimes
        assert set(CLAUDE_TOOLS.keys()).issubset(set(OPENCODE_TOOLS.keys()))
        assert set(CLAUDE_TOOLS.keys()) == set(GEMINI_TOOLS.keys())


class TestRuntimeTypes:
    """Tests for runtime type enums."""

    def test_runtime_types(self) -> None:
        assert RuntimeType.CLAUDE.value == "claude"
        assert RuntimeType.OPENCODE.value == "opencode"
        assert RuntimeType.GEMINI.value == "gemini"

    def test_scope_types(self) -> None:
        assert Scope.PROJECT.value == "project"
        assert Scope.GLOBAL.value == "global"
