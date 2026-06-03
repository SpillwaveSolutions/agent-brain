"""Phase 0 smoke test — proves the package imports and exposes a version.

The version string drifts with each release train (10.0.7 → 10.1.0 →
10.1.2 → 10.2.x …) so we assert *shape*, not exact value, here.
Lockstep version checks live in the version-compat suite and in
``MIN_BACKEND_VERSION`` inside ``server.py``.

Phase 53 Plan 01 adds a second assertion: the
``build_server(transport=)`` deprecation alias must continue to route
to ``backend_transport`` without breaking the stdio smoke. This pins
that the rename in Plan 01 didn't accidentally drop the legacy kwarg.
"""

from __future__ import annotations

import re
import warnings

import httpx

import agent_brain_mcp
from agent_brain_mcp.server import build_server


def test_package_imports() -> None:
    version = agent_brain_mcp.__version__
    assert isinstance(version, str) and version, "missing __version__"
    # Semver-ish: at least major.minor.patch with optional pre-release.
    assert re.match(
        r"^\d+\.\d+\.\d+", version
    ), f"version {version!r} is not semver-shaped"


def test_build_server_legacy_transport_kwarg_still_constructs(
    fake_httpx_client: httpx.Client,
) -> None:
    """Phase 53 Plan 01: legacy ``transport=`` kwarg keeps working
    (emits :class:`DeprecationWarning`, routes to
    ``backend_transport``). Smoke-level guard that the rename in
    ``server.py`` didn't silently drop the alias path used by
    long-tail callers.
    """
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        server, _ = build_server(fake_httpx_client, transport="http")

    # The wrapper attached both axis labels — backend mirrors the
    # legacy kwarg's value, listen falls back to the documented default.
    assert server._agent_brain_backend_transport == "http"
    assert server._agent_brain_listen_transport == "stdio"
    # The DeprecationWarning was actually emitted (not swallowed).
    dep_warnings = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert any("transport=" in str(w.message) for w in dep_warnings), (
        "expected DeprecationWarning mentioning transport= alias; "
        f"got: {[str(w.message) for w in caught]}"
    )
