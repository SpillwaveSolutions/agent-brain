"""Gemini CLI runtime converter.

Gemini uses different tool names and doesn't support some fields:
- Tool names: Read→read_file, Write→write_file, Edit→replace, Bash→run_shell_command
- No `color` field support
- Skills use `tools` list with Gemini-mapped names
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

LEGACY_PATH = ".claude/agent-brain"
NEW_PATH = ".agent-brain"


def _replace_paths(text: str) -> str:
    return text.replace(LEGACY_PATH, NEW_PATH)


def _rebuild_file(frontmatter: dict, body: str) -> str:  # type: ignore[type-arg]
    yaml_str = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)
    return f"---\n{yaml_str}---\n{body}\n"


class GeminiConverter:
    """Converter for Gemini CLI runtime."""

    @property
    def runtime_type(self) -> RuntimeType:
        return RuntimeType.GEMINI

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
        """Convert skill with Gemini-mapped tool names, no color field."""
        mapped_tools = map_tools(skill.allowed_tools, "gemini")
        # Filter out unsupported metadata fields
        clean_metadata = {k: v for k, v in skill.metadata.items() if k != "color"}
        fm: dict[str, object] = {
            "name": skill.name,
            "description": skill.description,
            "license": skill.license,
            "allowed-tools": mapped_tools,
            "metadata": clean_metadata,
        }
        return _rebuild_file(fm, _replace_paths(skill.body))

    def install(
        self,
        bundle: PluginBundle,
        target_dir: Path,
        scope: Scope,
    ) -> list[Path]:
        """Install Gemini CLI plugin files."""
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
