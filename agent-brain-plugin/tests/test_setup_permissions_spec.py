"""Regression checks for setup-assistant policy island wiring."""

from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parent.parent
AGENT_PATH = PLUGIN_DIR / "agents" / "setup-assistant.md"
COMMAND_PATHS = [
    PLUGIN_DIR / "commands" / "agent-brain-config.md",
    PLUGIN_DIR / "commands" / "agent-brain-install.md",
    PLUGIN_DIR / "commands" / "agent-brain-setup.md",
    PLUGIN_DIR / "commands" / "agent-brain-init.md",
    PLUGIN_DIR / "commands" / "agent-brain-start.md",
    PLUGIN_DIR / "commands" / "agent-brain-verify.md",
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_setup_assistant_has_required_allowed_tools() -> None:
    content = _read(AGENT_PATH)

    assert "allowed_tools:" in content
    assert '"Write(~/.agent-brain/**)"' in content
    assert '"Edit(~/.agent-brain/**)"' in content
    assert '"Bash(~/.claude/plugins/agent-brain/scripts/*)"' in content
    assert '"Bash(.claude/plugins/agent-brain/scripts/*)"' in content


def test_setup_commands_bind_to_setup_assistant_policy_island() -> None:
    for command_path in COMMAND_PATHS:
        content = _read(command_path)
        assert "context: fork" in content, f"Missing context: fork in {command_path}"
        assert "agent: setup-assistant" in content, (
            f"Missing agent: setup-assistant in {command_path}"
        )
