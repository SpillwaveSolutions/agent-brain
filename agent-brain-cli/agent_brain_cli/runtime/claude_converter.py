"""Claude Code runtime converter.

Claude is the canonical format, so this converter mostly passes through
files as-is, with path replacement from `.claude/agent-brain` to `.agent-brain`.
"""

import logging
import shutil
from pathlib import Path

import yaml

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
    """Replace legacy state dir paths with new runtime-neutral paths."""
    return text.replace(LEGACY_PATH, NEW_PATH)


def _rebuild_file(frontmatter: dict, body: str) -> str:  # type: ignore[type-arg]
    """Rebuild a markdown file from frontmatter dict and body."""
    yaml_str = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)
    return f"---\n{yaml_str}---\n{body}\n"


class ClaudeConverter:
    """Converter for Claude Code runtime (near-identity)."""

    @property
    def runtime_type(self) -> RuntimeType:
        return RuntimeType.CLAUDE

    def convert_command(self, command: PluginCommand) -> str:
        """Copy command with path replacements."""
        if command.source_path:
            text = Path(command.source_path).read_text(encoding="utf-8")
            return _replace_paths(text)
        # Fallback: reconstruct from parsed data
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
        """Copy agent with path replacements."""
        if agent.source_path:
            text = Path(agent.source_path).read_text(encoding="utf-8")
            return _replace_paths(text)
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
        """Copy skill with path replacements."""
        if skill.source_path:
            text = Path(skill.source_path).read_text(encoding="utf-8")
            return _replace_paths(text)
        fm: dict[str, object] = {
            "name": skill.name,
            "description": skill.description,
            "license": skill.license,
            "allowed-tools": skill.allowed_tools,
            "metadata": skill.metadata,
        }
        return _rebuild_file(fm, _replace_paths(skill.body))

    def install(
        self,
        bundle: PluginBundle,
        target_dir: Path,
        scope: Scope,
    ) -> list[Path]:
        """Install Claude plugin files.

        For Claude, the output structure mirrors the canonical layout.
        """
        created: list[Path] = []
        source = Path(bundle.source_dir)

        # Copy plugin.json
        manifest_src = source / ".claude-plugin" / "plugin.json"
        if manifest_src.exists():
            manifest_dest = target_dir / ".claude-plugin" / "plugin.json"
            manifest_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(manifest_src, manifest_dest)
            created.append(manifest_dest)

        # Convert and write commands
        cmds_dir = target_dir / "commands"
        cmds_dir.mkdir(parents=True, exist_ok=True)
        for cmd in bundle.commands:
            out_path = cmds_dir / f"{cmd.name}.md"
            out_path.write_text(self.convert_command(cmd), encoding="utf-8")
            created.append(out_path)

        # Convert and write agents
        agents_dir = target_dir / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        for agent in bundle.agents:
            out_path = agents_dir / f"{agent.name}.md"
            out_path.write_text(self.convert_agent(agent), encoding="utf-8")
            created.append(out_path)

        # Convert and write skills (with references)
        skills_dir = target_dir / "skills"
        for skill in bundle.skills:
            skill_out = skills_dir / skill.name
            skill_out.mkdir(parents=True, exist_ok=True)
            skill_file = skill_out / "SKILL.md"
            skill_file.write_text(self.convert_skill(skill), encoding="utf-8")
            created.append(skill_file)

            # Copy references directory if it exists
            if skill.source_path:
                refs_src = Path(skill.source_path).parent / "references"
                if refs_src.is_dir():
                    refs_dest = skill_out / "references"
                    if refs_dest.exists():
                        shutil.rmtree(refs_dest)
                    shutil.copytree(refs_src, refs_dest)
                    for ref in refs_dest.rglob("*"):
                        if ref.is_file():
                            created.append(ref)

        return created
