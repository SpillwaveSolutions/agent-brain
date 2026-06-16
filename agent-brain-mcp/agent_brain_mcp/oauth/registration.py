"""CIMD (Client ID Metadata Document) fetch with SSRF control stack.

Phase 67 Plan 03.

This module implements the mandatory SSRF protection for the CIMD
registration flow defined in the design doc §"SSRF Mitigation (Mandatory)"
and CONTEXT.md §"Client registration + SSRF mitigation":

  1. ``is_blocked_ip`` — returns True for RFC-1918, loopback, and link-local
     addresses (unconditional block regardless of allowlist).
  2. ``validate_client_id_host`` — parses the ``client_id`` URL, checks the
     hostname against the configured allowlist, and unconditionally blocks IP
     literals in private/loopback/link-local ranges.
  3. ``fetch_client_metadata`` — orchestrates the full SSRF control stack:
       a. validate_client_id_host (allowlist + unconditional IP block)
       b. DNS resolution via ``socket.getaddrinfo``
       c. Post-resolution IP re-validation (DNS-rebinding mitigation)
       d. HTTP fetch with a ~5s timeout (slowloris guard)

DNS-rebinding mitigation
------------------------
A hostname-only allowlist is insufficient: an attacker can register
``evil.allowlisteddomain.com`` with DNS that temporarily resolves to
``169.254.169.254`` (AWS IMDS) — a classic DNS-rebinding attack. This module
mitigates it by:

  1. Resolving the hostname via ``socket.getaddrinfo`` BEFORE the HTTP fetch.
  2. Running ``is_blocked_ip`` over ALL resolved addresses.
  3. Raising ``RegistrationError400`` if ANY resolved address is blocked.

There is a small TOCTOU window: the DNS cache may be flushed between the
``getaddrinfo`` check and the TCP connection establishment. For the
single-user co-located deployment shape (Phase 67 Shape A) this window is
acceptable and consistent with the design doc's guidance:

  "The implementation MUST use a library or custom wrapper that performs
  post-resolution IP validation (e.g., a custom httpx transport that
  intercepts the connection attempt after DNS resolution and checks the IP)."

The resolve-then-validate approach chosen here is the cleanest testable form
(monkeypatch ``socket.getaddrinfo``). Phase 70's split AS/RS shape may tighten
this further if needed.

Blocked networks
----------------
``_BLOCKED_NETWORKS`` covers:
  - RFC 1918:     10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16
  - Loopback:     127.0.0.0/8 (IPv4), ::1/128 (IPv6)
  - Link-local:   169.254.0.0/16 (IPv4), fe80::/10 (IPv6)
  - Unique-local: fc00::/7 (IPv6)

Design doc: docs/plans/2026-06-14-mcp-v4-oauth-design.md
  §"Registration Policy: CIMD over DCR"
  §"SSRF Mitigation (Mandatory)"
"""

from __future__ import annotations

import socket
import urllib.parse
from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network, ip_address

import httpx

# ---------------------------------------------------------------------------
# Blocked network ranges (unconditional — design doc control #4)
# ---------------------------------------------------------------------------

_BLOCKED_NETWORKS: list[IPv4Network | IPv6Network] = [
    # RFC 1918 private ranges
    IPv4Network("10.0.0.0/8"),
    IPv4Network("172.16.0.0/12"),
    IPv4Network("192.168.0.0/16"),
    # Loopback
    IPv4Network("127.0.0.0/8"),
    IPv6Network("::1/128"),
    # Link-local
    IPv4Network("169.254.0.0/16"),
    IPv6Network("fe80::/10"),
    # IPv6 unique-local (fc00::/7)
    IPv6Network("fc00::/7"),
]


# ---------------------------------------------------------------------------
# Error type
# ---------------------------------------------------------------------------


class RegistrationError400(Exception):  # noqa: N818
    """Raised when a CIMD registration is rejected with a 400-class error.

    N818 suppressed: the "400" suffix signals the HTTP status rather than
    naming the error type, consistent with the RFC 7591 §3.2.2 shape.

    Shape: ``invalid_client_metadata`` per the OAuth 2.0 Dynamic Client
    Registration Protocol (RFC 7591 §3.2.2).

    Attributes:
        message: Human-readable description of why registration was rejected.
    """

    def __init__(self, message: str) -> None:
        """Initialize the error.

        Args:
            message: Human-readable reason for the rejection.
        """
        self.message = message
        super().__init__(message)


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def is_blocked_ip(ip: str | IPv4Address | IPv6Address) -> bool:
    """Return True if the IP is in a blocked (private/loopback/link-local) range.

    Checks two things (belt-and-suspenders per the design doc):

    1. Membership in ``_BLOCKED_NETWORKS`` (explicit CIDR list).
    2. Standard ``ip_address`` flags: ``is_private``, ``is_loopback``,
       ``is_link_local``.

    Either check being True means the IP is blocked.

    Args:
        ip: An IPv4 or IPv6 address as a string or ``ipaddress`` object.

    Returns:
        True if the IP is in a blocked range; False if it is a public address.
    """
    if isinstance(ip, str):
        try:
            parsed = ip_address(ip)
        except ValueError:
            # Unparseable → treat as blocked (safe default)
            return True
    else:
        parsed = ip

    # Belt: explicit CIDR list
    for network in _BLOCKED_NETWORKS:
        if parsed in network:
            return True

    # Suspenders: standard ipaddress flags
    return bool(parsed.is_private or parsed.is_loopback or parsed.is_link_local)


def validate_client_id_host(client_id_url: str, allowlist: list[str]) -> str:
    """Validate the ``client_id`` URL's hostname against the SSRF control gates.

    Implements design doc §"SSRF Mitigation (Mandatory)" controls #1-#4:

      1. Parse the URL; reject if empty, missing scheme, or missing hostname.
      2. If the hostname is an IP literal in a blocked range → ``RegistrationError400``
         (unconditional, even if the IP literal appears in the allowlist).
      3. If the hostname is not in the allowlist → ``RegistrationError400``.

    Note: control #4 (unconditional IP block) applies BEFORE the allowlist
    check (#3). Even if an operator accidentally adds a private IP literal to
    the allowlist, it is still rejected here.

    Args:
        client_id_url: The ``client_id`` URL string from the registration request.
        allowlist: List of allowed hostname strings from
            ``resolve_client_id_allowlist()``.

    Returns:
        The validated hostname string (for use in subsequent DNS resolution).

    Raises:
        RegistrationError400: If the URL is malformed, missing a scheme,
            has an empty hostname, the hostname is a blocked IP literal, or
            the hostname is not in the allowlist.
    """
    if not client_id_url:
        raise RegistrationError400(
            "client_id URL is empty — a valid HTTPS URL is required "
            "for CIMD registration."
        )

    parsed = urllib.parse.urlparse(client_id_url)

    if not parsed.scheme:
        raise RegistrationError400(
            f"client_id URL {client_id_url!r} has no scheme. "
            "A valid absolute URL (e.g. https://...) is required for CIMD."
        )

    hostname = parsed.hostname  # lowercased, strips brackets from IPv6 literals
    if not hostname:
        raise RegistrationError400(
            f"client_id URL {client_id_url!r} has no hostname. "
            "A valid absolute URL (e.g. https://...) is required for CIMD."
        )

    # Control #4: unconditional block for IP literals in private ranges
    # (the urlparse.hostname is already bracket-stripped for IPv6 literals)
    try:
        addr = ip_address(hostname)
        # hostname IS an IP literal
        if is_blocked_ip(addr):
            raise RegistrationError400(
                f"client_id URL hostname {hostname!r} is a blocked private/loopback/"
                "link-local IP address. CIMD fetch to private IPs is unconditionally "
                "rejected regardless of the allowlist."
            )
        # IP literal that is NOT in a blocked range (rare; still must pass allowlist)
    except ValueError:
        # Not an IP literal — proceed to allowlist check
        pass

    # Control #3: allowlist check
    if hostname not in allowlist:
        raise RegistrationError400(
            f"client_id hostname {hostname!r} is not in "
            "AGENT_BRAIN_OAUTH_CLIENT_ID_ALLOWLIST. "
            "Only pre-approved hostnames may initiate CIMD registration. "
            "Set AGENT_BRAIN_OAUTH_CLIENT_ID_ALLOWLIST to include this hostname."
        )

    return hostname


async def fetch_client_metadata(
    client_id_url: str,
    *,
    allowlist: list[str],
    timeout_s: float = 5.0,
) -> dict[str, object]:
    """Fetch the Client ID Metadata Document (CIMD) with full SSRF protection.

    Implements all five SSRF controls from the design doc
    §"SSRF Mitigation (Mandatory)":

      1. **Allowlist + unconditional IP block** via ``validate_client_id_host``.
      2. **DNS resolution** via ``socket.getaddrinfo`` (pre-fetch).
      3. **Post-resolution IP re-validation** (DNS-rebinding mitigation):
         every resolved IP is checked with ``is_blocked_ip`` before the
         HTTP fetch. If ANY resolved IP is blocked, the request is aborted.
      4. **~5s timeout** on the HTTP fetch (slowloris/DoS guard).

    If any control rejects the URL, the function raises ``RegistrationError400``
    before making any network connection (no SSRF exfiltration).

    TOCTOU note
    -----------
    There is a small window between the ``getaddrinfo`` check and the TCP
    connection establishment where DNS could be changed (DNS cache poisoning /
    TOCTOU). For the single-user co-located deployment shape (Shape A) this
    is acceptable — see module docstring for details.

    Args:
        client_id_url: The ``client_id`` URL to fetch metadata from.
        allowlist: List of allowed hostname strings (from
            ``config.resolve_client_id_allowlist()``).
        timeout_s: HTTP fetch timeout in seconds (~5s default per design doc).

    Returns:
        The parsed JSON metadata document as a plain ``dict``.

    Raises:
        RegistrationError400: If any SSRF control rejects the URL (allowlist,
            unconditional IP block, or DNS-rebinding post-resolution check).
        httpx.HTTPStatusError: If the CIMD fetch returns a non-2xx status.
        httpx.RequestError: On network errors during the fetch.
    """
    # Control #1 + #4: allowlist + unconditional IP block
    hostname = validate_client_id_host(client_id_url, allowlist)

    # Controls #2 + #3: DNS resolution + post-resolution IP re-validation
    # (DNS-rebinding mitigation)
    try:
        addr_infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise RegistrationError400(
            f"DNS resolution failed for client_id hostname {hostname!r}: {exc}. "
            "Cannot proceed with CIMD registration without resolving the hostname."
        ) from exc

    for addr_info in addr_infos:
        # addr_info is (family, type, proto, canonname, sockaddr)
        # sockaddr[0] is always the host string for both IPv4 and IPv6
        sockaddr = addr_info[4]
        resolved_ip = str(sockaddr[0])
        if is_blocked_ip(resolved_ip):
            raise RegistrationError400(
                f"DNS-rebinding mitigation: client_id hostname {hostname!r} "
                f"resolved to {resolved_ip!r} which is a "
                "private/loopback/link-local address. "
                "Registration rejected to prevent SSRF. "
                "This may indicate a DNS rebinding attack or misconfigured "
                "allowlist entry."
            )

    # Control #5: HTTP fetch with ~5s timeout
    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_s)) as client:
        response = await client.get(client_id_url)
        response.raise_for_status()
        result: dict[str, object] = response.json()
        return result
