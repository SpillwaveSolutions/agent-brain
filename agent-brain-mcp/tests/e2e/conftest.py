"""E2E harness fixtures for agent-brain-mcp.

Per the test plan (``docs/plans/2026-05-28-mcp-uds-test-plan.md`` §4), every
E2E test spawns the real ``agent-brain-serve`` subprocess against a tiny
fixture corpus, then connects via the official MCP Python SDK over stdio.

These fixtures will be wired in Phase 4 when the MCP server itself exists
(currently Phase 0 scaffold). For now they exist as the contract the Phase 4
tests will be written against.

E2E tests are slow and excluded from the per-package default test run.
Opt in via ``task mcp:e2e`` or ``AGENT_BRAIN_E2E=1 pytest tests/e2e/``.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def short_state_dir() -> Generator[Path, None, None]:
    """Session-scoped state dir under /tmp/abmcp-e2e-* — short enough for AF_UNIX.

    Pytest's tmp_path lives under /private/var/folders/... on macOS and
    exceeds the 104-byte sockaddr_un.sun_path limit when an
    ``agent-brain.sock`` segment is appended. Every E2E test that touches
    a real socket must use this fixture.
    """
    base = Path(tempfile.mkdtemp(prefix="abmcp-e2e-"))
    os.chmod(base, 0o700)
    try:
        yield base
    finally:
        shutil.rmtree(base, ignore_errors=True)


@pytest.fixture(scope="session")
def tiny_corpus_path() -> Path:
    """Path to the fixture corpus shipped under ``tests/e2e/fixtures/tiny_corpus/``.

    The corpus is intentionally small (~5 markdown files + ~3 python files)
    so indexing completes in under a few seconds even with real embeddings.
    """
    return Path(__file__).parent / "fixtures" / "tiny_corpus"


@pytest.fixture(scope="session")
def indexed_server(
    short_state_dir: Path, tiny_corpus_path: Path
) -> Generator[dict[str, Path], None, None]:
    """Spawn ``agent-brain-serve --uds-only``, index the corpus, yield paths.

    Phase 4 stub. Real implementation:

    1. ``subprocess.Popen([... "agent-brain-serve", "--uds-only", ...])``
       with ``AGENT_BRAIN_STATE_DIR=short_state_dir`` in the env.
    2. Poll the UDS socket until ``/health/`` returns "healthy".
    3. POST to ``/index/`` against ``tiny_corpus_path``.
    4. Poll ``/index/jobs/<id>`` until "done".
    5. ``yield {"state_dir": short_state_dir, "socket_path": .../agent-brain.sock}``.
    6. Teardown: SIGTERM the subprocess, assert socket is unlinked, assert
       no orphan ``agent-brain-serve`` procs remain.

    For now we skip — the fixture itself will be the Phase 4 RED.
    """
    pytest.skip("indexed_server fixture lands in Phase 4 (agent-brain-mcp v1).")
    yield {}  # pragma: no cover — unreachable under skip


@pytest.fixture
def mcp_client(
    indexed_server: dict[str, Path],
) -> Generator[object, None, None]:
    """Open an MCP stdio client connected to ``agent-brain-mcp --backend uds``.

    Phase 4 stub. Real implementation uses the official MCP Python SDK
    (``mcp.client.stdio.stdio_client``) to spawn ``agent-brain-mcp`` as the
    server subprocess, complete the ``initialize`` handshake, and yield the
    connected client session.

    Teardown closes the client, waits for the subprocess to exit, and
    asserts no orphan ``agent-brain-mcp`` processes remain (verified via
    ``pgrep -f agent-brain-mcp``).
    """
    pytest.skip("mcp_client fixture lands in Phase 4 (agent-brain-mcp v1).")
    yield None  # pragma: no cover — unreachable under skip


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Auto-mark every test in this directory with ``@pytest.mark.e2e``."""
    e2e_marker = pytest.mark.e2e
    for item in items:
        if "tests/e2e/" in str(item.fspath):
            item.add_marker(e2e_marker)
