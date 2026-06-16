"""Phase 67 Plan 01: OAuth dependency import smoke test + SDK drift gate.

Verifies that:
1. All mcp.server.auth OAuth symbols are importable under mcp ^1.27.2.
2. PyJWT[crypto], authlib, and pwdlib[argon2] install and import correctly.
3. The project's own modules (server, http, client, subscriptions) still import
   cleanly post-bump — no breaking API drift from the 1.12→1.27.2 SDK jump.
4. The create_auth_routes() signature still accepts ``provider`` and ``issuer_url``
   parameters (guard against SDK signature drift between minor versions).

These are pure import/introspection tests — no network, no subprocess, no I/O.
asyncio_mode = "auto" per pyproject.ini_options; sync functions are fine here.

Phase 67 Plan 01 context:
  .planning/phases/67-co-located-as-rs-middleware/67-01-PLAN.md
"""

from __future__ import annotations

import inspect

# ---------------------------------------------------------------------------
# Task 2 — Group 1: mcp.server.auth OAuth symbols
# ---------------------------------------------------------------------------


def test_oauth_provider_imports() -> None:
    """All required OAuth provider symbols import from mcp.server.auth.provider.

    Verifies the complete set of types that Phase 67 plans 02-04 depend on:
    OAuthAuthorizationServerProvider, TokenVerifier, AccessToken,
    AuthorizationCode, RefreshToken, AuthorizationParams.
    """
    from mcp.server.auth.provider import (  # noqa: F401
        AccessToken,
        AuthorizationCode,
        AuthorizationParams,
        OAuthAuthorizationServerProvider,
        RefreshToken,
        TokenVerifier,
    )


def test_oauth_routes_imports() -> None:
    """All required OAuth route symbols import from mcp.server.auth.routes.

    Verifies create_auth_routes, ClientRegistrationOptions, and RevocationOptions
    — the route-builder API that wires /authorize, /token, /register.
    """
    from mcp.server.auth.routes import (  # noqa: F401
        ClientRegistrationOptions,
        RevocationOptions,
        create_auth_routes,
    )


def test_oauth_middleware_imports() -> None:
    """RequireAuthMiddleware and BearerAuthBackend import from bearer_auth.

    These are the two RS-side components that Phase 67 wraps around the /mcp
    Mount to enforce token validation.
    """
    from mcp.server.auth.middleware.bearer_auth import (  # noqa: F401
        BearerAuthBackend,
        RequireAuthMiddleware,
    )


# ---------------------------------------------------------------------------
# Task 2 — Group 2: OAuth runtime library imports
# ---------------------------------------------------------------------------


def test_pyjwt_crypto_extra_installed() -> None:
    """PyJWT[crypto] is installed: jwt.algorithms.RSAAlgorithm is accessible.

    The [crypto] extra installs the ``cryptography`` package and registers
    RSAAlgorithm in PyJWT's algorithm registry. This proves the extra was
    installed, not just the base pyjwt package.
    """
    import jwt

    assert hasattr(jwt, "algorithms"), "jwt.algorithms module missing"
    rsa_alg = getattr(jwt.algorithms, "RSAAlgorithm", None)
    assert rsa_alg is not None, (
        "jwt.algorithms.RSAAlgorithm not found — PyJWT[crypto] extra may not "
        "be installed (requires the 'cryptography' package)"
    )


def test_authlib_imports() -> None:
    """authlib package imports successfully.

    Phase 67 uses authlib for OAuth 2.1 grant-handler logic composable with
    the mcp SDK OAuthAuthorizationServerProvider.
    """
    import authlib  # noqa: F401


def test_pwdlib_argon2_extra_installed() -> None:
    """pwdlib[argon2] is installed: Argon2Hasher is accessible.

    The [argon2] extra installs argon2-cffi and registers the hasher. This
    proves the extra was installed (not just the base pwdlib package).
    """
    from pwdlib.hashers.argon2 import Argon2Hasher  # noqa: F401


# ---------------------------------------------------------------------------
# Task 2 — Group 3: Project module imports (SDK-drift gate)
# ---------------------------------------------------------------------------


def test_agent_brain_mcp_server_imports() -> None:
    """agent_brain_mcp.server imports cleanly post-SDK-bump.

    This module uses mcp.server.lowlevel, mcp.server.session,
    mcp.shared.session, mcp.shared.version — the surfaces most at risk from
    the 1.12→1.27.2 version jump.
    """
    import agent_brain_mcp.server  # noqa: F401


def test_agent_brain_mcp_http_imports() -> None:
    """agent_brain_mcp.http imports cleanly post-SDK-bump.

    This module uses StreamableHTTPSessionManager and TransportSecuritySettings
    from the mcp SDK HTTP transport surface.
    """
    import agent_brain_mcp.http  # noqa: F401


def test_agent_brain_mcp_client_imports() -> None:
    """agent_brain_mcp.client imports cleanly post-SDK-bump.

    This module uses mcp.client.streamable_http and mcp.client.stdio client
    transports.
    """
    import agent_brain_mcp.client  # noqa: F401


def test_agent_brain_mcp_subscriptions_imports() -> None:
    """agent_brain_mcp.subscriptions imports cleanly post-SDK-bump.

    The subscriptions package binds to the resource-notification surface of
    the SDK (send_resource_updated etc.).
    """
    import agent_brain_mcp.subscriptions  # noqa: F401


# ---------------------------------------------------------------------------
# Task 2 — Group 4: SDK signature guard (drift sentinel)
# ---------------------------------------------------------------------------


def test_create_auth_routes_signature_has_provider_and_issuer_url() -> None:
    """create_auth_routes() has ``provider`` and ``issuer_url`` parameters.

    Guards against SDK signature drift between minor versions. If the mcp SDK
    renames or removes these parameters, Phase 67's build_asgi_app() wiring
    will break at runtime — this test surfaces it immediately at the module
    level.

    Parameters inspected via inspect.signature to avoid an actual call
    (which would require a real provider instance and a valid issuer URL).
    """
    from mcp.server.auth.routes import create_auth_routes

    params = inspect.signature(create_auth_routes).parameters
    assert "provider" in params, (
        "create_auth_routes() missing 'provider' parameter — SDK API drift detected. "
        "Check mcp.server.auth.routes in the installed mcp version and update "
        "the Phase 67 wiring in build_asgi_app() accordingly."
    )
    assert "issuer_url" in params, (
        "create_auth_routes() missing 'issuer_url' parameter — SDK API drift detected. "
        "Check mcp.server.auth.routes in the installed mcp version and update "
        "the Phase 67 wiring in build_asgi_app() accordingly."
    )
