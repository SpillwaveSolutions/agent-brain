"""Configuration loader for Agent Brain CLI.

Provides YAML-based configuration loading with multiple search paths,
allowing projects and users to configure Agent Brain without environment variables.
"""

import logging
import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Default state directory name within project root
STATE_DIR_NAME = ".claude/agent-brain"


class ServerConfig(BaseModel):
    """Server-related configuration."""

    url: str = Field(
        default="http://127.0.0.1:8000",
        description="Server URL for CLI to connect to",
    )
    host: str = Field(
        default="127.0.0.1",
        description="Server bind host",
    )
    port: int = Field(
        default=8000,
        description="Server port (0 = auto-assign)",
    )
    auto_port: bool = Field(
        default=True,
        description="Automatically select available port if preferred port is in use",
    )


class ProjectConfig(BaseModel):
    """Project-related configuration."""

    state_dir: str | None = Field(
        default=None,
        description="Custom state directory path (default: .claude/agent-brain)",
    )
    project_root: str | None = Field(
        default=None,
        description="Project root directory",
    )


class EmbeddingConfig(BaseModel):
    """Embedding provider configuration."""

    provider: str = Field(
        default="openai",
        description="Embedding provider: openai, ollama, cohere, gemini",
    )
    model: str = Field(
        default="text-embedding-3-large",
        description="Model name for embeddings",
    )
    api_key: str | None = Field(
        default=None,
        description="API key (alternative to api_key_env)",
    )
    api_key_env: str | None = Field(
        default="OPENAI_API_KEY",
        description="Environment variable containing API key",
    )
    base_url: str | None = Field(
        default=None,
        description="Custom base URL (for Ollama or compatible APIs)",
    )


class SummarizationConfig(BaseModel):
    """Summarization provider configuration."""

    provider: str = Field(
        default="anthropic",
        description="Provider: anthropic, openai, ollama, gemini, grok",
    )
    model: str = Field(
        default="claude-haiku-4-5-20251001",
        description="Model name for summarization",
    )
    api_key: str | None = Field(
        default=None,
        description="API key (alternative to api_key_env)",
    )
    api_key_env: str | None = Field(
        default="ANTHROPIC_API_KEY",
        description="Environment variable containing API key",
    )
    base_url: str | None = Field(
        default=None,
        description="Custom base URL",
    )


class AgentBrainConfig(BaseModel):
    """Complete Agent Brain configuration."""

    server: ServerConfig = Field(default_factory=ServerConfig)
    project: ProjectConfig = Field(default_factory=ProjectConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    summarization: SummarizationConfig = Field(default_factory=SummarizationConfig)


def _find_config_file(start_path: Path | None = None) -> Path | None:
    """Find configuration file in standard locations.

    Search order:
    1. AGENT_BRAIN_CONFIG environment variable
    2. Current directory: agent-brain.yaml or config.yaml
    3. Project .claude/agent-brain/config.yaml
    4. User home: ~/.agent-brain/config.yaml
    5. User home: ~/.config/agent-brain/config.yaml (XDG)

    Args:
        start_path: Starting directory for project search. Defaults to cwd.

    Returns:
        Path to config file or None if not found.
    """
    # 1. Environment variable override
    env_config = os.getenv("AGENT_BRAIN_CONFIG")
    if env_config:
        path = Path(env_config).expanduser()
        if path.exists():
            logger.debug(f"Using config from AGENT_BRAIN_CONFIG: {path}")
            return path
        logger.warning(f"AGENT_BRAIN_CONFIG points to non-existent file: {env_config}")

    start = (start_path or Path.cwd()).resolve()

    # 2. Current directory
    for name in ("agent-brain.yaml", "agent-brain.yml", "config.yaml"):
        cwd_config = start / name
        if cwd_config.exists():
            logger.debug(f"Using config from current directory: {cwd_config}")
            return cwd_config

    # 3. Project .claude/agent-brain directory
    # Walk up looking for .claude directory
    current = start
    while current != current.parent:
        claude_config = current / ".claude" / "agent-brain" / "config.yaml"
        if claude_config.exists():
            logger.debug(f"Using config from project: {claude_config}")
            return claude_config
        current = current.parent

    # 4. User home ~/.agent-brain/
    home = Path.home()
    home_config = home / ".agent-brain" / "config.yaml"
    if home_config.exists():
        logger.debug(f"Using config from home: {home_config}")
        return home_config

    # 5. XDG config
    xdg_config = home / ".config" / "agent-brain" / "config.yaml"
    if xdg_config.exists():
        logger.debug(f"Using config from XDG: {xdg_config}")
        return xdg_config

    return None


def _load_yaml_config(path: Path) -> dict[str, Any]:
    """Load YAML configuration from file.

    Args:
        path: Path to YAML config file.

    Returns:
        Configuration dictionary.

    Raises:
        ValueError: If YAML parsing fails.
    """
    try:
        with open(path) as f:
            config = yaml.safe_load(f)
            return config if config else {}
    except yaml.YAMLError as e:
        raise ValueError(f"Failed to parse config file {path}: {e}") from e
    except OSError as e:
        raise ValueError(f"Failed to read config file {path}: {e}") from e


def load_config(start_path: Path | None = None) -> AgentBrainConfig:
    """Load Agent Brain configuration.

    Searches for config file in standard locations and returns
    validated configuration. Falls back to defaults if no config found.

    Args:
        start_path: Starting directory for config search.

    Returns:
        Validated AgentBrainConfig instance.
    """
    config_path = _find_config_file(start_path)

    if config_path:
        logger.info(f"Loading config from {config_path}")
        raw_config = _load_yaml_config(config_path)
        config = AgentBrainConfig(**raw_config)
    else:
        logger.debug("No config file found, using defaults")
        config = AgentBrainConfig()

    # Override with environment variables (highest precedence)
    if os.getenv("AGENT_BRAIN_URL"):
        config.server.url = os.getenv("AGENT_BRAIN_URL")  # type: ignore[assignment]
    if os.getenv("AGENT_BRAIN_STATE_DIR"):
        config.project.state_dir = os.getenv("AGENT_BRAIN_STATE_DIR")

    return config


def _find_project_root(start_path: Path | None = None) -> Path:
    """Find the project root by looking for markers.

    Walks up from start_path looking for:
    1. Git repository root
    2. .claude/ directory
    3. pyproject.toml file

    Args:
        start_path: Starting directory. Defaults to cwd.

    Returns:
        Project root path or start_path if no markers found.
    """
    import subprocess

    start = (start_path or Path.cwd()).resolve()

    # Try git root first
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(start),
        )
        if result.returncode == 0:
            return Path(result.stdout.strip()).resolve()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    # Walk up looking for markers
    current = start
    while current != current.parent:
        if (current / ".claude").is_dir():
            return current
        if (current / "pyproject.toml").is_file():
            return current
        current = current.parent

    return start


def get_state_dir(
    config: AgentBrainConfig | None = None,
    project_root: Path | None = None,
) -> Path:
    """Get the resolved state directory path.

    Resolution order:
    1. Detect project root and check for .claude/agent-brain/
    2. config.project.state_dir from config file
    3. AGENT_BRAIN_STATE_DIR environment variable (explicit override)
    4. Default: {project_root}/.claude/agent-brain

    Args:
        config: Optional pre-loaded config.
        project_root: Project root for default path.

    Returns:
        Resolved state directory path.
    """
    # 1. Auto-detect project root and check for existing state dir
    if project_root is None:
        project_root = _find_project_root()

    detected_state_dir = project_root / STATE_DIR_NAME
    if detected_state_dir.exists() and (detected_state_dir / "config.json").exists():
        return detected_state_dir

    # 2. Check config file setting
    if config is None:
        config = load_config()

    if config.project.state_dir:
        return Path(config.project.state_dir).expanduser().resolve()

    # 3. Environment variable as explicit override
    env_state_dir = os.getenv("AGENT_BRAIN_STATE_DIR")
    if env_state_dir:
        return Path(env_state_dir).expanduser().resolve()

    # 4. Default: project_root/.claude/agent-brain
    return project_root / STATE_DIR_NAME


def get_server_url(config: AgentBrainConfig | None = None) -> str:
    """Get the server URL.

    Resolution order:
    1. AGENT_BRAIN_URL environment variable
    2. runtime.json base_url (if server is running for current project)
    3. config.server.url from config file
    4. Default: http://127.0.0.1:8000

    Args:
        config: Optional pre-loaded config.

    Returns:
        Server URL string.
    """
    import json

    # Environment variable takes precedence
    env_url = os.getenv("AGENT_BRAIN_URL")
    if env_url:
        return env_url

    # Check runtime.json for running server
    state_dir = get_state_dir()
    runtime_file = state_dir / "runtime.json"
    if runtime_file.exists():
        try:
            with open(runtime_file) as f:
                runtime = json.load(f)
                if "base_url" in runtime:
                    return str(runtime["base_url"])
        except (json.JSONDecodeError, OSError):
            pass  # Fall through to config

    # Load config if not provided
    if config is None:
        config = load_config()

    return config.server.url
