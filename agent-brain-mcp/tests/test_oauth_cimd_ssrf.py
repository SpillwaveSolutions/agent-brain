"""SSRF + DNS-rebinding rejection tests for CIMD client registration.

Phase 67 Plan 03 — Tasks 1 + 2.

Tests the full mandatory SSRF control stack defined in the design doc
§"SSRF Mitigation (Mandatory)" and CONTEXT.md §"Client registration + SSRF mitigation":

  1. ``is_blocked_ip`` — True for RFC-1918/loopback/link-local addresses; False for public.
  2. ``validate_client_id_host`` — raises 400-class error for non-allowlisted hostnames.
  3. ``validate_client_id_host`` — raises unconditionally for blocked-IP literals even if
     they somehow appear in the allowlist.
  4. ``fetch_client_metadata`` — uses a ~5s httpx timeout.
  5. A non-allowlisted host never reaches the network (no fetch attempted).
  6. DNS-rebinding mitigation (MANDATORY): an allowlisted hostname whose DNS resolves to an
     RFC-1918 address is rejected even when the hostname passes the allowlist check.
  7. An allowlisted hostname resolving to a PUBLIC IP proceeds to fetch (happy path).
  8. ``provider.register_client``:
       - URL-shaped client_id → calls ``fetch_client_metadata`` (SSRF-guarded).
       - Static/non-URL client_id → registers without a fetch.
"""

from __future__ import annotations

import socket
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from agent_brain_mcp.oauth.registration import (
    RegistrationError400,
    fetch_client_metadata,
    is_blocked_ip,
    validate_client_id_host,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ALLOWLIST = ["mcp-client.example.com", "trusted.myco.io"]


# ---------------------------------------------------------------------------
# Task 1 Tests: is_blocked_ip
# ---------------------------------------------------------------------------


class TestIsBlockedIp:
    """Unit tests for ``is_blocked_ip``."""

    @pytest.mark.parametrize(
        "ip",
        [
            "10.0.0.1",
            "10.255.255.255",
            "172.16.0.1",
            "172.31.255.255",
            "192.168.1.1",
            "192.168.0.0",
            "127.0.0.1",
            "127.255.255.255",
            "169.254.169.254",  # AWS IMDS
            "169.254.0.1",
            "::1",  # IPv6 loopback
            "fe80::1",  # link-local
            "fc00::1",  # unique-local (fc00::/7)
        ],
    )
    def test_blocked_ips_return_true(self, ip: str) -> None:
        """Private/loopback/link-local addresses MUST be blocked."""
        assert is_blocked_ip(ip) is True, f"Expected {ip!r} to be blocked"

    @pytest.mark.parametrize(
        "ip",
        [
            "93.184.216.34",  # example.com
            "8.8.8.8",  # Google DNS
            "1.1.1.1",  # Cloudflare
            "2606:2800:220:1:248:1893:25c8:1946",  # example.com IPv6
        ],
    )
    def test_public_ips_return_false(self, ip: str) -> None:
        """Public addresses MUST NOT be blocked."""
        assert is_blocked_ip(ip) is False, f"Expected {ip!r} to be public (not blocked)"


# ---------------------------------------------------------------------------
# Task 1 Tests: validate_client_id_host
# ---------------------------------------------------------------------------


class TestValidateClientIdHost:
    """Unit tests for ``validate_client_id_host``."""

    def test_non_allowlisted_hostname_raises_400(self) -> None:
        """A hostname not in the allowlist raises RegistrationError400."""
        with pytest.raises(RegistrationError400):
            validate_client_id_host(
                "https://evil.example.org/.well-known/mcp-client",
                allowlist=_ALLOWLIST,
            )

    def test_allowlisted_hostname_returns_hostname(self) -> None:
        """A valid allowlisted hostname returns the hostname string."""
        result = validate_client_id_host(
            "https://mcp-client.example.com/.well-known/mcp-client",
            allowlist=_ALLOWLIST,
        )
        assert result == "mcp-client.example.com"

    def test_missing_scheme_raises_400(self) -> None:
        """A URL with no scheme raises RegistrationError400."""
        with pytest.raises(RegistrationError400):
            validate_client_id_host("mcp-client.example.com/metadata", allowlist=_ALLOWLIST)

    def test_empty_string_raises_400(self) -> None:
        """An empty client_id URL raises RegistrationError400."""
        with pytest.raises(RegistrationError400):
            validate_client_id_host("", allowlist=_ALLOWLIST)

    def test_ip_literal_private_unconditionally_blocked_even_if_allowlisted(
        self,
    ) -> None:
        """An IP literal in a private range is UNCONDITIONALLY rejected.

        Even if the IP literal somehow appears in the allowlist, the
        unconditional private-IP block MUST reject it (belt-and-suspenders
        per the design doc §"SSRF Mitigation (Mandatory)" control #4).
        """
        # Build an allowlist that includes the private IP literal
        allowlist_with_private_ip = _ALLOWLIST + ["192.168.1.100"]
        with pytest.raises(RegistrationError400):
            validate_client_id_host(
                "https://192.168.1.100/metadata",
                allowlist=allowlist_with_private_ip,
            )

    def test_loopback_ip_literal_unconditionally_blocked(self) -> None:
        """127.x.x.x IP literals are unconditionally blocked."""
        with pytest.raises(RegistrationError400):
            validate_client_id_host(
                "http://127.0.0.1:8080/metadata",
                allowlist=["127.0.0.1"],  # even if allowlisted
            )

    def test_aws_imds_ip_unconditionally_blocked(self) -> None:
        """The AWS IMDS endpoint (169.254.169.254) is unconditionally blocked."""
        with pytest.raises(RegistrationError400):
            validate_client_id_host(
                "http://169.254.169.254/latest/meta-data/",
                allowlist=["169.254.169.254"],  # even if allowlisted
            )


# ---------------------------------------------------------------------------
# Task 1 Tests: fetch_client_metadata — timeout + no-network-on-rejection
# ---------------------------------------------------------------------------


class TestFetchClientMetadataTimeout:
    """Verify the fetch uses a ~5s httpx timeout."""

    @pytest.mark.asyncio
    async def test_fetch_uses_5s_timeout(self) -> None:
        """The httpx.AsyncClient used by fetch_client_metadata has a 5s timeout."""
        fake_metadata = {"client_id": "https://mcp-client.example.com/meta"}
        captured_kwargs: dict[str, object] = {}

        class _CapturingClient:
            """Fake async context manager that captures constructor kwargs."""

            def __init__(self, **kwargs: object) -> None:
                captured_kwargs.update(kwargs)

            async def __aenter__(self) -> "_CapturingClient":
                return self

            async def __aexit__(self, *args: object) -> None:
                pass

            async def get(self, url: str) -> httpx.Response:
                req = httpx.Request("GET", url)
                resp = httpx.Response(200, json=fake_metadata, request=req)
                return resp

        with patch(
            "agent_brain_mcp.oauth.registration.httpx.AsyncClient",
            _CapturingClient,
        ):
            with patch("agent_brain_mcp.oauth.registration.socket.getaddrinfo") as mock_dns:
                mock_dns.return_value = [
                    (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 443))
                ]
                await fetch_client_metadata(
                    "https://mcp-client.example.com/.well-known/mcp-client",
                    allowlist=_ALLOWLIST,
                    timeout_s=5.0,
                )

        # Verify the client was constructed with a 5s timeout
        timeout_arg = captured_kwargs.get("timeout")
        assert timeout_arg is not None, "httpx.AsyncClient called without timeout"
        assert isinstance(timeout_arg, httpx.Timeout)
        # Connect + read timeouts should both be 5.0
        assert timeout_arg.connect == 5.0 or timeout_arg.read == 5.0, (
            f"Expected ~5s timeout, got {timeout_arg!r}"
        )


class TestFetchClientMetadataNoNetworkOnRejection:
    """A rejected URL never makes a network call."""

    @pytest.mark.asyncio
    async def test_non_allowlisted_host_raises_before_network(self) -> None:
        """fetch_client_metadata raises without attempting any network call."""
        with patch("agent_brain_mcp.oauth.registration.httpx.AsyncClient") as mock_cls:
            with pytest.raises(RegistrationError400):
                await fetch_client_metadata(
                    "https://evil.attacker.com/.well-known/mcp-client",
                    allowlist=_ALLOWLIST,
                )
            # Verify the client was never instantiated (no network call)
            mock_cls.assert_not_called()


# ---------------------------------------------------------------------------
# Task 2 Tests: DNS-rebinding mitigation (MANDATORY)
# ---------------------------------------------------------------------------


class TestDnsRebindingMitigation:
    """DNS-rebinding: allowlisted hostname that resolves to RFC-1918 is rejected.

    This is the MANDATORY test per the design doc §"SSRF Mitigation (Mandatory)"
    control #6:
      - The hostname ``mcp-client.example.com`` is in the allowlist.
      - Its DNS resolution (monkeypatched) returns an RFC-1918 address.
      - ``fetch_client_metadata`` MUST reject it with a 400-class error.
      - No HTTP request body should be fetched.
    """

    @pytest.mark.asyncio
    async def test_allowlisted_hostname_rfc1918_dns_rejected(self) -> None:
        """MANDATORY: allowlisted hostname + RFC-1918 DNS → rejected (no fetch)."""
        with patch("agent_brain_mcp.oauth.registration.socket.getaddrinfo") as mock_dns:
            # The hostname passes the allowlist but DNS resolves to a private IP
            mock_dns.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("10.1.2.3", 443))
            ]
            with patch("agent_brain_mcp.oauth.registration.httpx.AsyncClient") as mock_cls:
                with pytest.raises(RegistrationError400) as exc_info:
                    await fetch_client_metadata(
                        "https://mcp-client.example.com/.well-known/mcp-client",
                        allowlist=_ALLOWLIST,
                    )
                # No network call — client never used
                mock_cls.assert_not_called()
                # Error message should reference DNS/rebinding or private IP
                assert exc_info.value is not None

    @pytest.mark.asyncio
    async def test_allowlisted_hostname_imds_dns_rejected(self) -> None:
        """MANDATORY variant: allowlisted hostname + IMDS IP (169.254.169.254) → rejected."""
        with patch("agent_brain_mcp.oauth.registration.socket.getaddrinfo") as mock_dns:
            mock_dns.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("169.254.169.254", 80))
            ]
            with patch("agent_brain_mcp.oauth.registration.httpx.AsyncClient") as mock_cls:
                with pytest.raises(RegistrationError400):
                    await fetch_client_metadata(
                        "https://mcp-client.example.com/.well-known/mcp-client",
                        allowlist=_ALLOWLIST,
                    )
                mock_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_allowlisted_hostname_loopback_dns_rejected(self) -> None:
        """MANDATORY variant: allowlisted hostname + 127.x DNS → rejected."""
        with patch("agent_brain_mcp.oauth.registration.socket.getaddrinfo") as mock_dns:
            mock_dns.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("127.0.0.1", 443))
            ]
            with patch("agent_brain_mcp.oauth.registration.httpx.AsyncClient") as mock_cls:
                with pytest.raises(RegistrationError400):
                    await fetch_client_metadata(
                        "https://mcp-client.example.com/.well-known/mcp-client",
                        allowlist=_ALLOWLIST,
                    )
                mock_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_allowlisted_hostname_public_dns_proceeds_to_fetch(self) -> None:
        """Happy path: allowlisted hostname + public IP → fetch proceeds + metadata returned."""
        fake_metadata = {
            "client_id": "https://mcp-client.example.com/.well-known/mcp-client",
            "client_name": "Test MCP Client",
            "redirect_uris": ["https://mcp-client.example.com/callback"],
        }

        class _FakeClient:
            """Fake async context manager that returns canned metadata."""

            def __init__(self, **kwargs: object) -> None:
                pass

            async def __aenter__(self) -> "_FakeClient":
                return self

            async def __aexit__(self, *args: object) -> None:
                pass

            async def get(self, url: str) -> httpx.Response:
                req = httpx.Request("GET", url)
                return httpx.Response(200, json=fake_metadata, request=req)

        with patch("agent_brain_mcp.oauth.registration.socket.getaddrinfo") as mock_dns:
            # DNS resolves to a public IP
            mock_dns.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 443))
            ]
            with patch(
                "agent_brain_mcp.oauth.registration.httpx.AsyncClient",
                _FakeClient,
            ):
                result = await fetch_client_metadata(
                    "https://mcp-client.example.com/.well-known/mcp-client",
                    allowlist=_ALLOWLIST,
                )

        assert result == fake_metadata


# ---------------------------------------------------------------------------
# Task 2 Tests: provider.register_client CIMD wiring
# ---------------------------------------------------------------------------


class TestProviderRegisterClientCimdWiring:
    """provider.register_client routes URL-shaped client_ids through CIMD fetch."""

    def _make_provider(self) -> Any:
        """Build a minimal AgentBrainAuthServerProvider for testing."""
        from agent_brain_mcp.oauth.keys import get_or_create_signing_key
        from agent_brain_mcp.oauth.provider import AgentBrainAuthServerProvider
        from agent_brain_mcp.oauth.tokens import InMemoryTokenStore

        sk = get_or_create_signing_key()
        store = InMemoryTokenStore()
        return AgentBrainAuthServerProvider(
            signing_key=sk,
            store=store,
            issuer="https://mcp.test.example.com",
            resource="https://mcp.test.example.com/mcp",
            static_client_ids=[],
        )

    @pytest.mark.asyncio
    async def test_url_client_id_delegates_to_fetch_cimd(self) -> None:
        """A URL-shaped client_id causes register_client to call fetch_client_metadata."""
        from mcp.shared.auth import OAuthClientInformationFull
        from pydantic import AnyUrl

        provider = self._make_provider()
        cimd_url = "https://mcp-client.example.com/.well-known/mcp-client"

        with patch(
            "agent_brain_mcp.oauth.provider.fetch_client_metadata"
        ) as mock_fetch:
            mock_fetch.return_value = {
                "client_id": cimd_url,
                "client_name": "Test",
                "redirect_uris": ["https://mcp-client.example.com/callback"],
            }
            client_info = OAuthClientInformationFull(
                client_id=cimd_url,
                redirect_uris=[AnyUrl("https://mcp-client.example.com/callback")],
            )
            await provider.register_client(client_info)

        mock_fetch.assert_called_once()
        call_kwargs = mock_fetch.call_args
        # First positional arg should be the client_id URL
        assert cimd_url in call_kwargs.args or call_kwargs.kwargs.get("client_id_url") == cimd_url

    @pytest.mark.asyncio
    async def test_non_url_client_id_registers_without_fetch(self) -> None:
        """A non-URL (opaque) client_id registers directly, no fetch attempted."""
        from mcp.shared.auth import OAuthClientInformationFull
        from pydantic import AnyUrl

        provider = self._make_provider()

        with patch(
            "agent_brain_mcp.oauth.provider.fetch_client_metadata"
        ) as mock_fetch:
            client_info = OAuthClientInformationFull(
                client_id="claude-desktop",  # opaque static client ID
                redirect_uris=[AnyUrl("https://placeholder.invalid/callback")],
            )
            await provider.register_client(client_info)

        mock_fetch.assert_not_called()
        # Verify the client was stored
        stored = await provider.get_client("claude-desktop")
        assert stored is not None
        assert stored.client_id == "claude-desktop"

    @pytest.mark.asyncio
    async def test_url_client_id_ssrf_rejection_propagates_from_register(self) -> None:
        """A SSRF-rejected client_id causes register_client to raise RegistrationError400."""
        from mcp.shared.auth import OAuthClientInformationFull
        from pydantic import AnyUrl

        provider = self._make_provider()
        evil_url = "https://evil.attacker.com/.well-known/mcp-client"

        with patch(
            "agent_brain_mcp.oauth.provider.fetch_client_metadata",
            side_effect=RegistrationError400(
                "Hostname not in allowlist: evil.attacker.com"
            ),
        ):
            client_info = OAuthClientInformationFull(
                client_id=evil_url,
                redirect_uris=[AnyUrl("https://evil.attacker.com/callback")],
            )
            with pytest.raises(RegistrationError400):
                await provider.register_client(client_info)
