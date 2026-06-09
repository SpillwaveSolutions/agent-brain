"""Tests for ``agent-brain prompt <name>`` (Phase 59 Plan 02).

Covers the 9 must-have behaviors from the Plan 59-02 test plan:

  1. Missing ``--transport mcp`` → exit 2 with UsageError citing
     ``--transport mcp`` (open_mcp_backend factory contract — Plan 59-01).
  2. Happy path (default render): calls ``backend.get_prompt(name, None)``
     and prints messages[].content.text to stdout.
  3. ``--json`` flag: prints raw prompts/get dict as pretty JSON.
  4. ``--arg KEY=VALUE`` parses to a dict and forwards to
     ``backend.get_prompt``.
  5. ``--arg malformed`` (no ``=``) exits 2 with UsageError citing
     ``KEY=VALUE``.
  6. ``--arg =value`` (empty key) exits 2 with UsageError citing
     non-empty KEY.
  7. Unknown prompt name → CLI catches McpError, calls
     ``backend.list_prompts()``, exits 2 with sorted available names.
  8. Multi-message rendering: messages joined with literal ``\\n---\\n``.
  9. ``--arg expr=a=b`` partition-on-first-``=`` preserves the embedded
     ``=`` in VALUE.

Scope: UNIT. ``open_mcp_backend`` is patched at the command module's
import site so no real subprocess is ever spawned. Real-MCP coverage
is the future integration test in ``tests/integration/`` using the
Plan 57 corpus seeder (out of scope for this plan).
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner
from mcp import McpError
from mcp.types import ErrorData

from agent_brain_cli.cli import cli

# ---------------------------------------------------------------------------
# Fake backend factory — context-manager-aware MagicMock
# ---------------------------------------------------------------------------


def _make_fake_backend(
    *,
    get_prompt_result: dict[str, Any] | None = None,
    get_prompt_side_effect: BaseException | None = None,
    list_prompts_result: list[dict[str, Any]] | None = None,
) -> MagicMock:
    """Build a MagicMock that satisfies the McpBackend Protocol context
    manager surface AND records get_prompt/list_prompts calls.
    """
    backend = MagicMock()
    if get_prompt_side_effect is not None:
        backend.get_prompt = MagicMock(side_effect=get_prompt_side_effect)
    else:
        backend.get_prompt = MagicMock(
            return_value=get_prompt_result
            or {
                "description": "test prompt",
                "messages": [
                    {
                        "role": "user",
                        "content": {"type": "text", "text": "Test message body."},
                    }
                ],
            }
        )
    backend.list_prompts = MagicMock(
        return_value=list_prompts_result
        or [
            {"name": "find-callers"},
            {"name": "audit-indexed-folders"},
            {"name": "explain-architecture"},
        ]
    )
    # Context-manager surface — Plan 59-02 wraps backend in `with ...:`
    backend.__enter__ = MagicMock(return_value=backend)
    backend.__exit__ = MagicMock(return_value=None)
    backend.close = MagicMock(return_value=None)
    return backend


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_prompt_command_requires_transport_mcp() -> None:
    """Without --transport mcp, the command must exit 2 with a UsageError
    that mentions ``--transport mcp``."""
    runner = CliRunner()
    result = runner.invoke(cli, ["prompt", "find-callers"])

    assert result.exit_code == 2, (
        f"Expected exit 2, got {result.exit_code}\n"
        f"stdout: {result.output}\nstderr: {result.stderr_bytes}"
    )
    assert "--transport mcp" in result.output


def test_prompt_command_happy_path_default_render() -> None:
    """`agent-brain --transport mcp ... prompt find-callers` calls
    backend.get_prompt with (name, None) and prints the messages text."""
    backend = _make_fake_backend()
    with patch(
        "agent_brain_cli.commands.prompt.open_mcp_backend",
        return_value=backend,
    ):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--transport",
                "mcp",
                "--mcp-transport",
                "stdio",
                "prompt",
                "find-callers",
            ],
        )

    assert result.exit_code == 0, (
        f"Expected exit 0, got {result.exit_code}\n"
        f"stdout: {result.output}\nexception: {result.exception!r}"
    )
    backend.get_prompt.assert_called_once_with("find-callers", None)
    assert "Test message body." in result.output


def test_prompt_command_json_flag_pretty_prints_dict() -> None:
    """``--json`` prints the raw prompts/get dict via json.dumps(indent=2)."""
    canned = {
        "description": "json prompt",
        "messages": [
            {
                "role": "user",
                "content": {"type": "text", "text": "Body."},
            }
        ],
    }
    backend = _make_fake_backend(get_prompt_result=canned)
    with patch(
        "agent_brain_cli.commands.prompt.open_mcp_backend",
        return_value=backend,
    ):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--transport",
                "mcp",
                "--mcp-transport",
                "stdio",
                "prompt",
                "find-callers",
                "--json",
            ],
        )

    assert (
        result.exit_code == 0
    ), f"Expected exit 0, got {result.exit_code}\nstdout: {result.output}"
    # The output must be parseable JSON equal to the canned dict.
    parsed = json.loads(result.output)
    assert parsed == canned
    # Pretty-printed: more than one line.
    assert result.output.count("\n") >= 2


def test_prompt_command_arg_kv_pairs_forwarded_to_get_prompt() -> None:
    """``--arg symbol=parse_query --arg file=query_service.py`` parses
    to a dict and forwards to backend.get_prompt."""
    backend = _make_fake_backend()
    with patch(
        "agent_brain_cli.commands.prompt.open_mcp_backend",
        return_value=backend,
    ):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--transport",
                "mcp",
                "--mcp-transport",
                "stdio",
                "prompt",
                "find-callers",
                "--arg",
                "symbol=parse_query",
                "--arg",
                "file=query_service.py",
            ],
        )

    assert (
        result.exit_code == 0
    ), f"Expected exit 0, got {result.exit_code}\nstdout: {result.output}"
    backend.get_prompt.assert_called_once_with(
        "find-callers",
        {"symbol": "parse_query", "file": "query_service.py"},
    )


def test_prompt_command_malformed_arg_no_equals_sign_exits_2() -> None:
    """``--arg malformed`` (no ``=``) exits 2 with KEY=VALUE in the error."""
    backend = _make_fake_backend()
    with patch(
        "agent_brain_cli.commands.prompt.open_mcp_backend",
        return_value=backend,
    ):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--transport",
                "mcp",
                "--mcp-transport",
                "stdio",
                "prompt",
                "find-callers",
                "--arg",
                "malformed",
            ],
        )

    assert result.exit_code == 2
    assert "KEY=VALUE" in result.output


def test_prompt_command_empty_key_in_arg_exits_2() -> None:
    """``--arg =value`` (empty key) exits 2 with non-empty KEY citation."""
    backend = _make_fake_backend()
    with patch(
        "agent_brain_cli.commands.prompt.open_mcp_backend",
        return_value=backend,
    ):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--transport",
                "mcp",
                "--mcp-transport",
                "stdio",
                "prompt",
                "find-callers",
                "--arg",
                "=value",
            ],
        )

    assert result.exit_code == 2
    # Wording mentions non-empty KEY requirement.
    assert "KEY" in result.output
    assert "non-empty" in result.output.lower() or "empty" in result.output.lower()


def test_prompt_command_unknown_name_lists_available_alphabetical() -> None:
    """Unknown prompt name → catches McpError → calls list_prompts →
    exits 2 with sorted available names."""
    err = McpError(ErrorData(code=-32602, message="Unknown prompt: unknown-name"))
    backend = _make_fake_backend(
        get_prompt_side_effect=err,
        list_prompts_result=[
            {"name": "find-callers"},
            {"name": "audit-indexed-folders"},
            {"name": "explain-architecture"},
        ],
    )
    with patch(
        "agent_brain_cli.commands.prompt.open_mcp_backend",
        return_value=backend,
    ):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--transport",
                "mcp",
                "--mcp-transport",
                "stdio",
                "prompt",
                "unknown-name",
            ],
        )

    assert result.exit_code == 2
    assert "Unknown prompt" in result.output
    assert "unknown-name" in result.output
    # Alphabetical sort of available names.
    assert "audit-indexed-folders, explain-architecture, find-callers" in result.output
    # The fallback list_prompts call happened.
    backend.list_prompts.assert_called_once()


def test_prompt_command_multi_message_joined_with_separator() -> None:
    """Multi-message messages list joined with literal ``\\n---\\n``."""
    canned = {
        "description": "multi msg",
        "messages": [
            {"role": "user", "content": {"type": "text", "text": "first"}},
            {"role": "user", "content": {"type": "text", "text": "second"}},
            {"role": "user", "content": {"type": "text", "text": "third"}},
        ],
    }
    backend = _make_fake_backend(get_prompt_result=canned)
    with patch(
        "agent_brain_cli.commands.prompt.open_mcp_backend",
        return_value=backend,
    ):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--transport",
                "mcp",
                "--mcp-transport",
                "stdio",
                "prompt",
                "explain-architecture",
            ],
        )

    assert result.exit_code == 0
    # The separator appears verbatim between messages.
    assert "first\n---\nsecond\n---\nthird" in result.output


def test_prompt_command_arg_value_may_contain_equals_sign() -> None:
    """``--arg expr=a=b`` partitions on the FIRST ``=`` only — VALUE
    retains the embedded ``=``."""
    backend = _make_fake_backend()
    with patch(
        "agent_brain_cli.commands.prompt.open_mcp_backend",
        return_value=backend,
    ):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--transport",
                "mcp",
                "--mcp-transport",
                "stdio",
                "prompt",
                "find-callers",
                "--arg",
                "expr=a=b",
            ],
        )

    assert result.exit_code == 0
    backend.get_prompt.assert_called_once_with("find-callers", {"expr": "a=b"})


def test_prompt_command_help_lists_arg_and_json_options() -> None:
    """``agent-brain prompt --help`` documents <name>, --arg, and --json."""
    runner = CliRunner()
    result = runner.invoke(cli, ["prompt", "--help"])

    assert result.exit_code == 0
    assert "--arg" in result.output
    assert "--json" in result.output
    # The positional NAME argument shows up in usage.
    assert "NAME" in result.output


@pytest.mark.parametrize(
    "argv,expected_arguments",
    [
        # No --arg → None forwarded (preserve None vs {} distinction).
        ([], None),
        # Single --arg → dict with one entry.
        (["--arg", "x=1"], {"x": "1"}),
        # Three --arg → dict with three entries, last one wins on dup key.
        (
            ["--arg", "a=1", "--arg", "b=2", "--arg", "a=3"],
            {"a": "3", "b": "2"},
        ),
    ],
)
def test_prompt_command_arg_forwarding_matrix(
    argv: list[str], expected_arguments: dict[str, str] | None
) -> None:
    """Matrix: zero / one / multi (with duplicate KEY) ``--arg`` cases."""
    backend = _make_fake_backend()
    with patch(
        "agent_brain_cli.commands.prompt.open_mcp_backend",
        return_value=backend,
    ):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--transport",
                "mcp",
                "--mcp-transport",
                "stdio",
                "prompt",
                "find-callers",
                *argv,
            ],
        )

    assert result.exit_code == 0
    backend.get_prompt.assert_called_once_with("find-callers", expected_arguments)
