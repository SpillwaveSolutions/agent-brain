"""``agent-brain prompt <name>`` — invoke an MCP prompt and print the
expanded content.

Phase 59 Plan 02 (CLI-MCP-05). Requires ``--transport mcp`` (enforced
by :func:`open_mcp_backend` from Phase 59 Plan 01). Mirrors the
no-silent-fallback contract from v10.2 HTTP-03 and Phase 57 §3.5.

Examples::

    agent-brain --transport mcp --mcp-transport stdio prompt find-callers \\
        --arg symbol=parse_query --arg file=query_service.py
    agent-brain --transport mcp --mcp-transport http prompt explain-architecture
    agent-brain --transport mcp --mcp-transport stdio \\
        prompt onboard-to-codebase --json

The command does NOT hard-code the list of available prompt names — it
forwards ``<name>`` verbatim to the MCP server's ``prompts/get`` endpoint
and, on an MCP error response (unknown name), queries ``prompts/list``
to compose a usage-error message listing the available names.

Output modes (mutually exclusive — ``--json`` overrides default render):

  - Default: concatenated ``messages[].content.text`` joined with the
    literal separator ``"\\n---\\n"`` between messages (mirrors the v2
    design doc §6.6 client-side rendering convention).
  - ``--json``: pretty-printed JSON dict (``indent=2``) of the raw
    ``prompts/get`` response — easy to pipe into ``jq``.

Both modes go to stdout (clean pipe target). Errors go to stderr via
``click.echo(err=True)`` or ``click.UsageError`` (exit 2).
"""

from __future__ import annotations

import json
import sys
from typing import Any

import click
from mcp import McpError

from agent_brain_cli.client.transport import open_mcp_backend


def _parse_arg(arg: str) -> tuple[str, str]:
    """Split ``--arg KEY=VALUE`` on the FIRST ``=`` only.

    VALUE may contain additional ``=`` characters — they are preserved
    verbatim. The partition-on-first-``=`` semantics mirror the
    established CLI-command idiom in
    ``agent_brain_cli/commands/index.py`` (see ``--metadata KEY=VALUE``).

    Args:
        arg: The raw ``KEY=VALUE`` string from a single ``--arg`` flag.

    Returns:
        ``(key, value)`` 2-tuple.

    Raises:
        click.UsageError: When ``=`` is missing entirely OR when ``KEY``
            is empty (e.g. ``=value``). Click translates UsageError into
            exit code 2 with the message on stderr.
    """
    if "=" not in arg:
        raise click.UsageError(
            f"--arg value must be KEY=VALUE; got {arg!r} (missing '=')"
        )
    key, _, value = arg.partition("=")
    if not key:
        raise click.UsageError(
            f"--arg KEY must be non-empty; got {arg!r}"
        )
    return key, value


@click.command("prompt")
@click.argument("name", required=True)
@click.option(
    "--arg",
    "args",
    multiple=True,
    metavar="KEY=VALUE",
    help=(
        "Prompt argument as KEY=VALUE. Repeat for multiple args. "
        "VALUE may contain '=' (split on the first one only)."
    ),
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Print the raw prompts/get response as pretty JSON (indent=2).",
)
@click.pass_context
def prompt_command(
    ctx: click.Context, name: str, args: tuple[str, ...], as_json: bool
) -> None:
    """Invoke an MCP prompt by name and print its expanded content.

    Requires ``--transport mcp`` explicitly; no silent fallback to
    UDS/HTTP. Without it, the underlying ``open_mcp_backend`` factory
    raises ``click.UsageError`` (exit 2) per the Phase 57 §3.5
    no-silent-fallback contract.

    Unknown prompt name:
        When the MCP server responds with an error (typically
        ``-32602 INVALID_PARAMS`` for unknown prompts), the CLI catches
        :class:`mcp.McpError`, queries ``prompts/list`` to enumerate
        available names, and exits 2 with::

            Unknown prompt 'name'; available: a, b, c

        Names are alphabetically sorted for stable output.
    """
    # Parse --arg flags up-front so a malformed value surfaces before
    # the backend is constructed (the factory contract is a separate
    # axis from the arg-parse contract). Click translates UsageError
    # to exit 2 with the message on stderr.
    parsed_args: dict[str, str] = {}
    for raw in args:
        key, value = _parse_arg(raw)
        parsed_args[key] = value

    # open_mcp_backend enforces --transport mcp at a single point and
    # raises click.UsageError if the operator forgot it. The factory is
    # Plan 59-01's contract.
    #
    # Note: McpBackend Protocol intentionally does NOT declare
    # __enter__/__exit__ — Pattern A (Plan 57-02 / 57-03) spawns a
    # fresh stdio_client / streamablehttp_client per call inside the
    # async helper, so there is no persistent connection to bracket
    # CLI-side. Phase 60 may revisit if a persistent-loop refactor
    # lands.
    backend = open_mcp_backend(ctx)
    result: dict[str, Any]
    try:
        try:
            # Pass None (not {}) when no --arg was provided — the
            # MCP server treats them differently per the spec.
            result = backend.get_prompt(name, parsed_args or None)
        except McpError as exc:
            # Unknown prompt → fall back to prompts/list to give the
            # operator the available-names list. Defensive: if the
            # list call itself fails, surface the original error so
            # the user isn't told a second error masked the first.
            try:
                available_raw = backend.list_prompts()
            except Exception as list_exc:  # noqa: BLE001
                raise click.UsageError(
                    f"Prompt call failed: {exc}; additionally, "
                    f"prompts/list failed: {list_exc}"
                ) from exc
            names = sorted(
                p.get("name", "")
                for p in available_raw
                if p.get("name")
            )
            joined = (
                ", ".join(names) if names else "<no prompts registered>"
            )
            raise click.UsageError(
                f"Unknown prompt {name!r}; available: {joined}"
            ) from exc
    except click.UsageError:
        # UsageError is Click's standard exit-2 channel — re-raise so
        # Click handles the exit code + stderr surfacing.
        raise
    except Exception as exc:  # noqa: BLE001
        # Non-MCP failures (subprocess died, HTTP unreachable, SDK
        # internal error) surface as exit 1 with the error on stderr.
        click.echo(f"Error invoking prompt {name!r}: {exc}", err=True)
        sys.exit(1)

    if as_json:
        click.echo(json.dumps(result, indent=2))
        return

    # Default: render the expanded prompt text. Each message in the
    # MCP `prompts/get` response has shape
    # ``{"role": "...", "content": {"type": "text", "text": "..."}}``;
    # concatenate text bodies with the literal separator '\n---\n'
    # between messages (mirrors v2 design doc §6.6 convention).
    messages = result.get("messages", []) or []
    if not messages:
        # No messages — surface the description so the operator gets
        # SOMETHING useful instead of a blank line.
        description = result.get("description") or ""
        click.echo(description)
        return
    rendered: list[str] = []
    for message in messages:
        content = message.get("content") or {}
        text = content.get("text", "") or ""
        rendered.append(text)
    click.echo("\n---\n".join(rendered))


__all__ = ["prompt_command"]
