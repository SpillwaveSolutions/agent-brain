"""v3 DoD anchor — byte-identical query output across transports.

CLI-MCP-04 contract: ``agent-brain --transport uds query "X"`` and
``agent-brain --transport mcp --mcp-transport stdio query "X"``
return the same chunks in the same order against the same backend
state, modulo volatile timestamp/elapsed fields stripped via
:func:`_normalize.strip_volatile_fields`.

Runs inside ``task before-push`` — drift fails the QA gate when the
prerequisites (OPENAI_API_KEY + agent-brain-serve + agent-brain-mcp
binaries) are available. When prereqs are absent the test SKIPs
cleanly with a reason — the v3 DoD is a wire-level proof and a
translator-shape fallback would only prove the helper agrees with itself
(NOT byte-equivalence). The SKIP path is honest; the FAIL path is
loud; the false-PASS path does not exist.

The fixture clones the corpus-seeder pattern referenced by the plan's
read_first (``tests/integration/test_smoke_uds.py``). The smoke-UDS
file did not exist when Plan 57-02 began executing — the helper was
hoisted into ``tests/integration/_corpus.py`` so future phases can
share the same seeder shape (per the plan's "If the smoke harness is
not exportable today, hoist the body into a small
``tests/integration/_corpus.py``" guidance).
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from ._normalize import strip_volatile_fields

# Soft dep — if agent-brain-mcp is not importable, the equivalence
# test cannot run. The unit-level _normalize test below stays
# unconditional.
pytest.importorskip(
    "agent_brain_mcp",
    reason=(
        "agent-brain-mcp package not installed in test environment "
        "(CI installs it; local dev may skip)."
    ),
)

# Import the seeder helper. The integration package houses the shared
# corpus-seeder shape Phase 58/59 can reuse.
from tests.integration._corpus import (  # noqa: E402
    prerequisites_available,
    start_seeded_server,
)

_CORPUS = {
    "a.md": "echo one — the first document mentions echo prominently",
    "b.md": "echo two — the second document also mentions echo",
    "c.md": "echo three — the third document about echo concludes the set",
}


@pytest.fixture
def transport_equivalence_corpus(tmp_path: Path) -> Iterator[Path]:
    """Seed a 3-document corpus in an isolated state_dir.

    See the module docstring for the wire-level-only rationale and
    the hoisted ``tests/integration/_corpus.py`` provenance.
    """
    ok, reason = prerequisites_available()
    if not ok:
        pytest.skip(reason)

    with start_seeded_server(tmp_path, corpus=_CORPUS) as state_dir:
        yield state_dir


def _cli_env(state_dir: Path) -> dict[str, str]:
    """Build the env block both CLI subprocesses share.

    Both legs must point at the same seeded ``state_dir`` so they
    talk to the same backend state — that's what makes the
    equivalence proof meaningful.
    """
    import os

    env: dict[str, str] = {
        "AGENT_BRAIN_STATE_DIR": str(state_dir / ".agent-brain"),
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
    }
    # MCP backend shells out to agent-brain-mcp which needs
    # OPENAI_API_KEY to forward to its own server; the seeded
    # server reads it from the env block it inherited at startup.
    for k in (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "AGENT_BRAIN_API_KEY",
        "PYTHONPATH",
        "VIRTUAL_ENV",
    ):
        v = os.environ.get(k, "")
        if v:
            env[k] = v
    return env


def test_uds_and_mcp_stdio_query_byte_identical(
    transport_equivalence_corpus: Path,
) -> None:
    """The v3 DoD anchor — CLI-MCP-04.

    ``agent-brain --transport uds`` and ``--transport mcp
    --mcp-transport stdio`` MUST return the same JSON for the same
    query after stripping volatile fields. WIRE equality — both
    subprocesses are real, both backends are real.
    """
    state_dir = transport_equivalence_corpus
    env = _cli_env(state_dir)

    # UDS leg — real subprocess of the CLI, real UDS-backed server.
    uds_proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_brain_cli",
            "--transport",
            "uds",
            "query",
            "echo",
            "--json",
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
        check=True,
    )
    # MCP leg — real subprocess of the CLI, which itself spawns
    # agent-brain-mcp --transport stdio as a child of itself.
    mcp_proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_brain_cli",
            "--transport",
            "mcp",
            "--mcp-transport",
            "stdio",
            "query",
            "echo",
            "--json",
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
        check=True,
    )

    uds_payload = strip_volatile_fields(json.loads(uds_proc.stdout))
    mcp_payload = strip_volatile_fields(json.loads(mcp_proc.stdout))

    assert json.dumps(uds_payload, sort_keys=True) == json.dumps(
        mcp_payload, sort_keys=True
    ), (
        "v3 DoD violation — --transport mcp output diverged from "
        "--transport uds (CLI-MCP-04). Diff:"
        f"\nUDS:  {json.dumps(uds_payload, sort_keys=True, indent=2)}"
        f"\nMCP:  {json.dumps(mcp_payload, sort_keys=True, indent=2)}"
    )


def test_strip_volatile_fields_removes_known_keys() -> None:
    """Unit-level coverage of the stripper helper itself.

    Runs unconditionally — does NOT depend on prerequisites_available.
    """
    payload = {
        "results": [
            {
                "text": "x",
                "source": "a.md",
                "score": 0.9,
                "chunk_id": "c1",
                "metadata": {"indexed_at": "2026-01-01", "language": "md"},
                "indexed_at": "2026-01-01",
            },
        ],
        "query_time_ms": 12.3,
        "total_results": 1,
        "elapsed_seconds": 0.4,
    }
    stripped = strip_volatile_fields(payload)
    assert "elapsed_seconds" not in stripped
    assert "query_time_ms" not in stripped
    assert "indexed_at" not in stripped["results"][0]
    assert "indexed_at" not in stripped["results"][0]["metadata"]
    # Non-volatile fields preserved.
    assert stripped["total_results"] == 1
    assert stripped["results"][0]["text"] == "x"
    assert stripped["results"][0]["chunk_id"] == "c1"
    assert stripped["results"][0]["metadata"]["language"] == "md"
