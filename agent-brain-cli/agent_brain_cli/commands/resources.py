"""``agent-brain resources`` Click sub-group (Phase 59 Plan 03).

Subcommands:
    list — calls MCP resources/list + resources/templates/list; renders
           merged table with URI / Mime Type / Type columns. --json flag
           prints the raw merged dict instead.
    read <uri> — calls MCP resources/read; dispatches on content type:
           - JSON (mimeType == application/json or text and parses as JSON):
             pretty-print to stdout (json.dumps indent=2)
           - Text (mimeType starts with text/): pass through to stdout
           - Binary (blob content): REJECT writing to stdout — exit 2 with
             "Resource is binary ({mimeType}); pass --output-file PATH to save"
           - With --output-file PATH: write to file (binary-safe wb mode),
             echo "wrote {bytes} bytes to {path}" confirmation.

Server-side file:// sandbox is the authoritative source: the CLI does NOT
pre-check URIs against indexed roots. The agent-brain-mcp server returns
McpError with the sandbox-deny reason in the error data; the CLI catches
and surfaces VERBATIM to stderr. CLI-MCP-07.

Mirrors v3 design doc §3.5 no-silent-fallback contract: every subcommand
requires --transport mcp explicitly (enforced by :func:`open_mcp_backend`
from Phase 59 Plan 01).

Pattern carry-forward from Plan 59-02 ``commands/prompt.py``:
``McpBackend`` Protocol intentionally does NOT declare ``__enter__`` /
``__exit__`` — Pattern A (Plan 57-02 / 57-03) spawns a fresh
stdio_client / streamablehttp_client per call inside the async helper,
so there is no persistent connection to bracket CLI-side. Do NOT add a
``with backend:`` wrapper (mypy strict catches the Protocol shape
mismatch). Phase 60 may revisit if a persistent-loop refactor lands.
"""

from __future__ import annotations

import base64
import binascii
import json
import sys
from pathlib import Path
from typing import Any

import click
from mcp import McpError
from rich.console import Console
from rich.table import Table

from agent_brain_cli.client.transport import open_mcp_backend

_TEXT_MIME_PREFIXES: tuple[str, ...] = ("text/",)
_TEXT_MIME_LITERALS: frozenset[str] = frozenset({"application/text"})
_JSON_MIME_LITERALS: frozenset[str] = frozenset({"application/json"})


@click.group("resources")
def resources_group() -> None:
    """Enumerate and read MCP resources exposed by agent-brain-mcp.

    \b
    Examples:
      agent-brain --transport mcp --mcp-transport stdio resources list
      agent-brain --transport mcp --mcp-transport stdio resources list --json
      agent-brain --transport mcp --mcp-transport stdio resources read \\
          corpus://status
      agent-brain --transport mcp --mcp-transport stdio resources read \\
          file:///path/x.txt
      agent-brain --transport mcp --mcp-transport stdio resources read \\
          file:///a.png --output-file out.png
    """


@resources_group.command("list")
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Print the raw merged static+templates dict as pretty JSON.",
)
@click.pass_context
def list_command(ctx: click.Context, as_json: bool) -> None:
    """Enumerate all static URIs + templated URI schemes.

    Calls MCP ``resources/list`` (5 static URIs) AND
    ``resources/templates/list`` (4 templated URI schemes), merges into
    a single sorted (URI-alphabetical) table. With ``--json`` prints the
    raw merged dict instead.
    """
    backend = open_mcp_backend(ctx)
    try:
        static = backend.list_resources()
        templates = backend.list_resource_templates()
    except McpError as exc:
        click.echo(f"Error listing resources: {exc}", err=True)
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001 — surface SDK / wire failures
        click.echo(f"Error listing resources: {exc}", err=True)
        sys.exit(1)

    if as_json:
        click.echo(json.dumps({"resources": static, "templates": templates}, indent=2))
        return

    rows: list[tuple[str, str, str]] = []
    for r in static:
        uri = r.get("uri", "") or ""
        mime = r.get("mimeType", "") or ""
        rows.append((uri, mime, "static"))
    for t in templates:
        uri = t.get("uriTemplate", "") or t.get("uri", "") or ""
        mime = t.get("mimeType", "") or ""
        rows.append((uri, mime, "templated"))

    rows.sort(key=lambda row: row[0])

    console = Console()
    table = Table(title="MCP resources", show_header=True, header_style="bold")
    table.add_column("URI", overflow="fold")
    table.add_column("Mime Type", overflow="fold")
    table.add_column("Type")
    for uri, mime, kind in rows:
        table.add_row(uri, mime, kind)
    console.print(table)


@resources_group.command("read")
@click.argument("uri", required=True)
@click.option(
    "--output-file",
    "output_file",
    type=click.Path(dir_okay=False, resolve_path=False),
    default=None,
    help="Write content to this file (required for binary resources).",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help=(
        "Always pretty-print as JSON regardless of mime type "
        "(no content-type dispatch)."
    ),
)
@click.pass_context
def read_command(
    ctx: click.Context, uri: str, output_file: str | None, as_json: bool
) -> None:
    """Read an MCP resource by URI.

    Content-type dispatch (default mode):
      - JSON (mimeType == application/json): pretty-print to stdout
      - Text (mimeType starts with text/ or == application/text):
        passthrough to stdout
      - Binary (blob present): REJECT — exit 2 with
        "Resource is binary ({mimeType}); pass --output-file PATH to save"

    ``--output-file PATH``: write content (binary-safe ``wb`` mode) for
    BOTH text and binary resources; echo
    ``wrote {N} bytes to {path}`` confirmation. Universal escape hatch.

    ``--json``: force pretty JSON output regardless of mime type.

    Server-side ``file://`` sandbox is the authoritative source — the
    CLI does NOT pre-check URIs against indexed roots. The
    agent-brain-mcp server raises ``McpError`` with the sandbox deny
    reason in the error message/data; the CLI surfaces that error
    VERBATIM to stderr and exits 2. CLI-MCP-07.
    """
    backend = open_mcp_backend(ctx)
    result: dict[str, Any]
    try:
        result = backend.read_resource(uri)
    except McpError as exc:
        # Surface server verdict (especially the file:// sandbox deny
        # reason) VERBATIM to stderr per CONTEXT.md decisions. The
        # message + data are part of the McpError repr; we do NOT
        # paraphrase, we do NOT pre-check sandbox CLI-side.
        click.echo(f"Error reading {uri}: {exc}", err=True)
        sys.exit(2)
    except Exception as exc:  # noqa: BLE001 — surface SDK / wire failures
        click.echo(f"Error reading {uri}: {exc}", err=True)
        sys.exit(1)

    contents = result.get("contents") or []
    if not contents:
        click.echo(f"Resource {uri} returned no contents", err=True)
        sys.exit(1)

    first = contents[0] or {}
    mime = (first.get("mimeType") or "").lower()
    text = first.get("text")
    blob = first.get("blob")

    # --output-file: write whatever content is present, binary-safe.
    if output_file is not None:
        path = Path(output_file)
        if blob is not None:
            try:
                payload = base64.b64decode(blob)
            except (binascii.Error, ValueError) as exc:
                click.echo(f"Failed to decode blob for {uri}: {exc}", err=True)
                sys.exit(3)
            path.write_bytes(payload)
            click.echo(f"wrote {len(payload)} bytes to {path}")
            return
        if text is not None:
            data = text.encode("utf-8")
            path.write_bytes(data)
            click.echo(f"wrote {len(data)} bytes to {path}")
            return
        click.echo(f"Resource {uri} has neither text nor blob", err=True)
        sys.exit(1)

    # --json flag: force JSON pretty-print regardless of content type.
    if as_json:
        if text is not None:
            # If text already parses as JSON, render the parsed form.
            try:
                parsed = json.loads(text)
                click.echo(json.dumps(parsed, indent=2))
                return
            except (json.JSONDecodeError, TypeError):
                # Fall back: dump full result as JSON so the user sees
                # everything (mimeType + text wrapped).
                click.echo(json.dumps(result, indent=2))
                return
        click.echo(json.dumps(result, indent=2))
        return

    # Default content-type dispatch.
    if blob is not None:
        # Binary: REJECT stdout — exit 2 with the standard message.
        # click.UsageError → Click exits 2 with message on stderr.
        raise click.UsageError(
            f"Resource is binary ({mime or 'unknown'}); "
            f"pass --output-file PATH to save"
        )

    if text is None:
        click.echo(f"Resource {uri} has no text content", err=True)
        sys.exit(1)

    # JSON mime → pretty-print (try to parse; fall back to passthrough on bad JSON).
    if mime in _JSON_MIME_LITERALS:
        try:
            parsed = json.loads(text)
            click.echo(json.dumps(parsed, indent=2))
            return
        except json.JSONDecodeError:
            # Server claimed JSON but content isn't — fall through to text.
            pass

    # Text / application-text → passthrough.
    if mime.startswith(_TEXT_MIME_PREFIXES) or mime in _TEXT_MIME_LITERALS:
        click.echo(text)
        return

    # Unknown mime with text content: best-effort JSON parse, else passthrough.
    try:
        parsed = json.loads(text)
        click.echo(json.dumps(parsed, indent=2))
    except json.JSONDecodeError:
        click.echo(text)


__all__ = ["resources_group"]
