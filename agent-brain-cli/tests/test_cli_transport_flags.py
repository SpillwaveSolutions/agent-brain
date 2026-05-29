"""Phase 3 TDD: CLI-level ``--transport`` / ``--socket-path`` / ``--base-url``
/ ``--debug-transport`` flags on the root ``agent-brain`` group.

Maps to plan §12.3 #5 (HTTP/UDS produce equivalent results), #7 (an
explicit mismatch raises). The byte-identical-results acceptance #5 is
verified separately by an end-to-end integration test once Phase 3 GREEN
is in (the test plan reserves it for `agent-brain-cli/tests/integration/`).

RED until ``agent_brain_cli/cli.py`` gains the four flags and stores them
on ``ctx.obj``.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_brain_cli.cli import cli


@pytest.fixture
def clean_env() -> Generator[None, None, None]:
    keys = [k for k in os.environ if k.startswith("AGENT_BRAIN_")]
    saved = {k: os.environ.pop(k) for k in keys}
    try:
        yield
    finally:
        for k in keys:
            os.environ.pop(k, None)
        os.environ.update(saved)


@pytest.fixture
def short_state_dir() -> Generator[Path, None, None]:
    base = Path(tempfile.mkdtemp(prefix="absrv-cli-tx-"))
    os.chmod(base, 0o700)
    try:
        yield base
    finally:
        import shutil

        shutil.rmtree(base, ignore_errors=True)


class TestCliTransportFlagAccepted:
    """``--transport`` is a valid root option with choices."""

    def test_transport_flag_in_help(self, clean_env: None) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "--transport" in result.output

    def test_socket_path_flag_in_help(self, clean_env: None) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "--socket-path" in result.output

    def test_base_url_flag_in_help(self, clean_env: None) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "--base-url" in result.output

    def test_debug_transport_flag_in_help(self, clean_env: None) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "--debug-transport" in result.output


class TestCliTransportFlagRejectsInvalidChoice:
    """``--transport`` rejects values outside {auto,http,uds}."""

    def test_unknown_transport_value_rejected(self, clean_env: None) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--transport", "tcp42", "--help"])
        # Click prints usage + non-zero exit for invalid choice.
        assert result.exit_code != 0
        assert "tcp42" in result.output or "invalid" in result.output.lower()


class TestCliTransportFlagPopulatesContext:
    """Root flags must land on ``ctx.obj`` so subcommands can read them."""

    def test_transport_flag_lands_on_ctx_obj(self, clean_env: None) -> None:
        """Use a side-channel subcommand to inspect ``ctx.obj``."""
        import click

        @cli.command("ctx-probe", hidden=True)
        @click.pass_context
        def probe(ctx: click.Context) -> None:
            click.echo(f"TRANSPORT={ctx.obj.get('transport_hint')}")
            click.echo(f"BASE_URL={ctx.obj.get('base_url_override')}")
            click.echo(f"SOCKET={ctx.obj.get('socket_path_override')}")
            click.echo(f"DEBUG={ctx.obj.get('debug_transport')}")

        try:
            runner = CliRunner()
            result = runner.invoke(
                cli,
                [
                    "--transport",
                    "uds",
                    "--base-url",
                    "http://127.0.0.1:9999",
                    "--socket-path",
                    "/tmp/test.sock",
                    "--debug-transport",
                    "ctx-probe",
                ],
            )
            assert result.exit_code == 0, result.output
            assert "TRANSPORT=uds" in result.output
            assert "BASE_URL=http://127.0.0.1:9999" in result.output
            assert "SOCKET=/tmp/test.sock" in result.output
            assert "DEBUG=True" in result.output
        finally:
            # Pop the probe back off so other tests see a clean group.
            cli.commands.pop("ctx-probe", None)


class TestUdsOnlyMismatchRaises:
    """Plan §12.3 #7 — when CLI resolves to HTTP but ``--transport uds``
    was requested and no socket exists, the error must be explicit, not
    a hang or a silent fallback."""

    def test_explicit_uds_without_socket_exits_non_zero(
        self, clean_env: None, short_state_dir: Path
    ) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--transport",
                "uds",
                "--socket-path",
                str(short_state_dir / "no-such-socket.sock"),
                "status",
            ],
        )
        # Either a top-level exception or a clean non-zero exit is fine;
        # what must NOT happen is exit_code == 0 (silent HTTP fallback).
        assert result.exit_code != 0
        msg = (result.output or "") + (
            str(result.exception) if result.exception else ""
        )
        # Must NOT be Click's "no such option" error — that means the
        # --transport flag wasn't recognized (the bug this test pins is
        # downstream of flag parsing, not at the parser).
        assert "No such option" not in msg, (
            "Test would pass for the wrong reason — the CLI didn't even "
            f"recognize --transport. Output: {msg}"
        )
        # The error must be specifically about the socket / transport.
        assert (
            "socket" in msg.lower()
            or "not found" in msg.lower()
            or "no such" in msg.lower()
        )
