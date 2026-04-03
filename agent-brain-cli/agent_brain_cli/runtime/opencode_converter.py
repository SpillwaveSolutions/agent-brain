"""OpenCode runtime converter.

OpenCode uses a different format:
- Tool names are lowercase
- `allowed-tools` list becomes a `tools` boolean object
- Named colors are converted to hex
- Plugins must be registered in opencode.json with read/external_directory permissions
"""

import json
import logging
import shutil
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

# Path rewrites applied in order (longer matches first to avoid partial replacement)
PATH_REWRITES = [
    (".claude/agent-brain", ".agent-brain"),
    ("~/.claude/plugins/", "~/.config/opencode/"),
    ("~/.claude", "~/.config/opencode"),
]


def _replace_paths(text: str) -> str:
    """Apply all path rewrites to replace Claude paths with OpenCode equivalents."""
    for old, new in PATH_REWRITES:
        text = text.replace(old, new)
    return text


def _tools_to_bool_object(tools: list[str]) -> dict[str, bool]:
    """Convert a tool name list to OpenCode's boolean object format."""
    mapped = map_tools(tools, "opencode")
    return dict.fromkeys(mapped, True)


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
            "description": agent.description,
        }
        # Tools boolean object from allowed_tools
        if agent.allowed_tools:
            fm["tools"] = _tools_to_bool_object(agent.allowed_tools)
        # Color as hex
        if agent.color:
            fm["color"] = _color_to_hex(agent.color)
        # Subagent type mapping
        if agent.subagent_type:
            st = agent.subagent_type
            if st == "general-purpose":
                st = "general"
            fm["subagent_type"] = st
        # Triggers and skills
        fm["triggers"] = [
            {"pattern": t.pattern, "type": t.type} for t in agent.triggers
        ]
        fm["skills"] = agent.skills
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

    def _register_in_opencode_json(
        self,
        target_dir: Path,
        scope: Scope,
    ) -> None:
        """Register plugin permissions in opencode.json.

        OpenCode requires plugins to have explicit read and external_directory
        permissions in opencode.json. This merges agent-brain entries without
        overwriting existing permissions.
        """
        # Derive the .opencode dir and opencode.json location
        # target_dir is like: <project>/.opencode/plugins/agent-brain
        opencode_dir = target_dir.parent.parent  # .opencode/
        config_path = opencode_dir / "opencode.json"

        # Build the permission path pattern
        # Use relative path for project scope, absolute for global
        if scope == Scope.PROJECT:
            perm_key = "./.opencode/plugins/agent-brain/*"
        else:
            perm_key = f"{target_dir}/*"

        # Load existing config or create minimal structure
        config: dict[str, object] = {}
        if config_path.exists():
            try:
                config = json.loads(config_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                logger.warning("Could not parse %s, creating fresh config", config_path)

        # Ensure structure exists
        if "permission" not in config:
            config["permission"] = {}
        permission = config["permission"]
        if not isinstance(permission, dict):
            permission = {}
            config["permission"] = permission

        # Additional permission for the project state directory
        state_perm_key = ".agent-brain/*"

        for section in ("read", "external_directory"):
            if section not in permission:
                permission[section] = {}
            section_dict = permission[section]
            if isinstance(section_dict, dict):
                if perm_key not in section_dict:
                    section_dict[perm_key] = "allow"
                if state_perm_key not in section_dict:
                    section_dict[state_perm_key] = "allow"

        # Ensure schema is present
        if "$schema" not in config:
            config["$schema"] = "https://opencode.ai/config.json"

        config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        logger.info("Registered agent-brain in %s", config_path)

    def install(
        self,
        bundle: PluginBundle,
        target_dir: Path,
        scope: Scope,
    ) -> list[Path]:
        """Install OpenCode plugin files and register in opencode.json."""
        # Idempotent install: remove existing target before reinstalling
        if target_dir.exists():
            shutil.rmtree(target_dir)

        created: list[Path] = []

        cmds_dir = target_dir / "command"
        cmds_dir.mkdir(parents=True, exist_ok=True)
        for cmd in bundle.commands:
            out = cmds_dir / f"{cmd.name}.md"
            out.write_text(self.convert_command(cmd), encoding="utf-8")
            created.append(out)

        agents_dir = target_dir / "agent"
        agents_dir.mkdir(parents=True, exist_ok=True)
        for agent in bundle.agents:
            out = agents_dir / f"{agent.name}.md"
            out.write_text(self.convert_agent(agent), encoding="utf-8")
            created.append(out)

        skills_dir = target_dir / "skill"
        for skill in bundle.skills:
            skill_out = skills_dir / skill.name
            skill_out.mkdir(parents=True, exist_ok=True)
            skill_file = skill_out / "SKILL.md"
            skill_file.write_text(self.convert_skill(skill), encoding="utf-8")
            created.append(skill_file)

        # Register plugin permissions in opencode.json
        self._register_in_opencode_json(target_dir, scope)

        return created
