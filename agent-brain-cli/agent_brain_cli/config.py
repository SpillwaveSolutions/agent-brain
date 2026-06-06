"""Configuration loader for Agent Brain CLI.

Provides YAML-based configuration loading with multiple search paths,
allowing projects and users to configure Agent Brain without environment variables.
"""

import logging
import os
import sys
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

from agent_brain_cli.xdg_paths import get_xdg_config_dir

logger = logging.getLogger(__name__)

# Default state directory name within project root
STATE_DIR_NAME = ".agent-brain"
LEGACY_STATE_DIR_NAME = ".claude/agent-brain"


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
        description="Custom state directory path (default: .agent-brain)",
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
    3. Project .agent-brain/config.yaml (or legacy .claude/agent-brain/)
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

    # 3. Project .agent-brain directory (or legacy .claude/agent-brain)
    # Walk up looking for state directory
    current = start
    while current != current.parent:
        new_config = current / ".agent-brain" / "config.yaml"
        if new_config.exists():
            logger.debug(f"Using config from project: {new_config}")
            return new_config
        legacy_config = current / ".claude" / "agent-brain" / "config.yaml"
        if legacy_config.exists():
            logger.debug(f"Using config from project: {legacy_config}")
            return legacy_config
        current = current.parent

    # 4. XDG config (checked before legacy per XDG standard)
    xdg_config_path = get_xdg_config_dir() / "config.yaml"
    if xdg_config_path.exists():
        logger.debug(f"Using config from XDG: {xdg_config_path}")
        return xdg_config_path

    # Also check agent-brain.yaml in XDG dir
    xdg_alt = get_xdg_config_dir() / "agent-brain.yaml"
    if xdg_alt.exists():
        logger.debug(f"Using config from XDG: {xdg_alt}")
        return xdg_alt

    # 5. Legacy path ~/.agent-brain/ (deprecated, fallback only)
    home = Path.home()
    home_config = home / ".agent-brain" / "config.yaml"
    if home_config.exists():
        logger.debug(f"Using config from legacy home: {home_config}")
        sys.stderr.write(
            "Warning: Using legacy config path ~/.agent-brain/config.yaml. "
            "Run 'agent-brain start' to migrate to ~/.config/agent-brain/.\n"
        )
        return home_config

    home_alt = home / ".agent-brain" / "agent-brain.yaml"
    if home_alt.exists():
        logger.debug(f"Using config from legacy home: {home_alt}")
        sys.stderr.write(
            "Warning: Using legacy config path ~/.agent-brain/agent-brain.yaml. "
            "Run 'agent-brain start' to migrate to ~/.config/agent-brain/.\n"
        )
        return home_alt

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


def resolve_project_root(start_path: Path | None = None) -> Path:
    """Find the project root by looking for markers.

    Thin wrapper around :func:`resolve_project_root_with_strategy` that drops
    the strategy label for callers that only need the path.
    """
    return resolve_project_root_with_strategy(start_path)[0]


def resolve_project_root_with_strategy(
    start_path: Path | None = None,
) -> tuple[Path, str]:
    """Find the project root and report *which* rule matched.

    Used by ``agent-brain doctor`` to explain why a given directory was
    selected (issue #146).

    Resolution order (first match wins):
    1. Walk up from ``start_path`` looking for ``.agent-brain/`` — this lets a
       sub-project inside a mono-repo keep its own state dir and not get
       pulled to the git top-level (issues #124, #128).
    2. Walk up looking for legacy ``.claude/agent-brain/``.
    3. Git repository root (``git rev-parse --show-toplevel``).
    4. Walk up looking for ``.claude/`` or ``pyproject.toml``.
    5. Fall back to ``start_path``.

    Returns:
        ``(root, strategy)`` where ``strategy`` is one of
        ``"agent_brain_dir"``, ``"legacy_claude_dir"``, ``"git_root"``,
        ``"claude_dir"``, ``"pyproject"``, ``"cwd_fallback"``.
    """
    import subprocess

    start = (start_path or Path.cwd()).resolve()

    # 1 & 2. Prefer a local state dir over git root so nested projects work.
    current = start
    while current != current.parent:
        if (current / STATE_DIR_NAME).is_dir():
            return current, "agent_brain_dir"
        if (current / LEGACY_STATE_DIR_NAME).is_dir():
            return current, "legacy_claude_dir"
        current = current.parent

    # 3. Git root next — useful when this is the first time the user runs init.
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(start),
        )
        if result.returncode == 0:
            return Path(result.stdout.strip()).resolve(), "git_root"
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    # 4. Other markers.
    current = start
    while current != current.parent:
        if (current / ".claude").is_dir():
            return current, "claude_dir"
        if (current / "pyproject.toml").is_file():
            return current, "pyproject"
        current = current.parent

    return start, "cwd_fallback"


# Backwards-compatible alias for any external callers.
_find_project_root = resolve_project_root


def get_state_dir(
    config: AgentBrainConfig | None = None,
    project_root: Path | None = None,
) -> Path:
    """Get the resolved state directory path.

    Resolution order:
    1. Detect project root and check for .agent-brain/ (or legacy .claude/agent-brain/)
    2. config.project.state_dir from config file
    3. AGENT_BRAIN_STATE_DIR environment variable (explicit override)
    4. Default: {project_root}/.agent-brain

    Args:
        config: Optional pre-loaded config.
        project_root: Project root for default path.

    Returns:
        Resolved state directory path.
    """
    # 1. Auto-detect project root and check for existing state dir
    if project_root is None:
        project_root = resolve_project_root()

    # Check new path first, then legacy
    new_state_dir = project_root / STATE_DIR_NAME
    if new_state_dir.exists() and (new_state_dir / "config.json").exists():
        return new_state_dir

    legacy_state_dir = project_root / LEGACY_STATE_DIR_NAME
    if legacy_state_dir.exists() and (legacy_state_dir / "config.json").exists():
        return legacy_state_dir

    # 2. Check config file setting
    if config is None:
        config = load_config()

    if config.project.state_dir:
        return Path(config.project.state_dir).expanduser().resolve()

    # 3. Environment variable as explicit override
    env_state_dir = os.getenv("AGENT_BRAIN_STATE_DIR")
    if env_state_dir:
        return Path(env_state_dir).expanduser().resolve()

    # 4. Default: project_root/.agent-brain
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


def resolve_api_key(state_dir: Path | None = None) -> str | None:
    """Resolve the X-API-Key value the CLI should send (Issue #179).

    Precedence (first non-empty wins):
      1. ``AGENT_BRAIN_API_KEY`` environment variable
      2. ``runtime.json::api_key`` for the resolved state directory
         (set by the running server)
      3. ``config.json::api_key`` for the resolved state directory
         (set by ``agent-brain init``, used when the server hasn't
         started yet)

    Returns ``None`` when no source provides a value, which is the
    correct behavior for a server running in default no-auth loopback
    mode — the client sends no header and the server's no-op dependency
    accepts the request.

    Args:
        state_dir: Optional state directory to read from. Defaults to
            ``get_state_dir()`` so callers in CLI commands don't need
            to thread the path through.

    Returns:
        The resolved API key or ``None``.
    """
    import json

    env_key = os.getenv("AGENT_BRAIN_API_KEY")
    if env_key:
        return env_key

    if state_dir is None:
        try:
            state_dir = get_state_dir()
        except Exception:
            return None

    for filename in ("runtime.json", "config.json"):
        candidate = state_dir / filename
        if not candidate.exists():
            continue
        try:
            with open(candidate) as f:
                payload = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        api_key = payload.get("api_key")
        if api_key:
            return str(api_key)

    return None


def resolve_transport(
    *,
    transport_hint: str | None = None,
    base_url_override: str | None = None,
    socket_path_override: Path | None = None,
    config: AgentBrainConfig | None = None,
) -> tuple[Literal["http", "uds"], str]:
    """Resolve the active transport and its connection target.

    Sibling to :func:`get_server_url` — shares the same precedence chain
    for HTTP, layers UDS detection on top. See plan §4.4 and §12.3 #6.

    Precedence:
      1. ``transport_hint`` argument (from CLI ``--transport`` flag)
      2. ``AGENT_BRAIN_TRANSPORT`` environment variable
      3. ``"auto"`` (try UDS first, fall back to HTTP)

    For ``"uds"``: uses ``socket_path_override`` → ``AGENT_BRAIN_UDS_PATH``
    env → ``agent_brain_uds.resolve_socket_path``. Validates with
    :func:`agent_brain_uds.validate_socket` and raises on failure (so
    an explicit ``--transport uds`` without a valid socket exits loudly,
    per plan §12.3 #7).

    For ``"http"``: uses ``base_url_override`` → :func:`get_server_url`.

    For ``"auto"``: tries UDS; on any validation failure, falls back to
    HTTP transparently.

    Returns:
        A ``(transport, target)`` tuple where ``transport`` is
        ``"http"`` or ``"uds"`` and ``target`` is the URL or socket path
        (as a string).
    """
    chosen = (
        transport_hint or os.environ.get("AGENT_BRAIN_TRANSPORT") or "auto"
    ).lower()

    def _resolve_uds_target() -> str:
        from agent_brain_uds import resolve_socket_path, validate_socket

        if socket_path_override is not None:
            path = Path(socket_path_override).expanduser()
        elif env_path := os.environ.get("AGENT_BRAIN_UDS_PATH"):
            path = Path(env_path).expanduser()
        else:
            path = resolve_socket_path(None)
        validate_socket(path)
        return str(path)

    def _resolve_http_target() -> str:
        if base_url_override:
            return base_url_override
        return get_server_url(config)

    if chosen == "uds":
        return ("uds", _resolve_uds_target())
    if chosen == "http":
        return ("http", _resolve_http_target())

    # "auto" — try UDS, fall back to HTTP on any validation failure.
    try:
        from agent_brain_uds import AgentBrainUdsError

        try:
            return ("uds", _resolve_uds_target())
        except (AgentBrainUdsError, OSError, FileNotFoundError):
            return ("http", _resolve_http_target())
    except ImportError:
        # agent_brain_uds not installed — HTTP is the only option.
        return ("http", _resolve_http_target())


def resolve_mcp_transport(
    *,
    mcp_transport_hint: str | None = None,
    mcp_url_override: str | None = None,
) -> tuple[Literal["stdio", "http"], str | None]:
    """Resolve the MCP-axis transport when ``--transport mcp`` is active.

    Sibling to :func:`resolve_transport` — that helper handles the
    HTTP/UDS axis (the v1/v2 ``cli_listen_transport``); this helper
    handles the MCP axis (the v3 ``cli_backend_transport``, per design
    doc §2.1).

    Precedence (per Phase 57 CONTEXT §decisions / design doc §3.5):

      1. ``mcp_transport_hint`` argument (CLI ``--mcp-transport`` flag)
      2. ``AGENT_BRAIN_MCP_TRANSPORT`` environment variable
      3. Default: ``"stdio"``

    URL precedence for ``http``:

      1. ``mcp_url_override`` argument (CLI ``--mcp-url`` flag)
      2. ``AGENT_BRAIN_MCP_URL`` environment variable
      3. Hard error — ``mcp.runtime.json`` discovery lands in Phase 58.

    Returns:
        A ``(transport, target)`` tuple. ``transport`` is ``"stdio"``
        or ``"http"``. ``target`` is the MCP URL for ``http``, or
        ``None`` for ``stdio`` (stdio backends spawn a subprocess, not
        a URL connection).

    Raises:
        click.UsageError: When ``http`` is selected but no URL is
            resolvable. Exits the CLI with code 2 per the v10.2
            HTTP-03 no-silent-fallback contract.
    """
    chosen = (
        mcp_transport_hint or os.environ.get("AGENT_BRAIN_MCP_TRANSPORT") or "stdio"
    ).lower()
    if chosen == "stdio":
        return ("stdio", None)
    if chosen == "http":
        url = mcp_url_override or os.environ.get("AGENT_BRAIN_MCP_URL")
        if not url:
            # Late `import click as _click` keeps config.py free of a
            # top-level Click dependency (today config.py imports only
            # yaml + pydantic). The error surfaces with Click's
            # standard exit code 2 — v10.2 HTTP-03 carry-forward.
            import click as _click

            raise _click.UsageError(
                "discovery file support lands in Phase 58; "
                "pass --mcp-url explicitly in Phase 57"
            )
        return ("http", url)
    # Unknown value — Click.Choice on the flag already filters this at
    # parse time, but defend against the env-only path.
    import click as _click

    raise _click.UsageError(
        f"AGENT_BRAIN_MCP_TRANSPORT={chosen!r} is not a known MCP "
        "transport; expected 'stdio' or 'http'"
    )
