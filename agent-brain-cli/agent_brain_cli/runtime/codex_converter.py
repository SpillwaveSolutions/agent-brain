"""Codex runtime converter.

Codex is a named preset built on the generic skill-runtime converter.
It installs to `.codex/skills/agent-brain/` and generates an AGENTS.md
file at the project root with Agent Brain guidance.

Key differences from base SkillRuntimeConverter:
    - Default install dir: .codex/skills/agent-brain/
    - AGENTS.md generated at project root (idempotent via HTML comment markers)
    - Skills include invocation guidance headers
"""

import logging
from pathlib import Path

from agent_brain_cli.runtime.skill_runtime_converter import (
    SkillRuntimeConverter,
)
from agent_brain_cli.runtime.types import (
    PluginAgent,
    PluginBundle,
    PluginCommand,
    PluginSkill,
    RuntimeType,
    Scope,
)

logger = logging.getLogger(__name__)

# HTML comment markers for idempotent AGENTS.md updates
AGENTS_MD_START = "<!-- agent-brain:start -->"
AGENTS_MD_END = "<!-- agent-brain:end -->"

AGENTS_MD_SECTION = """\
{start_marker}

## Agent Brain

Agent Brain provides semantic search over your codebase and documentation.

### Available Skills

| Skill | Description |
|-------|-------------|
{skill_table}

### Usage

Ask your AI assistant to search documentation or code:

- "Search for authentication patterns in my codebase"
- "Find documentation about the API endpoints"
- "Look up how error handling works"

### Setup

Run `agent-brain start` to start the Agent Brain server, then use
`agent-brain index ./src` to index your source code.

{end_marker}"""


class CodexConverter:
    """Converter for Codex runtime (skill-runtime preset).

    Delegates skill-directory creation to SkillRuntimeConverter and
    adds Codex-specific AGENTS.md generation.
    """

    def __init__(self) -> None:
        self._base = SkillRuntimeConverter()

    @property
    def runtime_type(self) -> RuntimeType:
        return RuntimeType.CODEX

    def convert_command(self, command: PluginCommand) -> str:
        """Convert command with Codex invocation guidance header."""
        base_content = self._base.convert_command(command)
        return _add_codex_header(base_content, command.name)

    def convert_agent(self, agent: PluginAgent) -> str:
        """Convert agent with Codex invocation guidance header."""
        base_content = self._base.convert_agent(agent)
        return _add_codex_header(base_content, agent.name)

    def convert_skill(self, skill: PluginSkill) -> str:
        """Convert skill with Codex invocation guidance header."""
        return self._base.convert_skill(skill)

    def install(
        self,
        bundle: PluginBundle,
        target_dir: Path,
        scope: Scope,
        project_root: Path | None = None,
    ) -> list[Path]:
        """Install Codex skills and generate AGENTS.md.

        Delegates skill-directory creation to the base converter,
        then generates/updates AGENTS.md at the project root.

        Args:
            bundle: Parsed plugin bundle.
            target_dir: Where to write skill directories.
            scope: Project-level or global installation.
            project_root: Project root for AGENTS.md. If None,
                derived from target_dir for project scope.
        """
        # Install skill directories via base converter
        created = self._base.install(bundle, target_dir, scope)

        # Re-write command and agent SKILL.md files with Codex headers
        for cmd in bundle.commands:
            from agent_brain_cli.runtime.skill_runtime_converter import (
                _skill_dir_name,
            )

            skill_name = _skill_dir_name(cmd.name)
            skill_file = target_dir / skill_name / "SKILL.md"
            if skill_file.exists():
                skill_file.write_text(self.convert_command(cmd), encoding="utf-8")

        for agent in bundle.agents:
            from agent_brain_cli.runtime.skill_runtime_converter import (
                _skill_dir_name,
            )

            skill_name = _skill_dir_name(agent.name)
            skill_file = target_dir / skill_name / "SKILL.md"
            if skill_file.exists():
                skill_file.write_text(self.convert_agent(agent), encoding="utf-8")

        # Generate AGENTS.md at project root
        if project_root is None:
            if scope == Scope.PROJECT:
                # .codex/skills/agent-brain → project root (3 levels up)
                project_root = target_dir.parent.parent.parent
            else:
                project_root = Path.cwd()

        agents_md_path = project_root / "AGENTS.md"
        try:
            agents_md_files = _update_agents_md(agents_md_path, bundle)
            created.extend(agents_md_files)
        except OSError as exc:
            logger.warning("Could not write AGENTS.md: %s", exc)

        return created


def _add_codex_header(content: str, name: str) -> str:
    """Add a Codex invocation guidance header after the frontmatter.

    Inserts a brief note about how to invoke this skill in Codex.
    """
    # Split on the closing --- of frontmatter
    parts = content.split("---\n", 2)
    if len(parts) < 3:
        return content

    header = (
        f"> **Codex Skill:** `{name}`\n"
        f"> Invoke by asking about {name} or referencing it directly.\n\n"
    )
    return f"---\n{parts[1]}---\n{header}{parts[2]}"


def _update_agents_md(agents_md_path: Path, bundle: PluginBundle) -> list[Path]:
    """Generate or update AGENTS.md with Agent Brain section.

    Uses HTML comment markers for idempotent updates — running this
    multiple times will replace the existing section rather than
    duplicating it.

    Returns list of created/updated paths.
    """
    # Build skill table
    skill_rows: list[str] = []
    for cmd in bundle.commands:
        skill_rows.append(f"| {cmd.name} | {cmd.description} |")
    for agent in bundle.agents:
        skill_rows.append(f"| {agent.name} | {agent.description} |")
    for skill in bundle.skills:
        skill_rows.append(f"| {skill.name} | {skill.description} |")

    skill_table = "\n".join(skill_rows) if skill_rows else "| (none) | - |"

    section = AGENTS_MD_SECTION.format(
        start_marker=AGENTS_MD_START,
        end_marker=AGENTS_MD_END,
        skill_table=skill_table,
    )

    if agents_md_path.exists():
        existing = agents_md_path.read_text(encoding="utf-8")
        if AGENTS_MD_START in existing and AGENTS_MD_END in existing:
            # Replace existing section
            start_idx = existing.index(AGENTS_MD_START)
            end_idx = existing.index(AGENTS_MD_END) + len(AGENTS_MD_END)
            updated = existing[:start_idx] + section + existing[end_idx:]
            agents_md_path.write_text(updated, encoding="utf-8")
        else:
            # Append section
            agents_md_path.write_text(
                existing.rstrip() + "\n\n" + section + "\n",
                encoding="utf-8",
            )
    else:
        # Create new file
        content = f"# AGENTS.md\n\n{section}\n"
        agents_md_path.parent.mkdir(parents=True, exist_ok=True)
        agents_md_path.write_text(content, encoding="utf-8")

    return [agents_md_path]
