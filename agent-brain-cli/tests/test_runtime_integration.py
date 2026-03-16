"""Integration tests for all 5 runtime converters against the real plugin."""

from pathlib import Path

import pytest
import yaml

from agent_brain_cli.runtime.claude_converter import ClaudeConverter
from agent_brain_cli.runtime.codex_converter import CodexConverter
from agent_brain_cli.runtime.gemini_converter import GeminiConverter
from agent_brain_cli.runtime.opencode_converter import OpenCodeConverter
from agent_brain_cli.runtime.parser import parse_plugin_dir
from agent_brain_cli.runtime.skill_runtime_converter import SkillRuntimeConverter
from agent_brain_cli.runtime.types import Scope


@pytest.fixture
def real_plugin_dir() -> Path:
    """Return path to real plugin dir, skip if not found."""
    path = Path(__file__).parent.parent.parent / "agent-brain-plugin"
    if not path.is_dir():
        pytest.skip("Real plugin dir not found")
    return path


class TestAllConvertersIntegration:
    """Integration tests: parse real plugin → convert with all 5 converters."""

    def test_claude_produces_canonical_layout(
        self, real_plugin_dir: Path, tmp_path: Path
    ) -> None:
        bundle = parse_plugin_dir(real_plugin_dir)
        converter = ClaudeConverter()
        target = tmp_path / "claude"
        files = converter.install(bundle, target, Scope.PROJECT)

        assert (target / "commands").is_dir()
        assert (target / "agents").is_dir()
        assert (target / "skills").is_dir()
        assert len(files) > 30

    def test_opencode_produces_tools_objects(
        self, real_plugin_dir: Path, tmp_path: Path
    ) -> None:
        bundle = parse_plugin_dir(real_plugin_dir)
        converter = OpenCodeConverter()
        target = tmp_path / "opencode"
        files = converter.install(bundle, target, Scope.PROJECT)

        # Check skills use tools: {bash: true} format
        for skill in bundle.skills:
            skill_file = target / "skills" / skill.name / "SKILL.md"
            if skill_file.exists():
                content = skill_file.read_text()
                assert "tools:" in content
        assert len(files) > 30

    def test_gemini_maps_tool_names(
        self, real_plugin_dir: Path, tmp_path: Path
    ) -> None:
        bundle = parse_plugin_dir(real_plugin_dir)
        converter = GeminiConverter()
        target = tmp_path / "gemini"
        files = converter.install(bundle, target, Scope.PROJECT)

        # Check skills use Gemini tool names
        for skill in bundle.skills:
            skill_file = target / "skills" / skill.name / "SKILL.md"
            if skill_file.exists():
                content = skill_file.read_text()
                if "Bash" in str(skill.allowed_tools):
                    assert "run_shell_command" in content
        assert len(files) > 30

    def test_skill_runtime_flattens_to_skill_dirs(
        self, real_plugin_dir: Path, tmp_path: Path
    ) -> None:
        bundle = parse_plugin_dir(real_plugin_dir)
        converter = SkillRuntimeConverter()
        target = tmp_path / "skill-runtime"
        files = converter.install(bundle, target, Scope.PROJECT)

        # Everything should be flat skill directories
        skill_dirs = [d for d in target.iterdir() if d.is_dir()]
        expected_min = len(bundle.commands) + len(bundle.agents) + len(bundle.skills)
        assert len(skill_dirs) >= expected_min

        # Every dir should have SKILL.md
        for d in skill_dirs:
            assert (d / "SKILL.md").exists(), f"Missing SKILL.md in {d.name}"

        # Should have templates and scripts
        if bundle.templates:
            assert (target / "agent-brain-setup" / "assets").is_dir()
        if bundle.scripts:
            assert (target / "agent-brain-verify" / "scripts").is_dir()

        assert len(files) >= 30

    def test_codex_creates_skills_and_agents_md(
        self, real_plugin_dir: Path, tmp_path: Path
    ) -> None:
        bundle = parse_plugin_dir(real_plugin_dir)
        converter = CodexConverter()
        target = tmp_path / ".codex" / "skills" / "agent-brain"
        files = converter.install(bundle, target, Scope.PROJECT, project_root=tmp_path)

        # Skill directories should exist
        skill_dirs = [d for d in target.iterdir() if d.is_dir()]
        assert len(skill_dirs) >= (
            len(bundle.commands) + len(bundle.agents) + len(bundle.skills)
        )

        # AGENTS.md should exist at project root
        agents_md = tmp_path / "AGENTS.md"
        assert agents_md.exists()
        content = agents_md.read_text()
        assert "Agent Brain" in content
        assert "agent-brain:start" in content

        # Command skills should have Codex headers
        for cmd in bundle.commands[:3]:  # Check first 3
            from agent_brain_cli.runtime.skill_runtime_converter import (
                _skill_dir_name,
            )

            skill_name = _skill_dir_name(cmd.name)
            skill_file = target / skill_name / "SKILL.md"
            if skill_file.exists():
                assert "Codex Skill:" in skill_file.read_text()

        assert len(files) >= 30

    def test_all_converters_replace_legacy_paths(
        self, real_plugin_dir: Path, tmp_path: Path
    ) -> None:
        """Verify no converter leaves .claude/agent-brain paths."""
        bundle = parse_plugin_dir(real_plugin_dir)

        converters = [
            ("claude", ClaudeConverter()),
            ("opencode", OpenCodeConverter()),
            ("gemini", GeminiConverter()),
            ("skill-runtime", SkillRuntimeConverter()),
        ]

        for name, converter in converters:
            target = tmp_path / name
            converter.install(bundle, target, Scope.PROJECT)

            for md_file in target.rglob("*.md"):
                content = md_file.read_text()
                assert (
                    ".claude/agent-brain" not in content
                ), f"Legacy path found in {name}/{md_file.relative_to(target)}"

    def test_all_skill_mds_have_valid_yaml(
        self, real_plugin_dir: Path, tmp_path: Path
    ) -> None:
        """Every SKILL.md produced by any converter has valid YAML frontmatter."""
        bundle = parse_plugin_dir(real_plugin_dir)

        converter = SkillRuntimeConverter()
        target = tmp_path / "check"
        converter.install(bundle, target, Scope.PROJECT)

        for skill_md in target.rglob("SKILL.md"):
            content = skill_md.read_text()
            assert content.startswith("---\n"), f"Bad frontmatter start in {skill_md}"
            parts = content.split("---\n")
            assert len(parts) >= 3, f"Missing closing --- in {skill_md}"
            fm = yaml.safe_load(parts[1])
            assert isinstance(fm, dict), f"Non-dict frontmatter in {skill_md}"
            assert "name" in fm, f"Missing name in {skill_md}"

    def test_parser_extracts_templates_and_scripts(self, real_plugin_dir: Path) -> None:
        """Verify parser finds templates and scripts from real plugin."""
        bundle = parse_plugin_dir(real_plugin_dir)

        # Real plugin has templates/ and scripts/
        assert (
            len(bundle.templates) >= 1
        ), f"Expected templates, got {len(bundle.templates)}"
        assert len(bundle.scripts) >= 1, f"Expected scripts, got {len(bundle.scripts)}"

        template_names = [t.name for t in bundle.templates]
        assert "settings.json" in template_names

        script_names = [s.name for s in bundle.scripts]
        assert "ab-setup-check.sh" in script_names
