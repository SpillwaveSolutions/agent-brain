"""Generic skill-runtime converter.

Transforms all plugin artifacts (commands, agents, skills, templates, scripts)
into flat skill directories. Each artifact becomes a directory with a SKILL.md
file. This converter supports any runtime that uses skill directories (Codex,
Qwen, Cursor, etc.) via the --dir option.

Transformation rules:
    command agent-brain-init.md  → <dir>/agent-brain-init/SKILL.md
    agent research-assistant.md  → <dir>/agent-brain-research/SKILL.md
    skill using-agent-brain/     → <dir>/agent-brain-using/SKILL.md + references/
    templates/*                  → <dir>/agent-brain-setup/assets/
    scripts/*                    → <dir>/agent-brain-verify/scripts/
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


def _build_skill_md(frontmatter: dict, body: str) -> str:  # type: ignore[type-arg]
    """Build a SKILL.md file from frontmatter and body."""
    yaml_str = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)
    return f"---\n{yaml_str}---\n{body}\n"


def _skill_dir_name(name: str, prefix: str = "agent-brain-") -> str:
    """Derive a skill directory name from an artifact name.

    Ensures the name starts with the agent-brain- prefix for namespacing.
    """
    if name.startswith(prefix):
        return name
    return f"{prefix}{name}"


class SkillRuntimeConverter:
    """Converter that flattens all plugin artifacts into skill directories.

    Commands become skills with their body as instructions.
    Agents become orchestration skills referencing dependent skills.
    Existing skills are copied with references intact.
    Templates and scripts become asset skill directories.
    """

    @property
    def runtime_type(self) -> RuntimeType:
        return RuntimeType.SKILL_RUNTIME

    def convert_command(self, command: PluginCommand) -> str:
        """Convert a command into a SKILL.md file.

        The command body becomes the skill instructions, with
        allowed-tools set to common tools needed for CLI commands.
        """
        fm: dict[str, object] = {
            "name": command.name,
            "description": command.description,
            "allowed-tools": ["Bash", "Read", "Write"],
        }
        if command.parameters:
            params_text = "\n\n## Parameters\n\n"
            for p in command.parameters:
                req = " (required)" if p.required else ""
                default = f" [default: {p.default}]" if p.default else ""
                params_text += f"- **{p.name}**: {p.description}{req}{default}\n"
            body = _replace_paths(command.body) + params_text
        else:
            body = _replace_paths(command.body)
        return _build_skill_md(fm, body)

    def convert_agent(self, agent: PluginAgent) -> str:
        """Convert an agent into an orchestration SKILL.md file.

        The agent body becomes skill instructions with a note that
        this is an orchestration skill.
        """
        fm: dict[str, object] = {
            "name": agent.name,
            "description": agent.description,
            "allowed-tools": ["Bash", "Read", "Write", "Grep", "Glob"],
        }
        header = "<!-- Orchestration skill converted from agent -->\n\n"
        if agent.skills:
            header += "## Related Skills\n\n"
            for skill_name in agent.skills:
                header += f"- {skill_name}\n"
            header += "\n"
        body = header + _replace_paths(agent.body)
        return _build_skill_md(fm, body)

    def convert_skill(self, skill: PluginSkill) -> str:
        """Convert a skill, preserving its existing format."""
        fm: dict[str, object] = {
            "name": skill.name,
            "description": skill.description,
            "allowed-tools": skill.allowed_tools,
        }
        if skill.license:
            fm["license"] = skill.license
        if skill.metadata:
            fm["metadata"] = skill.metadata
        return _build_skill_md(fm, _replace_paths(skill.body))

    def install(
        self,
        bundle: PluginBundle,
        target_dir: Path,
        scope: Scope,
    ) -> list[Path]:
        """Install all plugin artifacts as flat skill directories.

        Each artifact gets its own directory under target_dir with a
        SKILL.md file. References, templates, and scripts are included
        as assets.
        """
        created: list[Path] = []

        # Commands → skill directories
        for cmd in bundle.commands:
            skill_name = _skill_dir_name(cmd.name)
            skill_dir = target_dir / skill_name
            skill_dir.mkdir(parents=True, exist_ok=True)
            skill_file = skill_dir / "SKILL.md"
            skill_file.write_text(self.convert_command(cmd), encoding="utf-8")
            created.append(skill_file)

        # Agents → orchestration skill directories
        for agent in bundle.agents:
            skill_name = _skill_dir_name(agent.name)
            skill_dir = target_dir / skill_name
            skill_dir.mkdir(parents=True, exist_ok=True)
            skill_file = skill_dir / "SKILL.md"
            skill_file.write_text(self.convert_agent(agent), encoding="utf-8")
            created.append(skill_file)

        # Skills → skill directories (with references)
        for skill in bundle.skills:
            skill_name = _skill_dir_name(skill.name)
            skill_dir = target_dir / skill_name
            skill_dir.mkdir(parents=True, exist_ok=True)
            skill_file = skill_dir / "SKILL.md"
            skill_file.write_text(self.convert_skill(skill), encoding="utf-8")
            created.append(skill_file)

            # Copy references if they exist
            if skill.source_path:
                refs_src = Path(skill.source_path).parent / "references"
                if refs_src.is_dir():
                    refs_dest = skill_dir / "references"
                    if refs_dest.exists():
                        shutil.rmtree(refs_dest)
                    shutil.copytree(refs_src, refs_dest)
                    for ref in refs_dest.rglob("*"):
                        if ref.is_file():
                            created.append(ref)

        # Templates → agent-brain-setup/assets/
        if bundle.templates:
            setup_dir = target_dir / "agent-brain-setup"
            assets_dir = setup_dir / "assets"
            assets_dir.mkdir(parents=True, exist_ok=True)
            # Create a setup SKILL.md if it doesn't exist
            setup_skill = setup_dir / "SKILL.md"
            if not setup_skill.exists():
                fm: dict[str, object] = {
                    "name": "agent-brain-setup",
                    "description": "Agent Brain setup templates and configuration",
                    "allowed-tools": ["Bash", "Read", "Write"],
                }
                body = (
                    "This skill contains setup templates for Agent Brain.\n\n"
                    "## Assets\n\n"
                )
                for tpl in bundle.templates:
                    body += f"- `assets/{tpl.name}`\n"
                setup_skill.write_text(
                    _build_skill_md(fm, body), encoding="utf-8"
                )
                created.append(setup_skill)

            for tpl in bundle.templates:
                tpl_file = assets_dir / tpl.name
                tpl_file.write_text(tpl.content, encoding="utf-8")
                created.append(tpl_file)

        # Scripts → agent-brain-verify/scripts/
        if bundle.scripts:
            verify_dir = target_dir / "agent-brain-verify"
            scripts_dir = verify_dir / "scripts"
            scripts_dir.mkdir(parents=True, exist_ok=True)
            # Create a verify SKILL.md if it doesn't exist
            verify_skill = verify_dir / "SKILL.md"
            if not verify_skill.exists():
                fm_v: dict[str, object] = {
                    "name": "agent-brain-verify",
                    "description": "Agent Brain verification and health check scripts",
                    "allowed-tools": ["Bash", "Read"],
                }
                body_v = (
                    "This skill contains verification scripts for "
                    "Agent Brain.\n\n"
                    "## Scripts\n\n"
                )
                for script in bundle.scripts:
                    body_v += f"- `scripts/{script.name}`\n"
                verify_skill.write_text(
                    _build_skill_md(fm_v, body_v), encoding="utf-8"
                )
                created.append(verify_skill)

            for script in bundle.scripts:
                script_file = scripts_dir / script.name
                script_file.write_text(script.content, encoding="utf-8")
                created.append(script_file)

        return created
