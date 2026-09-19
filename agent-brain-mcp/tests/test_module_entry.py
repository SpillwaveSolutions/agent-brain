"""``python -m agent_brain_mcp`` must work: ``agent-brain mcp start`` spawns it."""

import subprocess
import sys


def test_python_dash_m_entry_point() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "agent_brain_mcp", "--help"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    assert "--transport" in proc.stdout
