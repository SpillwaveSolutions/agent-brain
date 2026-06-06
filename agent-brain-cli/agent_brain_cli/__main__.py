"""Entry point for ``python -m agent_brain_cli``.

Defers to the Click ``cli`` group. Added in Phase 57 Plan 02 so the
byte-equivalence contract test can invoke the CLI without depending
on the ``agent-brain`` console-script being installed on ``PATH``
in every test environment.
"""

from __future__ import annotations

from agent_brain_cli.cli import cli

if __name__ == "__main__":
    cli()
