"""Phase 0 smoke test — proves the package imports and is on the lockstep version.

Real test suites land in Phase 4 (initialize, tools, resources, prompts) and
Phase 5 (error mapping, cancellation).
"""

import agent_brain_mcp


def test_package_imports() -> None:
    assert agent_brain_mcp.__version__ == "10.0.7"
