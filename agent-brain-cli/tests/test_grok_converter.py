"""Tests for the Grok Build runtime converter."""

from pathlib import Path

from agent_brain_cli.runtime.grok_converter import GrokConverter
from agent_brain_cli.runtime.parser import parse_plugin_dir
from agent_brain_cli.runtime.types import RuntimeType, Scope

_UNIVERSAL_PLUGIN = (
    '{"$schema": "https://agent-plugins.org/schemas/1.0.0/'
    'plugin.schema.json", "name": "agent-brain"}'
)


def _plugin_dir(tmp_path: Path) -> Path:
    root = tmp_path / "plugin"
    (root / ".claude-plugin").mkdir(parents=True)
    (root / ".claude-plugin" / "plugin.json").write_text(
        '{"name": "agent-brain", "version": "1.0.0"}'
    )
    (root / ".grok-plugin").mkdir()
    (root / ".grok-plugin" / "marketplace.json").write_text(
        '{"name": "agent-brain-marketplace",'
        ' "version": "1.0.0", "plugins": []}'
    )
    (root / "plugin.json").write_text(_UNIVERSAL_PLUGIN)
    cmds = root / "commands"
    cmds.mkdir()
    (cmds / "agent-brain-search.md").write_text(
        "---\nname: agent-brain-search\n"
        "description: Search docs\nparameters: []\nskills: []\n"
        "---\nSearch in .claude/agent-brain/data."
    )
    return root


class TestGrokConverter:
    def test_runtime_type(self) -> None:
        assert GrokConverter().runtime_type is RuntimeType.GROK

    def test_install_creates_grok_layout(self, tmp_path: Path) -> None:
        source = _plugin_dir(tmp_path)
        bundle = parse_plugin_dir(source)
        target = tmp_path / ".grok" / "plugins" / "agent-brain"
        GrokConverter().install(bundle, target, Scope.PROJECT)

        assert (target / "commands" / "agent-brain-search.md").exists()
        assert (target / ".claude-plugin" / "plugin.json").exists()
        assert (target / ".grok-plugin" / "marketplace.json").exists()
        assert (target / "plugin.json").exists()
        content = (target / "commands" / "agent-brain-search.md").read_text()
        assert ".claude/agent-brain" not in content
