"""Phase 0 smoke test — proves the package imports and is on the lockstep version.

Real test suites land in Phase 1 (paths, permissions, client) and Phase 5
(adversarial security).
"""

import agent_brain_uds


def test_package_imports() -> None:
    assert agent_brain_uds.__version__ == "10.0.7"
