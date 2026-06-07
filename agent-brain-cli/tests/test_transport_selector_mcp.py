"""Phase 57-01 TDD: ``--transport mcp`` selector + ``open_backend`` dispatcher.

Maps to v3 design doc §3.5 (No-silent-fallback contract — all three
misuse cases surface as exit-2 ``click.UsageError``) and the §2.1
three-axes transport model (``cli_backend_transport`` is the axis
selected by ``--transport mcp`` + ``--mcp-transport``).

Test surface:

  Test 1 (§3.5 case 1): --transport mcp with agent_brain_mcp.client NOT
                        importable → exit 2 + "install agent-brain-mcp
                        to use --transport mcp".
  Test 2 (§3.5 case 2): --mcp-transport http without --mcp-url and no
                        env → exit 2 + "discovery file support lands in
                        Phase 58".
  Test 3 (skeleton routing — stdio): --transport mcp --mcp-transport
                        stdio reaches McpStdioBackend skeleton's
                        NotImplementedError("Wired in Phase 57+").
  Test 4 (skeleton routing — http): --transport mcp --mcp-transport
                        http --mcp-url <url> reaches McpHttpBackend
                        skeleton's NotImplementedError.
  Test 5 (regression): --transport http still constructs a HTTP backend
                        (the rename open_client → open_backend did not
                        break the HTTP path).
  Test 6 (smoke): ``open_backend`` is importable from the same module
                  AND ``open_client`` is gone.
  Test 7 (§3.5 case 3): --transport mcp --mcp-transport stdio with
                        agent-brain-mcp not reachable on PATH (shutil.
                        which returns None) → exit 2 + "agent-brain-mcp
                        not found on PATH; install agent-brain-mcp into
                        the same Python environment".
"""

from __future__ import annotations

import os
import sys
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from agent_brain_cli.cli import cli


@pytest.fixture
def clean_env() -> Generator[None, None, None]:
    """Strip every AGENT_BRAIN_* env var for the duration of one test."""
    keys = [k for k in os.environ if k.startswith("AGENT_BRAIN_")]
    saved = {k: os.environ.pop(k) for k in keys}
    try:
        yield
    finally:
        for k in keys:
            os.environ.pop(k, None)
        os.environ.update(saved)


class TestMcpCase1PackageNotInstalled:
    """§3.5 case 1 — agent-brain-mcp package not installed."""

    def test_mcp_without_package_exits_2_with_install_message(
        self, clean_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Force the lazy import inside the dispatcher to fail by stubbing
        # the module to None in sys.modules. Python's import machinery
        # treats a None-valued sys.modules entry as a recorded ImportError.
        monkeypatch.setitem(sys.modules, "agent_brain_mcp.client", None)

        runner = CliRunner()
        result = runner.invoke(cli, ["--transport", "mcp", "query", "X"])

        assert result.exit_code == 2, (
            f"expected exit code 2, got {result.exit_code}; "
            f"output={result.output!r}"
        )
        assert (
            "install agent-brain-mcp to use --transport mcp" in result.output.lower()
            or "install agent-brain-mcp to use --transport mcp" in result.output
        )


class TestMcpCase2HttpWithoutUrl:
    """§3.5 case 2 — --mcp-transport http without a URL."""

    def test_http_without_url_exits_2_with_phase58_message(
        self, clean_env: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Phase 58 wired discovery via mcp.runtime.json. Use an empty
        # state_dir so discovery fails and the verbatim §3.5 wording
        # surfaces.
        monkeypatch.setenv("AGENT_BRAIN_STATE_DIR", str(tmp_path))
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--transport", "mcp", "--mcp-transport", "http", "query", "X"],
            env={"AGENT_BRAIN_MCP_URL": ""},
        )

        assert result.exit_code == 2, (
            f"expected exit code 2, got {result.exit_code}; "
            f"output={result.output!r}"
        )
        # Phase 58 swapped wording — verbatim v3 design doc §3.5.
        assert "discovery file not found at" in result.output
        assert "run 'agent-brain mcp start' or pass --mcp-url" in result.output


class TestSkeletonRoutingStdio:
    """--transport mcp --mcp-transport stdio reaches the McpStdioBackend
    skeleton — proves the dispatcher routed correctly (the skeleton then
    raises NotImplementedError("Wired in Phase 57+"))."""

    def test_stdio_branch_reaches_skeleton(
        self, clean_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Skip if agent-brain-mcp isn't installed in the venv — that
        # path is covered by TestMcpCase1PackageNotInstalled (§3.5 case 1).
        pytest.importorskip("agent_brain_mcp.client")
        # PATH precheck must pass so the dispatcher hits the actual
        # McpStdioBackend constructor + .query() method.
        monkeypatch.setattr(
            "shutil.which",
            lambda cmd: (
                "/usr/local/bin/agent-brain-mcp" if cmd == "agent-brain-mcp" else None
            ),
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--transport", "mcp", "--mcp-transport", "stdio", "query", "X"],
        )

        # Either Click surfaces the NotImplementedError as result.exception
        # OR the message lands in result.output. Either is acceptable as
        # long as the skeleton's sentinel string was reached.
        combined = result.output + (str(result.exception) if result.exception else "")
        assert "Wired in Phase 57+" in combined, (
            f"expected skeleton's NotImplementedError sentinel to surface; "
            f"exit_code={result.exit_code} output={result.output!r} "
            f"exception={result.exception!r}"
        )


class TestSkeletonRoutingHttp:
    """--transport mcp --mcp-transport http --mcp-url <url> reaches the
    McpHttpBackend skeleton."""

    def test_http_branch_reaches_skeleton(self, clean_env: None) -> None:
        # Skip if agent-brain-mcp isn't installed in the venv — that
        # path is covered by TestMcpCase1PackageNotInstalled (§3.5 case 1).
        pytest.importorskip("agent_brain_mcp.client")

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--transport",
                "mcp",
                "--mcp-transport",
                "http",
                "--mcp-url",
                "http://127.0.0.1:9999/mcp",
                "query",
                "X",
            ],
        )

        combined = result.output + (str(result.exception) if result.exception else "")
        assert "Wired in Phase 57+" in combined, (
            f"expected skeleton's NotImplementedError sentinel to surface; "
            f"exit_code={result.exit_code} output={result.output!r} "
            f"exception={result.exception!r}"
        )


class TestHttpRegression:
    """The rename open_client → open_backend did not break --transport http.

    We patch the per-command open_backend call site to return a MagicMock
    so we don't need a live server — the assertion here is only that the
    CLI reaches the command handler over the HTTP branch.
    """

    def test_http_transport_still_resolves_query_command(self, clean_env: None) -> None:
        with patch("agent_brain_cli.commands.query.open_backend") as mock_open:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=None)
            mock_client.query.return_value = MagicMock(
                results=[],
                query="X",
                count=0,
                total_count=0,
                elapsed_seconds=0.01,
                source_types_searched=None,
                languages_searched=None,
                file_paths_searched=None,
            )
            mock_open.return_value = mock_client

            runner = CliRunner()
            result = runner.invoke(
                cli,
                [
                    "--transport",
                    "http",
                    "--base-url",
                    "http://127.0.0.1:8000",
                    "query",
                    "X",
                ],
            )

            # The query command should have been reached via open_backend.
            assert mock_open.called, (
                f"expected open_backend to be invoked from the query "
                f"command on the HTTP transport; "
                f"exit_code={result.exit_code} output={result.output!r}"
            )


class TestOpenBackendImportSmoke:
    """``open_backend`` is importable and ``open_client`` is gone."""

    def test_open_backend_importable(self) -> None:
        from agent_brain_cli.client.transport import open_backend  # noqa: F401

        assert callable(open_backend)

    def test_open_client_no_longer_present(self) -> None:
        import agent_brain_cli.client.transport as t_mod

        assert not hasattr(t_mod, "open_client"), (
            "open_client should be removed in Phase 57-01 — "
            "open_backend is the new name"
        )


class TestMcpCase3StdioPathPrecheck:
    """§3.5 case 3 — --mcp-transport stdio with agent-brain-mcp not on PATH.

    The dispatcher must run ``shutil.which("agent-brain-mcp")`` BEFORE
    instantiating ``McpStdioBackend``. When ``shutil.which`` returns
    ``None``, the dispatcher raises a ``click.UsageError`` (exit 2) with
    the verbatim §3.5 wording.
    """

    def test_stdio_without_agent_brain_mcp_on_path_exits_2(
        self, clean_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The PATH precheck only runs AFTER the agent_brain_mcp.client
        # lazy import succeeds — so we need the package importable for
        # this test to exercise the precheck branch (not §3.5 case 1).
        pytest.importorskip("agent_brain_mcp.client")

        # The dispatcher imports the bare `shutil` module and calls
        # `shutil.which("agent-brain-mcp")`. Patch shutil.which at the
        # source so the precheck simulates a missing binary on PATH.
        monkeypatch.setattr("shutil.which", lambda cmd: None)

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--transport", "mcp", "--mcp-transport", "stdio", "query", "X"],
        )

        assert result.exit_code == 2, (
            f"expected exit code 2, got {result.exit_code}; "
            f"output={result.output!r}"
        )
        assert (
            "agent-brain-mcp not found on PATH; install agent-brain-mcp "
            "into the same Python environment"
        ) in result.output, (
            f"expected verbatim §3.5 case 3 wording; " f"output={result.output!r}"
        )
