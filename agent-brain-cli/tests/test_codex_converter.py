"""Tests for the Codex runtime converter."""

import json
from pathlib import Path

import pytest
import yaml

from agent_brain_cli.runtime.codex_converter import (
    AGENTS_MD_END,
    AGENTS_MD_START,
    CodexConverter,
    _add_codex_header,
    _update_agents_md,
)
from agent_brain_cli.runtime.parser import parse_plugin_dir
from agent_brain_cli.runtime.types import (
    PluginAgent,
    PluginBundle,
    PluginCommand,
    PluginManifest,
    PluginParameter,
    PluginScript,
    PluginSkill,
    PluginTemplate,
    RuntimeType,
    Scope,
    TriggerPattern,
)


@pytest.fixture
def sample_command() -> PluginCommand:
    return PluginCommand(
        name="agent-brain-search",
        description="Search documents",
        parameters=[
            PluginParameter(
                name="query", description="Search query", required=True
            ),
        ],
        skills=["using-agent-brain"],
        body="Run search against .claude/agent-brain data.",
    )


@pytest.fixture
def sample_agent() -> PluginAgent:
    return PluginAgent(
        name="search-assistant",
        description="Helps search documents",
        triggers=[],
        skills=["using-agent-brain"],
        body="Agent body.",
    )


@pytest.fixture
def sample_skill() -> PluginSkill:
    return PluginSkill(
        name="using-agent-brain",
        description="Search skill",
        allowed_tools=["Bash", "Read"],
        body="Skill body.",
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
        manifest=PluginManifest(name="agent-brain", version="9.1.0"),
    )


class TestCodexConverter:
    """Tests for CodexConverter."""

    def test_runtime_type(self) -> None:
        converter = CodexConverter()
        assert converter.runtime_type == RuntimeType.CODEX

    def test_convert_command_has_codex_header(
        self, sample_command: PluginCommand
    ) -> None:
        converter = CodexConverter()
        result = converter.convert_command(sample_command)
        assert "Codex Skill:" in result
        assert "agent-brain-search" in result

    def test_convert_agent_has_codex_header(
        self, sample_agent: PluginAgent
    ) -> None:
        converter = CodexConverter()
        result = converter.convert_agent(sample_agent)
        assert "Codex Skill:" in result
        assert "search-assistant" in result

    def test_convert_skill_preserves_format(
        self, sample_skill: PluginSkill
    ) -> None:
        converter = CodexConverter()
        result = converter.convert_skill(sample_skill)
        parts = result.split("---\n")
        fm = yaml.safe_load(parts[1])
        assert fm["name"] == "using-agent-brain"
        assert fm["allowed-tools"] == ["Bash", "Read"]

    def test_install_creates_codex_structure(
        self, tmp_path: Path, sample_bundle: PluginBundle
    ) -> None:
        """Test Codex install creates skills + AGENTS.md."""
        # Simulate project layout: tmp_path is project root
        target = tmp_path / ".codex" / "skills" / "agent-brain"
        converter = CodexConverter()
        files = converter.install(sample_bundle, target, Scope.PROJECT)

        # Skills should exist
        assert (target / "agent-brain-search" / "SKILL.md").exists()
        assert (target / "agent-brain-search-assistant" / "SKILL.md").exists()
        assert (
            target / "agent-brain-using-agent-brain" / "SKILL.md"
        ).exists()

        # AGENTS.md should be created at project root
        agents_md = tmp_path / "AGENTS.md"
        assert agents_md.exists()
        assert agents_md in files

    def test_install_agents_md_content(
        self, tmp_path: Path, sample_bundle: PluginBundle
    ) -> None:
        """Test AGENTS.md contains correct content."""
        target = tmp_path / ".codex" / "skills" / "agent-brain"
        converter = CodexConverter()
        converter.install(sample_bundle, target, Scope.PROJECT)

        agents_md = tmp_path / "AGENTS.md"
        content = agents_md.read_text()
        assert AGENTS_MD_START in content
        assert AGENTS_MD_END in content
        assert "Agent Brain" in content
        assert "agent-brain-search" in content
        assert "search-assistant" in content
        assert "using-agent-brain" in content

    def test_install_codex_headers_in_skills(
        self, tmp_path: Path, sample_bundle: PluginBundle
    ) -> None:
        """Test that command/agent SKILL.md files have Codex headers."""
        target = tmp_path / ".codex" / "skills" / "agent-brain"
        converter = CodexConverter()
        converter.install(sample_bundle, target, Scope.PROJECT)

        cmd_skill = (target / "agent-brain-search" / "SKILL.md").read_text()
        assert "Codex Skill:" in cmd_skill

        agent_skill = (
            target / "agent-brain-search-assistant" / "SKILL.md"
        ).read_text()
        assert "Codex Skill:" in agent_skill


class TestAgentsMdIdempotency:
    """Tests for AGENTS.md idempotent updates."""

    def test_creates_new_agents_md(self, tmp_path: Path) -> None:
        agents_md_path = tmp_path / "AGENTS.md"
        bundle = PluginBundle(
            commands=[
                PluginCommand(
                    name="search", description="Search", body="Body"
                )
            ]
        )
        _update_agents_md(agents_md_path, bundle)
        assert agents_md_path.exists()
        content = agents_md_path.read_text()
        assert AGENTS_MD_START in content
        assert AGENTS_MD_END in content
        assert "search" in content

    def test_idempotent_update(self, tmp_path: Path) -> None:
        """Running twice should not duplicate the section."""
        agents_md_path = tmp_path / "AGENTS.md"
        bundle = PluginBundle(
            commands=[
                PluginCommand(
                    name="search", description="Search", body="Body"
                )
            ]
        )
        _update_agents_md(agents_md_path, bundle)
        first_content = agents_md_path.read_text()

        # Run again
        _update_agents_md(agents_md_path, bundle)
        second_content = agents_md_path.read_text()

        assert first_content == second_content
        assert second_content.count(AGENTS_MD_START) == 1
        assert second_content.count(AGENTS_MD_END) == 1

    def test_updates_existing_section(self, tmp_path: Path) -> None:
        """Updating with different content should replace, not append."""
        agents_md_path = tmp_path / "AGENTS.md"
        bundle1 = PluginBundle(
            commands=[
                PluginCommand(name="old-cmd", description="Old", body="Body")
            ]
        )
        _update_agents_md(agents_md_path, bundle1)
        assert "old-cmd" in agents_md_path.read_text()

        bundle2 = PluginBundle(
            commands=[
                PluginCommand(name="new-cmd", description="New", body="Body")
            ]
        )
        _update_agents_md(agents_md_path, bundle2)
        content = agents_md_path.read_text()
        assert "new-cmd" in content
        assert "old-cmd" not in content
        assert content.count(AGENTS_MD_START) == 1

    def test_appends_to_existing_file_without_markers(
        self, tmp_path: Path
    ) -> None:
        """If AGENTS.md exists without markers, append section."""
        agents_md_path = tmp_path / "AGENTS.md"
        agents_md_path.write_text("# My Project Agents\n\nCustom content.\n")

        bundle = PluginBundle(
            commands=[
                PluginCommand(name="search", description="Search", body="")
            ]
        )
        _update_agents_md(agents_md_path, bundle)
        content = agents_md_path.read_text()
        assert "My Project Agents" in content
        assert "Custom content" in content
        assert AGENTS_MD_START in content

    def test_preserves_surrounding_content(self, tmp_path: Path) -> None:
        """Content before and after markers should be preserved."""
        agents_md_path = tmp_path / "AGENTS.md"
        agents_md_path.write_text(
            f"# Before\n\n{AGENTS_MD_START}\nold section\n"
            f"{AGENTS_MD_END}\n\n# After\n"
        )
        bundle = PluginBundle(
            commands=[
                PluginCommand(name="search", description="Search", body="")
            ]
        )
        _update_agents_md(agents_md_path, bundle)
        content = agents_md_path.read_text()
        assert "# Before" in content
        assert "# After" in content
        assert "old section" not in content
        assert "search" in content


class TestAddCodexHeader:
    """Tests for Codex header injection."""

    def test_adds_header_after_frontmatter(self) -> None:
        content = "---\nname: test\n---\nBody content.\n"
        result = _add_codex_header(content, "test-cmd")
        assert "Codex Skill:" in result
        assert "test-cmd" in result
        # Body should still be present
        assert "Body content." in result

    def test_no_frontmatter_returns_unchanged(self) -> None:
        content = "Just plain content."
        result = _add_codex_header(content, "test")
        assert result == content


class TestCodexDryRun:
    """Tests for Codex dry-run via install_agent command."""

    @pytest.fixture
    def plugin_dir(self, tmp_path: Path) -> Path:
        """Create minimal plugin directory."""
        root = tmp_path / "plugin"
        root.mkdir()
        manifest = root / ".claude-plugin"
        manifest.mkdir()
        (manifest / "plugin.json").write_text(
            json.dumps({"name": "agent-brain", "version": "1.0.0"})
        )
        cmds = root / "commands"
        cmds.mkdir()
        (cmds / "agent-brain-search.md").write_text(
            "---\nname: agent-brain-search\n"
            "description: Search\nparameters: []\nskills: []\n"
            "---\nBody."
        )
        agents = root / "agents"
        agents.mkdir()
        (agents / "search-assistant.md").write_text(
            "---\nname: search-assistant\n"
            "description: Helper\ntriggers: []\nskills: []\n"
            "---\nBody."
        )
        skills = root / "skills" / "using-agent-brain"
        skills.mkdir(parents=True)
        (skills / "SKILL.md").write_text(
            "---\nname: using-agent-brain\n"
            "description: Skill\nallowed-tools: [Bash]\n"
            "---\nBody."
        )
        return root

    def test_codex_dry_run(
        self, tmp_path: Path, plugin_dir: Path
    ) -> None:
        """Test --agent codex --dry-run via CLI runner."""
        from click.testing import CliRunner

        from agent_brain_cli.commands.install_agent import (
            install_agent_command,
        )

        runner = CliRunner()
        result = runner.invoke(
            install_agent_command,
            [
                "--agent",
                "codex",
                "--plugin-dir",
                str(plugin_dir),
                "--path",
                str(tmp_path),
                "--dry-run",
                "--json",
            ],
        )
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output["dry_run"] is True
        assert output["agent"] == "codex"
        assert output["file_count"] > 0

    def test_codex_install(
        self, tmp_path: Path, plugin_dir: Path
    ) -> None:
        """Test --agent codex installs to .codex/skills/agent-brain."""
        from click.testing import CliRunner

        from agent_brain_cli.commands.install_agent import (
            install_agent_command,
        )

        runner = CliRunner()
        result = runner.invoke(
            install_agent_command,
            [
                "--agent",
                "codex",
                "--plugin-dir",
                str(plugin_dir),
                "--path",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 0
        target = tmp_path / ".codex" / "skills" / "agent-brain"
        assert target.is_dir()
        assert (target / "agent-brain-search" / "SKILL.md").exists()

    def test_skill_runtime_requires_dir(self, tmp_path: Path, plugin_dir: Path) -> None:
        """Test --agent skill-runtime without --dir fails."""
        from click.testing import CliRunner

        from agent_brain_cli.commands.install_agent import (
            install_agent_command,
        )

        runner = CliRunner()
        result = runner.invoke(
            install_agent_command,
            [
                "--agent",
                "skill-runtime",
                "--plugin-dir",
                str(plugin_dir),
                "--path",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 1
        assert "--dir is required" in result.output

    def test_skill_runtime_with_dir(
        self, tmp_path: Path, plugin_dir: Path
    ) -> None:
        """Test --agent skill-runtime --dir works."""
        from click.testing import CliRunner

        from agent_brain_cli.commands.install_agent import (
            install_agent_command,
        )

        runner = CliRunner()
        skill_dir = tmp_path / "custom-skills"
        result = runner.invoke(
            install_agent_command,
            [
                "--agent",
                "skill-runtime",
                "--plugin-dir",
                str(plugin_dir),
                "--dir",
                str(skill_dir),
            ],
        )
        assert result.exit_code == 0
        assert skill_dir.is_dir()
        assert (skill_dir / "agent-brain-search" / "SKILL.md").exists()
