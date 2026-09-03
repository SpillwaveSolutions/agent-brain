"""Tests for the Cursor runtime converter."""

from pathlib import Path

from agent_brain_cli.runtime.cursor_converter import CursorConverter
from agent_brain_cli.runtime.parser import parse_plugin_dir
from agent_brain_cli.runtime.types import RuntimeType, Scope

_CURSOR_PLUGIN = (
    '{"name": "agent-brain", "version": "1.0.0",'
    ' "skills": "skills/", "commands": "commands/"}'
)
_UNIVERSAL_PLUGIN = (
    '{"$schema": "https://agent-plugins.org/schemas/1.0.0/'
    'plugin.schema.json", "name": "agent-brain"}'
)
_MCP = (
    '{"$schema": "https://agent-plugins.org/schemas/1.0.0/'
    'mcp.schema.json", "mcpServers": {}}'
)


def _plugin_dir(tmp_path: Path) -> Path:
    root = tmp_path / "plugin"
    (root / ".claude-plugin").mkdir(parents=True)
    (root / ".claude-plugin" / "plugin.json").write_text(
        '{"name": "agent-brain", "version": "1.0.0"}'
    )
    (root / ".cursor-plugin").mkdir()
    (root / ".cursor-plugin" / "plugin.json").write_text(_CURSOR_PLUGIN)
    (root / "plugin.json").write_text(_UNIVERSAL_PLUGIN)
    (root / "mcp.json").write_text(_MCP)
    cmds = root / "commands"
    cmds.mkdir()
    (cmds / "agent-brain-search.md").write_text(
        "---\nname: agent-brain-search\n"
        "description: Search docs\nparameters: []\nskills: []\n"
        "---\nSearch in .claude/agent-brain/data."
    )
    skills = root / "skills" / "using-agent-brain"
    skills.mkdir(parents=True)
    (skills / "SKILL.md").write_text(
        "---\nname: using-agent-brain\n"
        "description: Search skill\n"
        "allowed-tools:\n  - Bash\n"
        "---\nSkill body."
    )
    return root


class TestCursorConverter:
    def test_runtime_type(self) -> None:
        assert CursorConverter().runtime_type is RuntimeType.CURSOR

    def test_install_creates_cursor_layout(self, tmp_path: Path) -> None:
        source = _plugin_dir(tmp_path)
        bundle = parse_plugin_dir(source)
        target = tmp_path / ".cursor" / "plugins" / "agent-brain"
        created = CursorConverter().install(bundle, target, Scope.PROJECT)

        assert (target / "commands" / "agent-brain-search.md").exists()
        assert (target / "skills" / "using-agent-brain" / "SKILL.md").exists()
        assert (target / ".cursor-plugin" / "plugin.json").exists()
        assert (target / "plugin.json").exists()
        assert (target / "mcp.json").exists()
        content = (target / "commands" / "agent-brain-search.md").read_text()
        assert ".agent-brain" in content
        assert ".claude/agent-brain" not in content
        assert any(p.name == "plugin.json" for p in created)
