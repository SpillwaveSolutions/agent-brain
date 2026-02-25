"""Types command group for listing file type presets.

File type presets are named groups of glob patterns used with --include-type
during indexing.  These definitions must stay in sync with
`agent_brain_server/services/file_type_presets.py`.
"""

import json

import click
from rich.console import Console
from rich.table import Table

console = Console()

# Hardcoded preset definitions matching
# agent_brain_server/services/file_type_presets.py.
# Update both files if presets change.
FILE_TYPE_PRESETS: dict[str, list[str]] = {
    "python": ["*.py", "*.pyi", "*.pyw"],
    "javascript": ["*.js", "*.jsx", "*.mjs", "*.cjs"],
    "typescript": ["*.ts", "*.tsx"],
    "go": ["*.go"],
    "rust": ["*.rs"],
    "java": ["*.java"],
    "csharp": ["*.cs"],
    "c": ["*.c", "*.h"],
    "cpp": ["*.cpp", "*.hpp", "*.cc", "*.hh"],
    "web": ["*.html", "*.css", "*.scss", "*.jsx", "*.tsx"],
    "docs": ["*.md", "*.txt", "*.rst", "*.pdf"],
    "text": ["*.md", "*.txt", "*.rst"],
    "pdf": ["*.pdf"],
    "code": [
        "*.py",
        "*.pyi",
        "*.pyw",
        "*.js",
        "*.jsx",
        "*.mjs",
        "*.cjs",
        "*.ts",
        "*.tsx",
        "*.go",
        "*.rs",
        "*.java",
        "*.cs",
        "*.c",
        "*.h",
        "*.cpp",
        "*.hpp",
        "*.cc",
        "*.hh",
    ],
}


@click.group("types")
def types_group() -> None:
    """File type presets for indexing.

    \b
    Examples:
      agent-brain types list              # Show all presets
      agent-brain types list --json       # JSON output
    """
    pass


@types_group.command("list")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def list_types_cmd(json_output: bool) -> None:
    """List available file type presets and their extensions.

    Presets can be used with the --include-type flag when indexing:

    \b
    Examples:
      agent-brain index ./src --include-type python
      agent-brain index ./project --include-type python,docs
      agent-brain types list              # See all available presets
      agent-brain types list --json       # JSON output
    """
    if json_output:
        click.echo(json.dumps(FILE_TYPE_PRESETS, indent=2))
        return

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Preset", style="bold")
    table.add_column("Extensions")

    for preset_name, patterns in FILE_TYPE_PRESETS.items():
        table.add_row(preset_name, ", ".join(patterns))

    console.print(table)
    console.print(
        "\n[dim]Use with: agent-brain index <path> --include-type <preset>[/]"
    )
