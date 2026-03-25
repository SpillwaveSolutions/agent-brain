"""Data models for the plugin parser and runtime converter system."""

from dataclasses import dataclass, field
from enum import Enum


class RuntimeType(str, Enum):
    """Supported AI runtime environments."""

    CLAUDE = "claude"
    OPENCODE = "opencode"
    GEMINI = "gemini"
    SKILL_RUNTIME = "skill-runtime"
    CODEX = "codex"


class Scope(str, Enum):
    """Installation scope."""

    PROJECT = "project"
    GLOBAL = "global"


@dataclass
class PluginParameter:
    """A command parameter definition."""

    name: str
    description: str
    required: bool = False
    default: str | None = None


@dataclass
class TriggerPattern:
    """An agent trigger pattern."""

    pattern: str
    type: str  # "message_pattern", "keyword", "error_pattern"


@dataclass
class PluginCommand:
    """Parsed representation of a plugin command file."""

    name: str
    description: str
    parameters: list[PluginParameter] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    body: str = ""
    source_path: str = ""


@dataclass
class PluginAgent:
    """Parsed representation of a plugin agent file."""

    name: str
    description: str
    triggers: list[TriggerPattern] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    body: str = ""
    source_path: str = ""
    allowed_tools: list[str] = field(default_factory=list)
    color: str = ""
    subagent_type: str = ""


@dataclass
class PluginSkill:
    """Parsed representation of a plugin skill file."""

    name: str
    description: str
    allowed_tools: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
    body: str = ""
    source_path: str = ""
    license: str = ""
    references: list[str] = field(default_factory=list)


@dataclass
class PluginTemplate:
    """A template file from the plugin templates/ directory."""

    name: str
    content: str
    source_path: str = ""


@dataclass
class PluginScript:
    """A script file from the plugin scripts/ directory."""

    name: str
    content: str
    source_path: str = ""


@dataclass
class PluginManifest:
    """Parsed plugin.json manifest."""

    name: str = ""
    description: str = ""
    version: str = ""
    author_name: str = ""
    author_email: str = ""
    homepage: str = ""
    repository: str = ""
    license: str = ""


@dataclass
class PluginBundle:
    """Complete parsed representation of a plugin directory."""

    commands: list[PluginCommand] = field(default_factory=list)
    agents: list[PluginAgent] = field(default_factory=list)
    skills: list[PluginSkill] = field(default_factory=list)
    templates: list[PluginTemplate] = field(default_factory=list)
    scripts: list[PluginScript] = field(default_factory=list)
    manifest: PluginManifest = field(default_factory=PluginManifest)
    source_dir: str = ""
