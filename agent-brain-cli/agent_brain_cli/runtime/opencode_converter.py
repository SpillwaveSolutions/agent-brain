"""OpenCode runtime converter.

OpenCode uses a different format:
- Tool names are lowercase
- `allowed-tools` list becomes a `tools` boolean object
- Named colors are converted to hex
"""

import logging
from pathlib import Path

import yaml

from agent_brain_cli.runtime.tool_maps import map_tools
from agent_brain_cli.runtime.types import (
    PluginAgent,
    PluginBundle,
    PluginCommand,
    PluginSkill,
    RuntimeType,
    Scope,
)

logger = logging.getLogger(__name__)

# Color name to hex mapping for OpenCode
COLOR_MAP: dict[str, str] = {
    "red": "#FF0000",
    "green": "#00FF00",
    "blue": "#0000FF",
    "yellow": "#FFFF00",
    "orange": "#FFA500",
    "purple": "#800080",
    "cyan": "#00FFFF",
    "magenta": "#FF00FF",
    "white": "#FFFFFF",
    "black": "#000000",
    "gray": "#808080",
    "grey": "#808080",
}

LEGACY_PATH = ".claude/agent-brain"
NEW_PATH = ".agent-brain"


def _replace_paths(text: str) -> str:
    return text.replace(LEGACY_PATH, NEW_PATH)


def _tools_to_bool_object(tools: list[str]) -> dict[str, bool]:
    """Convert a tool name list to OpenCode's boolean object format."""
    mapped = map_tools(tools, "opencode")
    return {tool: True for tool in mapped}


def _color_to_hex(color: str) -> str:
    """Convert a named color to hex, pass hex through unchanged."""
    if color.startswith("#"):
        return color
    return COLOR_MAP.get(color.lower(), color)


def _rebuild_file(frontmatter: dict, body: str) -> str:  # type: ignore[type-arg]
    yaml_str = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)
    return f"---\n{yaml_str}---\n{body}\n"


class OpenCodeConverter:
    """Converter for OpenCode runtime."""

    @property
    def runtime_type(self) -> RuntimeType:
        return RuntimeType.OPENCODE

    def convert_command(self, command: PluginCommand) -> str:
        fm: dict[str, object] = {
            "name": command.name,
            "description": command.description,
            "parameters": [
                {
                    "name": p.name,
                    "description": p.description,
                    "required": p.required,
                    **({"default": p.default} if p.default else {}),
                }
                for p in command.parameters
            ],
            "skills": command.skills,
        }
        return _rebuild_file(fm, _replace_paths(command.body))

    def convert_agent(self, agent: PluginAgent) -> str:
        fm: dict[str, object] = {
            "name": agent.name,
            "description": agent.description,
            "triggers": [
                {"pattern": t.pattern, "type": t.type} for t in agent.triggers
            ],
            "skills": agent.skills,
        }
        return _rebuild_file(fm, _replace_paths(agent.body))

    def convert_skill(self, skill: PluginSkill) -> str:
        """Convert skill with tool boolean object instead of list."""
        tools_obj = _tools_to_bool_object(skill.allowed_tools)
        fm: dict[str, object] = {
            "name": skill.name,
            "description": skill.description,
            "license": skill.license,
            "tools": tools_obj,
            "metadata": skill.metadata,
        }
        return _rebuild_file(fm, _replace_paths(skill.body))

    def install(
        self,
        bundle: PluginBundle,
        target_dir: Path,
        scope: Scope,
    ) -> list[Path]:
        """Install OpenCode plugin files."""
        created: list[Path] = []

        cmds_dir = target_dir / "commands"
        cmds_dir.mkdir(parents=True, exist_ok=True)
        for cmd in bundle.commands:
            out = cmds_dir / f"{cmd.name}.md"
            out.write_text(self.convert_command(cmd), encoding="utf-8")
            created.append(out)

        agents_dir = target_dir / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        for agent in bundle.agents:
            out = agents_dir / f"{agent.name}.md"
            out.write_text(self.convert_agent(agent), encoding="utf-8")
            created.append(out)

        skills_dir = target_dir / "skills"
        for skill in bundle.skills:
            skill_out = skills_dir / skill.name
            skill_out.mkdir(parents=True, exist_ok=True)
            skill_file = skill_out / "SKILL.md"
            skill_file.write_text(self.convert_skill(skill), encoding="utf-8")
            created.append(skill_file)

        return created
