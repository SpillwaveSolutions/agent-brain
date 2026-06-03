"""Phase 53 Plan 02 — :func:`validate_loopback_host` (HTTP-02).

Pins the loopback whitelist contract from CONTEXT decision D-08:

* Accept exactly ``{127.0.0.1, localhost, ::1}``.
* Reject everything else with a single exact contract message — no
  ``--allow-public-bind`` escape hatch, no per-host customization,
  no env-var override. Auth is the only acceptable gate for a
  non-loopback bind, and auth is v4 (OAUTH-01).

These are pure unit tests — no async, no sockets, no subprocesses.
The integration coverage that the validator gates a real
``run_http`` call BEFORE binding lives in ``test_http_listener.py``.
"""

from __future__ import annotations

import click
import pytest

from agent_brain_mcp.http import (
    ALLOWED_LOOPBACK_HOSTS,
    LOOPBACK_REJECTION_MESSAGE,
    validate_loopback_host,
)


class TestAcceptedHosts:
    """The three loopback variants pass without raising."""

    @pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1"])
    def test_loopback_variant_accepted(self, host: str) -> None:
        # No exception → host is on the whitelist.
        validate_loopback_host(host)

    def test_allowed_set_is_exactly_three_entries(self) -> None:
        """Belt-and-suspenders: pin the whitelist composition.

        If a future commit accidentally widens the whitelist (e.g.
        adds ``0.0.0.0`` in a "convenience" edit), this test fails
        loudly before the integration tests even run.
        """
        assert ALLOWED_LOOPBACK_HOSTS == frozenset({"127.0.0.1", "localhost", "::1"})


class TestRejectedHosts:
    """Everything else raises with the exact contract message."""

    @pytest.mark.parametrize(
        "host",
        [
            "0.0.0.0",  # ANY interface — the classic "expose me to the world"
            "10.0.0.5",  # private subnet but non-loopback
            "192.168.1.42",  # home/lab non-loopback
            "example.com",  # hostname pointing somewhere non-loopback
            "127.0.0.2",  # loopback-adjacent but not exactly 127.0.0.1
            "127.0.1.1",  # Debian-default localhost — still rejected
            "::",  # IPv6 ANY
            "",  # empty string — defensive against accidental defaulting
            "  ",  # whitespace-only — same
            "LOCALHOST",  # case mismatch — whitelist is case-sensitive
            "Localhost",
        ],
    )
    def test_non_loopback_host_rejected(self, host: str) -> None:
        with pytest.raises(click.ClickException) as exc_info:
            validate_loopback_host(host)
        # Exact-match the contract message. Substring-match would
        # tolerate accidental wording drift.
        assert exc_info.value.message == LOOPBACK_REJECTION_MESSAGE

    def test_rejection_uses_default_exit_code(self) -> None:
        """Plain ``ClickException`` (exit code 1) — NOT ``PortInUseError``.

        D-08 (loopback whitelist) and D-12 (port-in-use) are two
        distinct failure modes and Plan 02 surfaces them with
        distinct exit codes so callers (Plan 03's smoke harness;
        operators in shell pipelines) can route on ``$?``. This
        test pins the distinction: validate_loopback_host raises
        with the *generic* ClickException default.
        """
        with pytest.raises(click.ClickException) as exc_info:
            validate_loopback_host("0.0.0.0")
        # Plain ClickException — exit_code is 1, NOT 2 (PortInUseError
        # is exit 2). This guard prevents a future refactor from
        # collapsing the two error classes into one.
        assert exc_info.value.exit_code == 1


class TestContractMessageFormat:
    """The exact wording of the rejection message is part of the public contract."""

    def test_message_contains_loopback_set(self) -> None:
        # The literal set wording — operators grep for this in CI
        # logs to assert "yes, the host check fired."
        assert "{127.0.0.1, localhost, ::1}" in LOOPBACK_REJECTION_MESSAGE

    def test_message_mentions_v4_auth(self) -> None:
        """The message must explain WHY (auth is v4)."""
        assert "auth is deferred to v4" in LOOPBACK_REJECTION_MESSAGE

    def test_message_warns_about_public_bind(self) -> None:
        """The message must steer operators away from non-loopback."""
        assert "unsafe in v2" in LOOPBACK_REJECTION_MESSAGE
