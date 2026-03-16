"""Install-agent command for installing runtime-specific plugin files."""

import json
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.panel import Panel

from agent_brain_cli.runtime.claude_converter import ClaudeConverter
from agent_brain_cli.runtime.codex_converter import CodexConverter
from agent_brain_cli.runtime.gemini_converter import GeminiConverter
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


class _SkillRuntimeChoice(click.Choice):
    """Extended choice that includes skill-runtime and codex."""

    def __init__(self) -> None:
        super().__init__(
            ["claude", "opencode", "gemini", "skill-runtime", "codex"]
        )


@click.command("install-agent")
@click.option(
    "--agent",
    "-a",
    required=True,
    type=_SkillRuntimeChoice(),
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
def install_agent_command(
    agent: str,
    scope: str,
    plugin_dir: str | None,
    target_dir_option: str | None,
    dry_run: bool,
    json_output: bool,
    path: str | None,
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
        target = _resolve_target_dir(
            agent, scope, project_root, target_dir_option
        )

        # Create converter
        converter_cls = CONVERTERS[agent]
        converter = converter_cls()
        scope_enum = Scope.GLOBAL if scope == "global" else Scope.PROJECT

        if dry_run:
            _handle_dry_run(
                converter, bundle, target, scope_enum, agent, scope,
                json_output,
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

    except SystemExit:
        raise
    except Exception as exc:
        if json_output:
            click.echo(json.dumps({"error": str(exc)}))
        else:
            console.print(f"[red]Error:[/] {exc}")
        raise SystemExit(1) from exc


def _handle_dry_run(
    converter: ClaudeConverter
    | OpenCodeConverter
    | GeminiConverter
    | SkillRuntimeConverter
    | CodexConverter,
    bundle: Any,
    target: Path,
    scope_enum: Scope,
    agent: str,
    scope: str,
    json_output: bool,
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
        click.echo(
            json.dumps(
                {
                    "dry_run": True,
                    "agent": agent,
                    "scope": scope,
                    "target_dir": str(target),
                    "files": [str(f) for f in planned],
                    "file_count": len(planned),
                },
                indent=2,
            )
        )
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
