"""Phase 0 smoke test — proves the package imports and exposes a version.

The version string drifts with each release train (10.0.7 → 10.1.0 →
10.1.2 → 10.2.x …) so we assert *shape*, not exact value, here.
Lockstep version checks live in the version-compat suite and in
``MIN_BACKEND_VERSION`` inside ``server.py``.
"""

import re

import agent_brain_mcp


def test_package_imports() -> None:
    version = agent_brain_mcp.__version__
    assert isinstance(version, str) and version, "missing __version__"
    # Semver-ish: at least major.minor.patch with optional pre-release.
    assert re.match(
        r"^\d+\.\d+\.\d+", version
    ), f"version {version!r} is not semver-shaped"
