"""Phase 53 Plan 01 — CLI surface for the new ``--transport`` flag.

These tests pin the Click contract added in Plan 01:

* ``--transport [stdio|http]`` (case-insensitive Choice, default
  ``stdio``).
* ``--host TEXT`` default ``127.0.0.1``. Loopback whitelist enforcement
  lives in Plan 02 — this plan only plumbs the value through.
* ``--port INTEGER`` with :class:`click.IntRange(1, 65535)` validation.

The tests use Click's :class:`CliRunner` to invoke the CLI in-process.
For the dispatch-passthrough cases, ``asyncio.run`` is monkey-patched
to capture the awaitable's kwargs without actually awaiting
:func:`main_async` — that keeps the test scoped to "did Click hand the
flag through correctly?" and leaves dispatch correctness to
:mod:`tests.test_dispatch`.

Decision references:
    * D-02 — default stdio; AGENT_BRAIN_MCP_TRANSPORT NOT honored.
    * D-03 — defaults for host/port.
    * D-11 — Click rejects invalid transport via the standard
      ``not one of`` message.
"""

from __future__ import annotations

from typing import Any

import pytest
from click.testing import CliRunner

from agent_brain_mcp.cli import main


class TestHelpSurface:
    """``--help`` advertises the new flags so operators discover them."""

    def test_help_lists_transport_option(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0, result.output
        # Click renders Choice as ``[stdio|http]`` (case-insensitive
        # Choice still prints the canonical case).
        assert "--transport" in result.output
        assert "[stdio|http]" in result.output

    def test_help_lists_host_option(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "--host" in result.output
        # show_default=True so the default is in the help text.
        assert "127.0.0.1" in result.output

    def test_help_lists_port_option(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "--port" in result.output
        # Default 8765 is documented in the help.
        assert "8765" in result.output


class TestTransportRejection:
    """Click's :class:`Choice` rejects unknown transports loudly."""

    def test_transport_bogus_exits_non_zero(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["--transport", "bogus"])
        assert result.exit_code != 0
        # Click's standard usage-error wording. ``--transport`` is a
        # ``click.Choice``; its rejection message contains ``not one
        # of`` and the allowed list. Spelling varies slightly across
        # Click versions; the substring assertion is intentionally
        # loose on quoting.
        lowered = result.output.lower()
        assert "not one of" in lowered or "invalid value" in lowered
        # Both choices must appear in the rejection message.
        assert "stdio" in lowered
        assert "http" in lowered


class TestPortRange:
    """``--port`` is :class:`click.IntRange(1, 65535)`."""

    def test_port_zero_rejected(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["--port", "0"])
        assert result.exit_code != 0
        # Click's IntRange rejection mentions the boundary. We only
        # assert non-zero exit + that ``--port`` is named in the error
        # — the exact phrasing of "not in range" varies by Click
        # version (8.1.x vs 8.2.x).
        assert "--port" in result.output or "port" in result.output.lower()

    def test_port_too_large_rejected(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["--port", "65536"])
        assert result.exit_code != 0


class TestDispatchPassthrough:
    """Default + explicit flag values reach :func:`main_async` unchanged.

    ``asyncio.run`` is monkey-patched to capture the awaitable's
    underlying kwargs without driving the coroutine. The point of these
    tests is "Click pipes the flag through" — actual dispatch
    correctness is owned by :mod:`tests.test_dispatch`.
    """

    @pytest.fixture
    def captured_kwargs(self, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
        """Replace ``asyncio.run`` so the coroutine surrenders its
        kwargs instead of being scheduled. Returns a dict the test
        body inspects after :class:`CliRunner` invocation.
        """
        captured: dict[str, Any] = {}

        def _fake_main_async(**kwargs: Any) -> None:
            # Return a no-op coroutine so the existing asyncio.run
            # signature (which expects an awaitable) doesn't blow up.
            # The actual capture happens BEFORE the coroutine is
            # created by intercepting main_async itself.
            captured.update(kwargs)

            async def _noop() -> None:
                return None

            return _noop()  # type: ignore[return-value]

        # Patch the symbol that ``cli.main`` imported at module load.
        # Re-importing in the runner subprocess isn't enough; the
        # CliRunner runs in-process so monkeypatching the cli module's
        # namespace is the right scope.
        monkeypatch.setattr("agent_brain_mcp.cli.main_async", _fake_main_async)

        # Also replace asyncio.run with a synchronous awaiter so the
        # _noop() coroutine returned above doesn't trigger
        # ``coroutine was never awaited`` warnings. We just throw the
        # coroutine away (close it) since the kwargs are already in
        # ``captured``.
        def _fake_asyncio_run(coro: Any) -> None:
            coro.close()

        monkeypatch.setattr("agent_brain_mcp.cli.asyncio.run", _fake_asyncio_run)
        return captured

    def test_default_invocation_passes_transport_stdio(
        self, captured_kwargs: dict[str, Any]
    ) -> None:
        runner = CliRunner()
        result = runner.invoke(main, [])
        assert result.exit_code == 0, result.output
        assert captured_kwargs["transport"] == "stdio"
        assert captured_kwargs["host"] == "127.0.0.1"
        assert captured_kwargs["port"] == 8765

    def test_explicit_http_with_custom_port(
        self, captured_kwargs: dict[str, Any]
    ) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["--transport", "http", "--port", "9999"])
        assert result.exit_code == 0, result.output
        assert captured_kwargs["transport"] == "http"
        assert captured_kwargs["port"] == 9999
        # --host left as default — value propagates verbatim.
        assert captured_kwargs["host"] == "127.0.0.1"

    def test_transport_is_case_insensitive(
        self, captured_kwargs: dict[str, Any]
    ) -> None:
        """Click's ``Choice(case_sensitive=False)`` normalizes the value
        to lowercase. Phase 53's CLI uses the case-insensitive form so
        ``--transport HTTP`` is accepted and surfaces as ``"http"``.
        """
        runner = CliRunner()
        result = runner.invoke(main, ["--transport", "HTTP"])
        assert result.exit_code == 0, result.output
        # Click normalizes the choice — ``case_sensitive=False`` returns
        # the value in the case it was declared (``"http"``).
        assert captured_kwargs["transport"] == "http"

    def test_custom_host_value_passes_through(
        self, captured_kwargs: dict[str, Any]
    ) -> None:
        """Plan 01 plumbs ``--host`` through verbatim — Plan 02 layers
        on the loopback whitelist enforcement. So Plan 01 must NOT
        reject non-loopback hosts at the CLI parse step; the value
        just rides into ``main_async`` unchanged.
        """
        runner = CliRunner()
        result = runner.invoke(main, ["--transport", "http", "--host", "localhost"])
        assert result.exit_code == 0, result.output
        assert captured_kwargs["host"] == "localhost"
