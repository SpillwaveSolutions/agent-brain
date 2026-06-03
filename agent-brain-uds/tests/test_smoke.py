"""Phase 0 smoke test — proves the package imports and exposes a version string.

Real test suites land in Phase 1 (paths, permissions, client) and Phase 5
(adversarial security).

The version assertion is intentionally lockstep-loose (matches the monorepo
version-pattern, not a specific release) so the smoke test does not need to be
edited on every PyPI bump. Lockstep versioning is enforced by the release
workflow and by `MIN_BACKEND_VERSION` checks elsewhere.
"""

import re

import agent_brain_uds


def test_package_imports() -> None:
    # Lockstep version pattern: MAJOR.MINOR.PATCH (no pre-release suffix).
    # Exact version is enforced by the release workflow; the smoke test only
    # confirms the attribute exists and has the canonical shape.
    assert isinstance(agent_brain_uds.__version__, str)
    assert re.match(r"^\d+\.\d+\.\d+$", agent_brain_uds.__version__), (
        f"__version__ {agent_brain_uds.__version__!r} does not match the "
        "MAJOR.MINOR.PATCH lockstep pattern enforced by the release workflow."
    )
