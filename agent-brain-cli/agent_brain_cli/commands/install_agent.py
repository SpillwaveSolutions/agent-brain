"""Install-agent command for installing runtime-specific plugin files."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.panel import Panel

from agent_brain_cli.runtime.claude_converter import ClaudeConverter
from agent_brain_cli.runtime.codex_converter import CodexConverter
from agent_brain_cli.runtime.gemini_converter import GeminiConverter
from agent_brain_cli.runtime.mcp_registration import (
    McpRegistrationResult,
    register_claude_mcp,
    register_opencode_mcp,
)
from agent_brain_cli.runtime.opencode_converter import OpenCodeConverter
from agent_brain_cli.runtime.parser import parse_plugin_dir
from agent_brain_cli.runtime.skill_runtime_converter import SkillRuntimeConverter
from agent_brain_cli.runtime.types import Scope

console = Console()

# Default install directories per runtime and scope
INSTALL_DIRS: dict[str, dict[str, str]] = {
    "claude": {
        "project": ".claude/plugins/agent-brain",
        "global": "~/.claude/plugins/agent-brain",
    },
    "opencode": {
        "project": ".opencode/plugins/agent-brain",
        "global": "~/.config/opencode/plugins/agent-brain",
    },
    "gemini": {
        "project": ".gemini/plugins/agent-brain",
        "global": "~/.config/gemini/plugins/agent-brain",
    },
    "codex": {
        "project": ".codex/skills/agent-brain",
        "global": "~/.codex/skills/agent-brain",
    },
}

# Runtimes that require --dir (no default directory)
DIR_REQUIRED_RUNTIMES = {"skill-runtime"}

ConverterType = type[
    ClaudeConverter
    | OpenCodeConverter
    | GeminiConverter
    | SkillRuntimeConverter
    | CodexConverter
]

CONVERTERS: dict[str, ConverterType] = {
    "claude": ClaudeConverter,
    "opencode": OpenCodeConverter,
    "gemini": GeminiConverter,
    "skill-runtime": SkillRuntimeConverter,
    "codex": CodexConverter,
}


def _find_plugin_dir() -> Path | None:
    """Find the canonical plugin directory.

    Searches for agent-brain-plugin in common locations.
    """
    # Check relative to this package (development layout)
    pkg_dir = Path(__file__).parent.parent.parent.parent
    candidate = pkg_dir / "agent-brain-plugin"
    if candidate.is_dir() and (candidate / "commands").is_dir():
        return candidate

    # Check installed location
    installed = Path.home() / ".claude" / "plugins" / "agent-brain"
    if installed.is_dir() and (installed / "commands").is_dir():
        return installed

    return None


def _resolve_target_dir(
    runtime: str,
    scope: str,
    project_root: Path | None = None,
    custom_dir: str | None = None,
) -> Path:
    """Resolve the target installation directory."""
    if custom_dir:
        return Path(custom_dir).expanduser().resolve()
    dir_template = INSTALL_DIRS[runtime][scope]
    if scope == "global":
        return Path(dir_template).expanduser()
    if project_root is None:
        project_root = Path.cwd()
    return project_root / dir_template


RUNTIME_CHOICES = ["claude", "opencode", "gemini", "skill-runtime", "codex"]

# Runtimes for which we can auto-register the MCP server today, mapped to the
# writer that knows that runtime's config schema. All writers share the
# ``(config_path, state_dir, *, backend, auth, dry_run)`` signature.
MCP_REGISTRARS: dict[str, Callable[..., McpRegistrationResult]] = {
    "claude": register_claude_mcp,
    "opencode": register_opencode_mcp,
}


def _resolve_mcp_paths(
    agent: str, scope: str, project_root: Path | None
) -> tuple[Path, Path]:
    """Return (config_path, state_dir) for MCP registration.

    The config file follows each runtime's own discovery rules:

    * **claude** — project ``.mcp.json`` at the root, global ``~/.claude.json``.
    * **opencode** — project ``opencode.json`` at the root (highest-precedence
      project config), global ``~/.config/opencode/opencode.json``.
    """
    root = project_root if project_root is not None else Path.cwd()
    if agent == "opencode":
        if scope == "global":
            config = Path.home() / ".config" / "opencode" / "opencode.json"
            return config, Path.home() / ".agent-brain"
        return root / "opencode.json", root / ".agent-brain"
    # claude (and any future mcpServers-style runtime)
    if scope == "global":
        return Path.home() / ".claude.json", Path.home() / ".agent-brain"
    return root / ".mcp.json", root / ".agent-brain"


def _register_mcp(
    agent: str,
    scope: str,
    project_root: Path | None,
    mcp_auth: str,
    mcp_backend: str,
    dry_run: bool,
) -> dict[str, Any]:
    """Register the MCP server for supported runtimes; report what happened."""
    registrar = MCP_REGISTRARS.get(agent)
    if registrar is None:
        return {
            "skipped": True,
            "reason": (
                f"MCP auto-registration is currently supported only for "
                f"{', '.join(sorted(MCP_REGISTRARS))}; configure "
                f"{agent} manually (see the configuring-agent-brain skill)."
            ),
        }
    config_path, state_dir = _resolve_mcp_paths(agent, scope, project_root)
    result = registrar(
        config_path,
        state_dir,
        backend=mcp_backend,
        auth=mcp_auth,
        dry_run=dry_run,
    )
    return {
        "skipped": False,
        "action": result.action,
        "path": str(result.path),
        "server_name": result.server_name,
    }


@click.command("install-agent")
@click.option(
    "--agent",
    "-a",
    required=True,
    type=click.Choice(RUNTIME_CHOICES),
    help="Target runtime to install for",
)
@click.option(
    "--project",
    "scope",
    flag_value="project",
    default=True,
    help="Install to project directory (default)",
)
@click.option(
    "--global",
    "scope",
    flag_value="global",
    help="Install to user-level directory",
)
@click.option(
    "--plugin-dir",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    help="Custom canonical plugin source directory",
)
@click.option(
    "--dir",
    "target_dir_option",
    type=click.Path(resolve_path=True),
    help="Target skill directory (required for skill-runtime)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="List files that would be created without writing",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output as JSON",
)
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    help="Project path for --project scope (default: cwd)",
)
@click.option(
    "--with-mcp",
    is_flag=True,
    help="Also register the agent-brain MCP server (Claude Code or OpenCode)",
)
@click.option(
    "--mcp-auth",
    type=click.Choice(["none", "oauth"]),
    default="none",
    help="MCP client auth mode written into the registration (default: none)",
)
@click.option(
    "--mcp-backend",
    type=click.Choice(["auto", "uds", "http"]),
    default="auto",
    help="How the MCP server reaches agent-brain-serve (default: auto)",
)
def install_agent_command(
    agent: str,
    scope: str,
    plugin_dir: str | None,
    target_dir_option: str | None,
    dry_run: bool,
    json_output: bool,
    path: str | None,
    with_mcp: bool,
    mcp_auth: str,
    mcp_backend: str,
) -> None:
    """Install Agent Brain plugin for a specific runtime.

    Converts the canonical plugin format into the target runtime's
    native format and installs it.

    \b
    Examples:
      agent-brain install-agent --agent claude --project
      agent-brain install-agent --agent opencode --global
      agent-brain install-agent --agent gemini --dry-run
      agent-brain install-agent --agent skill-runtime --dir ./my-skills
      agent-brain install-agent --agent codex
    """
    try:
        # Validate --dir requirement for skill-runtime
        if agent in DIR_REQUIRED_RUNTIMES and not target_dir_option:
            msg = (
                f"--dir is required for --agent {agent}. "
                "Specify the target skill directory."
            )
            if json_output:
                click.echo(json.dumps({"error": msg}))
            else:
                console.print(f"[red]Error:[/] {msg}")
            raise SystemExit(1)

        # Resolve plugin source directory
        source: Path
        if plugin_dir:
            source = Path(plugin_dir)
        else:
            found = _find_plugin_dir()
            if found is None:
                msg = (
                    "Could not find canonical plugin directory. "
                    "Use --plugin-dir to specify location."
                )
                if json_output:
                    click.echo(json.dumps({"error": msg}))
                else:
                    console.print(f"[red]Error:[/] {msg}")
                raise SystemExit(1)
            source = found

        # Parse the plugin
        bundle = parse_plugin_dir(source)

        if not json_output and not dry_run:
            console.print(
                f"[dim]Parsed {len(bundle.commands)} commands, "
                f"{len(bundle.agents)} agents, "
                f"{len(bundle.skills)} skills, "
                f"{len(bundle.templates)} templates, "
                f"{len(bundle.scripts)} scripts[/]"
            )

        # Resolve target directory
        project_root = Path(path) if path else None
        target = _resolve_target_dir(agent, scope, project_root, target_dir_option)

        # Create converter
        converter_cls = CONVERTERS[agent]
        converter = converter_cls()
        scope_enum = Scope.GLOBAL if scope == "global" else Scope.PROJECT

        mcp_summary: dict[str, Any] | None = None
        if with_mcp:
            mcp_summary = _register_mcp(
                agent, scope, project_root, mcp_auth, mcp_backend, dry_run
            )

        if dry_run:
            _handle_dry_run(
                converter,
                bundle,
                target,
                scope_enum,
                agent,
                scope,
                json_output,
                mcp_summary,
            )
            return

        # Actually install
        if isinstance(converter, CodexConverter):
            codex_root = Path(path) if path else Path.cwd()
            files = converter.install(
                bundle, target, scope_enum, project_root=codex_root
            )
        else:
            files = converter.install(bundle, target, scope_enum)

        if json_output:
            result: dict[str, Any] = {
                "status": "installed",
                "agent": agent,
                "scope": scope,
                "target_dir": str(target),
                "files_created": len(files),
                "source_dir": str(source),
            }
            if mcp_summary is not None:
                result["mcp_registration"] = mcp_summary
            click.echo(json.dumps(result, indent=2))
        else:
            console.print(
                Panel(
                    f"[green]Plugin installed successfully![/]\n\n"
                    f"[bold]Runtime:[/] {agent}\n"
                    f"[bold]Scope:[/] {scope}\n"
                    f"[bold]Target:[/] {target}\n"
                    f"[bold]Files:[/] {len(files)}",
                    title="Agent Brain Installed",
                    border_style="green",
                )
            )
            _print_mcp_summary(mcp_summary)

    except SystemExit:
        raise
    except Exception as exc:
        if json_output:
            click.echo(json.dumps({"error": str(exc)}))
        else:
            console.print(f"[red]Error:[/] {exc}")
        raise SystemExit(1) from exc


def _handle_dry_run(
    converter: (
        ClaudeConverter
        | OpenCodeConverter
        | GeminiConverter
        | SkillRuntimeConverter
        | CodexConverter
    ),
    bundle: Any,
    target: Path,
    scope_enum: Scope,
    agent: str,
    scope: str,
    json_output: bool,
    mcp_summary: dict[str, Any] | None = None,
) -> None:
    """Handle dry-run mode: simulate install in temp dir."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        tmp_target = Path(tmp)
        # For Codex, pass tmp as project_root so AGENTS.md lands in tmpdir
        if isinstance(converter, CodexConverter):
            files = converter.install(
                bundle, tmp_target, scope_enum, project_root=Path(tmp)
            )
        else:
            files = converter.install(bundle, tmp_target, scope_enum)
        # Remap paths to real target
        planned: list[Path] = []
        for f in files:
            try:
                planned.append(target / f.relative_to(tmp_target))
            except ValueError:
                # AGENTS.md may be at project_root, not under target
                planned.append(f)

    if json_output:
        payload: dict[str, Any] = {
            "dry_run": True,
            "agent": agent,
            "scope": scope,
            "target_dir": str(target),
            "files": [str(f) for f in planned],
            "file_count": len(planned),
        }
        if mcp_summary is not None:
            payload["mcp_registration"] = mcp_summary
        click.echo(json.dumps(payload, indent=2))
    else:
        console.print(
            Panel(
                f"[yellow]Dry run[/] — no files written\n\n"
                f"[bold]Runtime:[/] {agent}\n"
                f"[bold]Scope:[/] {scope}\n"
                f"[bold]Target:[/] {target}\n"
                f"[bold]Files:[/] {len(planned)}",
                title="Install Preview",
                border_style="yellow",
            )
        )
        for f in planned:
            console.print(f"  [dim]{f}[/]")
        _print_mcp_summary(mcp_summary)


def _print_mcp_summary(mcp_summary: dict[str, Any] | None) -> None:
    """Render the MCP registration outcome for human-readable output."""
    if mcp_summary is None:
        return
    if mcp_summary.get("skipped"):
        console.print(f"[yellow]MCP:[/] {mcp_summary['reason']}")
        return
    console.print(
        f"[green]MCP server registered[/] ([bold]{mcp_summary['action']}[/]) "
        f"→ {mcp_summary['path']}"
    )
