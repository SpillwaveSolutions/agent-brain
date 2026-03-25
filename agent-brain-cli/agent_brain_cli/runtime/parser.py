"""Plugin directory parser for YAML frontmatter + markdown files."""

import json
import logging
from pathlib import Path
from typing import Any

import yaml

from agent_brain_cli.runtime.types import (
    PluginAgent,
    PluginBundle,
    PluginCommand,
    PluginManifest,
    PluginParameter,
    PluginScript,
    PluginSkill,
    PluginTemplate,
    TriggerPattern,
)

logger = logging.getLogger(__name__)


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter from a markdown file.

    Expects format:
        ---
        key: value
        ---
        body content

    Args:
        text: Full file content.

    Returns:
        Tuple of (frontmatter dict, body string).

    Raises:
        ValueError: If frontmatter delimiters are missing or YAML is invalid.
    """
    text = text.strip()
    if not text.startswith("---"):
        raise ValueError("File does not start with YAML frontmatter delimiter '---'")

    # Find closing delimiter
    end_idx = text.find("---", 3)
    if end_idx == -1:
        raise ValueError("Missing closing YAML frontmatter delimiter '---'")

    yaml_text = text[3:end_idx].strip()
    body = text[end_idx + 3 :].strip()

    try:
        frontmatter = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in frontmatter: {exc}") from exc

    if not isinstance(frontmatter, dict):
        raise ValueError(
            f"Frontmatter must be a YAML mapping, got {type(frontmatter).__name__}"
        )

    return frontmatter, body


def parse_command(path: Path) -> PluginCommand:
    """Parse a command markdown file.

    Args:
        path: Path to the command .md file.

    Returns:
        Parsed PluginCommand.
    """
    text = path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)

    parameters = []
    for p in fm.get("parameters", []) or []:
        if isinstance(p, dict):
            parameters.append(
                PluginParameter(
                    name=p.get("name", ""),
                    description=p.get("description", ""),
                    required=bool(p.get("required", False)),
                    default=str(p["default"]) if "default" in p else None,
                )
            )

    return PluginCommand(
        name=fm.get("name", path.stem),
        description=fm.get("description", ""),
        parameters=parameters,
        skills=fm.get("skills", []) or [],
        body=body,
        source_path=str(path),
    )


def parse_agent(path: Path) -> PluginAgent:
    """Parse an agent markdown file.

    Args:
        path: Path to the agent .md file.

    Returns:
        Parsed PluginAgent.
    """
    text = path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)

    triggers = []
    for t in fm.get("triggers", []) or []:
        if isinstance(t, dict):
            triggers.append(
                TriggerPattern(
                    pattern=t.get("pattern", ""),
                    type=t.get("type", "keyword"),
                )
            )

    return PluginAgent(
        name=fm.get("name", path.stem),
        description=fm.get("description", ""),
        triggers=triggers,
        skills=fm.get("skills", []) or [],
        body=body,
        source_path=str(path),
        allowed_tools=fm.get("allowed_tools", fm.get("allowed-tools", [])) or [],
        color=fm.get("color", ""),
        subagent_type=fm.get("subagent_type", fm.get("subagent-type", "")),
    )


def parse_skill(path: Path) -> PluginSkill:
    """Parse a skill SKILL.md file.

    Args:
        path: Path to the SKILL.md file.

    Returns:
        Parsed PluginSkill.
    """
    text = path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)

    # Collect reference file paths relative to skill dir
    skill_dir = path.parent
    references: list[str] = []
    refs_dir = skill_dir / "references"
    if refs_dir.is_dir():
        for ref_file in sorted(refs_dir.rglob("*.md")):
            references.append(str(ref_file.relative_to(skill_dir)))

    metadata = fm.get("metadata", {}) or {}
    # Normalize metadata values to strings
    str_metadata = {str(k): str(v) for k, v in metadata.items()}

    return PluginSkill(
        name=fm.get("name", skill_dir.name),
        description=fm.get("description", ""),
        allowed_tools=fm.get("allowed-tools", []) or [],
        metadata=str_metadata,
        body=body,
        source_path=str(path),
        license=fm.get("license", ""),
        references=references,
    )


def parse_manifest(path: Path) -> PluginManifest:
    """Parse a plugin.json manifest file.

    Args:
        path: Path to plugin.json.

    Returns:
        Parsed PluginManifest.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    author = data.get("author", {})
    if isinstance(author, str):
        author_name = author
        author_email = ""
    else:
        author_name = author.get("name", "")
        author_email = author.get("email", "")

    return PluginManifest(
        name=data.get("name", ""),
        description=data.get("description", ""),
        version=data.get("version", ""),
        author_name=author_name,
        author_email=author_email,
        homepage=data.get("homepage", ""),
        repository=data.get("repository", ""),
        license=data.get("license", ""),
    )


def parse_templates(templates_dir: Path) -> list[PluginTemplate]:
    """Parse template files from the templates/ directory.

    Args:
        templates_dir: Path to the templates directory.

    Returns:
        List of parsed PluginTemplate objects.
    """
    templates: list[PluginTemplate] = []
    if not templates_dir.is_dir():
        return templates
    for tpl_file in sorted(templates_dir.iterdir()):
        if tpl_file.is_file():
            try:
                content = tpl_file.read_text(encoding="utf-8")
                templates.append(
                    PluginTemplate(
                        name=tpl_file.name,
                        content=content,
                        source_path=str(tpl_file),
                    )
                )
            except OSError as exc:
                logger.warning("Failed to read template %s: %s", tpl_file, exc)
    return templates


def parse_scripts(scripts_dir: Path) -> list[PluginScript]:
    """Parse script files from the scripts/ directory.

    Args:
        scripts_dir: Path to the scripts directory.

    Returns:
        List of parsed PluginScript objects.
    """
    scripts: list[PluginScript] = []
    if not scripts_dir.is_dir():
        return scripts
    for script_file in sorted(scripts_dir.iterdir()):
        if script_file.is_file():
            try:
                content = script_file.read_text(encoding="utf-8")
                scripts.append(
                    PluginScript(
                        name=script_file.name,
                        content=content,
                        source_path=str(script_file),
                    )
                )
            except OSError as exc:
                logger.warning("Failed to read script %s: %s", script_file, exc)
    return scripts


def parse_plugin_dir(plugin_dir: Path) -> PluginBundle:
    """Parse an entire plugin directory into a PluginBundle.

    Expects the Claude Code plugin directory layout:
        plugin_dir/
        ├── .claude-plugin/plugin.json
        ├── commands/*.md
        ├── agents/*.md
        └── skills/*/SKILL.md

    Args:
        plugin_dir: Path to the plugin root directory.

    Returns:
        Complete PluginBundle with all parsed components.

    Raises:
        FileNotFoundError: If plugin_dir doesn't exist.
    """
    if not plugin_dir.is_dir():
        raise FileNotFoundError(f"Plugin directory not found: {plugin_dir}")

    # Parse manifest
    manifest = PluginManifest()
    manifest_path = plugin_dir / ".claude-plugin" / "plugin.json"
    if manifest_path.exists():
        manifest = parse_manifest(manifest_path)

    # Parse commands
    commands: list[PluginCommand] = []
    commands_dir = plugin_dir / "commands"
    if commands_dir.is_dir():
        for cmd_file in sorted(commands_dir.glob("*.md")):
            try:
                commands.append(parse_command(cmd_file))
            except (ValueError, OSError) as exc:
                logger.warning("Failed to parse command %s: %s", cmd_file, exc)

    # Parse agents
    agents: list[PluginAgent] = []
    agents_dir = plugin_dir / "agents"
    if agents_dir.is_dir():
        for agent_file in sorted(agents_dir.glob("*.md")):
            try:
                agents.append(parse_agent(agent_file))
            except (ValueError, OSError) as exc:
                logger.warning("Failed to parse agent %s: %s", agent_file, exc)

    # Parse skills
    skills: list[PluginSkill] = []
    skills_dir = plugin_dir / "skills"
    if skills_dir.is_dir():
        for skill_dir_path in sorted(skills_dir.iterdir()):
            skill_file = skill_dir_path / "SKILL.md"
            if skill_file.exists():
                try:
                    skills.append(parse_skill(skill_file))
                except (ValueError, OSError) as exc:
                    logger.warning("Failed to parse skill %s: %s", skill_file, exc)

    # Parse templates
    templates = parse_templates(plugin_dir / "templates")

    # Parse scripts
    scripts = parse_scripts(plugin_dir / "scripts")

    return PluginBundle(
        commands=commands,
        agents=agents,
        skills=skills,
        templates=templates,
        scripts=scripts,
        manifest=manifest,
        source_dir=str(plugin_dir),
    )
