"""``agent-brain doctor`` — diagnose installation, configuration and server state."""

from __future__ import annotations

import json

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agent_brain_cli.diagnostics import (
    SEVERITY_FAIL,
    SEVERITY_OK,
    SEVERITY_WARN,
    apply_safe_fixes,
    report_to_json,
    run_doctor,
)

console = Console()


_STATUS_STYLE = {
    SEVERITY_OK: ("green", "OK"),
    SEVERITY_WARN: ("yellow", "WARN"),
    SEVERITY_FAIL: ("red", "FAIL"),
}


@click.command("doctor")
@click.option(
    "--url",
    envvar="AGENT_BRAIN_URL",
    default=None,
    help="Server URL to probe (default: resolved from runtime.json or config).",
)
@click.option("--json", "json_output", is_flag=True, help="Emit machine-readable JSON.")
@click.option(
    "--fix",
    "apply_fixes",
    is_flag=True,
    help=(
        "Apply safe, idempotent, offline fixes (add .agent-brain/ to .gitignore, "
        "create state dir + stub config.json). Will not touch API keys, network, "
        "or user code. Re-runs the report after fixing."
    ),
)
def doctor_command(url: str | None, json_output: bool, apply_fixes: bool) -> None:
    """Diagnose your Agent Brain setup.

    Inspects Python version, project init state, provider config, required
    API keys, optional dependencies, .gitignore hygiene, and whether the
    server is reachable. Exits non-zero on any critical failure so it can
    be used in scripts (``agent-brain doctor || agent-brain init``).

    Pass ``--fix`` to auto-apply the safe subset of remediations and re-run.
    """
    report = run_doctor(server_url_override=url)

    fix_actions: list[str] = []
    if apply_fixes:
        fix_actions = apply_safe_fixes(report)
        if fix_actions:
            # Re-run so the printed report reflects the fixed state.
            report = run_doctor(server_url_override=url)

    if json_output:
        payload = json.loads(report_to_json(report))
        if apply_fixes:
            payload["applied_fixes"] = fix_actions
        click.echo(json.dumps(payload, indent=2))
        raise SystemExit(report.exit_code)

    header_color = "green" if report.exit_code == 0 else "red"
    console.print(
        Panel(
            (
                f"[bold]Project root:[/] {report.project_root}\n"
                f"[bold]State dir:[/]    {report.state_dir} "
                f"({'present' if report.state_dir_exists else 'missing'})\n"
                f"[bold]Server URL:[/]   {report.server_url}"
            ),
            title="Agent Brain Doctor",
            border_style=header_color,
        )
    )

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Check", style="dim")
    table.add_column("Status")
    table.add_column("Details", overflow="fold")

    for check in report.checks:
        style, label = _STATUS_STYLE.get(check.status, ("white", check.status.upper()))
        body = check.message
        if check.fix:
            body = f"{body}\n[dim]→ {check.fix}[/]"
        table.add_row(check.name, f"[{style}]{label}[/]", body)

    console.print(table)

    if apply_fixes:
        if fix_actions:
            console.print("\n[cyan]Applied safe fixes:[/]")
            for action in fix_actions:
                console.print(f"  • {action}")
        else:
            console.print(
                "\n[dim]No safe fixes applied (nothing actionable, or all "
                "checks already passing).[/]"
            )

    if report.exit_code != 0:
        console.print(
            "\n[red]Doctor reported critical issues.[/] "
            "Fix the items above and re-run.",
        )
    else:
        console.print("\n[green]All critical checks passed.[/]")

    raise SystemExit(report.exit_code)
