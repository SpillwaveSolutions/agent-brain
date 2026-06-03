"""Phase 55 Plan 01 — contract test scaffolding.

This conftest defines the SDK-driven fixture chain that Plans 02 (16-tool
matrix, VAL-01), 03 (subscription lifecycle, VAL-02), and 04 (HTTP transport,
VAL-03) ALL consume. The public surface is LOCKED on Plan 01's first commit.

Fixture contract
----------------
``mcp_stdio_session`` is a CALLABLE that returns an async context manager
yielding a connected :class:`mcp.ClientSession` over stdio. Usage::

    async def test_x(mcp_stdio_session):
        async with mcp_stdio_session() as session:
            result = await session.initialize()
            ...

The callable shape — rather than a direct ``async def`` fixture yielding
the session — is **load-bearing** because of anyio's task-group ownership
constraint: ``stdio_client`` opens an anyio ``TaskGroup`` whose cancel
scope MUST be entered and exited from the same asyncio task. A
pytest-asyncio async-generator fixture (``yield session`` inside an
``async def`` fixture) runs setup and teardown in DIFFERENT tasks
(documented in Phase 52 Plan 02 Decision: ``test_subscribe_handler_dispatch``
"fixture-wrapped harness trips anyio's ``RuntimeError: Attempted to exit
cancel scope in a different task than it was entered in``"). The
callable + ``async with`` pattern keeps the entire enter/exit in the
test's own task.

The subprocess wires :func:`agent_brain_mcp.server.build_server` to an
in-memory fake httpx backend (the ``_DEFAULT_RESPONSES`` extended in
``tests/conftest.py``), NOT a real ``agent-brain-serve`` subprocess —
per Phase 55 CONTEXT decision D-04 the contract suite verifies the MCP
protocol layer, not the server's behavior. Keeps the suite under 30s.

The bundled fake-server script (``_DEFAULT_CONTRACT_SERVER_SCRIPT``) is
the inline default; downstream plans may inject per-test response
overrides or a custom script via factory kwargs (e.g., Plan 03's
subscription tests need a script that exposes a progressing job state
for ``job://`` polling).

Teardown contract (Phase 55 D-17, inherits Phase 4 / Phase 52 pattern)
----------------------------------------------------------------------
On fixture exit:

1. The SDK's ``stdio_client`` async context manager handles SIGTERM ->
   wait -> SIGKILL on the subprocess (inside the ``async with``).
2. After every test in the contract suite, this conftest also runs a
   defensive ``pgrep -f fake_contract_server.py`` scan and FAILS the
   test if any subprocess survived. Orphan processes would inherit
   the test's open file descriptors and leak into subsequent tests,
   masking real teardown bugs. The scan is script-name-scoped so it
   does NOT match the parent ``pytest`` process or unrelated tests'
   subprocesses.

Subscriptions, transports, tools are NOT exercised here. This module is
scaffolding only — Plans 02/03/04 own the substantive assertions.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from pathlib import Path

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

# ----------------------------------------------------------------------
# Bundled fake-server script
# ----------------------------------------------------------------------
#
# Mirrors the proven pattern in ``tests/test_e2e_stdio.py`` and
# ``tests/conftest.py::_FAKE_HTTP_SERVER_SCRIPT``: a self-contained
# Python script that imports ``build_server`` + ``run_stdio`` and wires
# an :class:`httpx.MockTransport` backend keyed on the shared
# ``_DEFAULT_RESPONSES`` dict (re-exported here so downstream plans
# don't have to copy the table).
#
# The script reads its responses payload from the
# ``AGENT_BRAIN_MCP_CONTRACT_RESPONSES_JSON`` env var (a JSON-serialized
# dict mapping ``"METHOD path"`` -> response body). Plans 02/03/04 can
# inject per-test response overrides without rewriting the script.
_DEFAULT_CONTRACT_SERVER_SCRIPT = """
import asyncio
import json
import os

import httpx

from agent_brain_mcp.server import build_server, run_stdio


def _load_responses() -> dict:
    raw = os.environ.get("AGENT_BRAIN_MCP_CONTRACT_RESPONSES_JSON", "{}")
    table = json.loads(raw)
    # Keys land as "METHOD path" strings; rehydrate to (method, path)
    # tuples for the request handler.
    return {tuple(k.split(" ", 1)): v for k, v in table.items()}


_RESPONSES = _load_responses()


def _handler(request):
    key = (request.method, request.url.path)
    body = _RESPONSES.get(key, {"detail": "not configured: " + str(key)})
    return httpx.Response(200, json=body)


async def main():
    client = httpx.Client(
        transport=httpx.MockTransport(_handler),
        base_url="http://contract-test",
    )
    server, manager = build_server(client)
    try:
        await run_stdio(server, manager)
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
"""


@pytest.fixture(scope="session")
def contract_fake_server_module(
    tmp_path_factory: pytest.TempPathFactory,
) -> Path:
    """Write the bundled fake-server script once per test session.

    Session-scoped so the script file is reused across every contract
    test in a run; Plans 02/03/04 amortize the disk write.
    """
    base = tmp_path_factory.mktemp("mcp-contract")
    script = base / "fake_contract_server.py"
    script.write_text(_DEFAULT_CONTRACT_SERVER_SCRIPT)
    return script


def _build_responses_env(
    response_overrides: dict[tuple[str, str], dict] | None = None,
) -> str:
    """Serialize ``_DEFAULT_RESPONSES`` + overrides to JSON for the subprocess.

    The fake-server script reads this JSON from
    ``AGENT_BRAIN_MCP_CONTRACT_RESPONSES_JSON`` and rehydrates the
    ``(method, path) -> body`` table. Tuple keys are flattened to
    ``"METHOD path"`` strings because JSON object keys must be strings.
    """
    # Import lazily so tests/conftest.py doesn't have to be on
    # ``sys.path`` at module load — pytest discovery handles it.
    from tests.conftest import _DEFAULT_RESPONSES  # noqa: PLC0415

    merged: dict[tuple[str, str], dict] = dict(_DEFAULT_RESPONSES)
    if response_overrides:
        merged.update(response_overrides)

    flat = {f"{method} {path}": body for (method, path), body in merged.items()}
    return json.dumps(flat)


def _scan_for_orphans() -> list[str]:
    """Return PIDs of any surviving ``fake_contract_server.py`` subprocesses.

    Uses ``pgrep -f`` to match against the full command line. The
    pattern is script-name-scoped so it does NOT match the parent
    ``pytest`` process or unrelated tests' subprocesses. Empty list
    when no orphans survived teardown.
    """
    result = subprocess.run(
        ["pgrep", "-f", "fake_contract_server.py"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return []
    return [pid.strip() for pid in result.stdout.strip().splitlines() if pid.strip()]


def _kill_orphans(pids: list[str]) -> None:
    """SIGKILL surviving PIDs so subsequent tests don't inherit them.

    Called after the orphan-scan assertion fails (so the failing test
    still sees the orphan list) but BEFORE the next test runs.
    """
    for pid in pids:
        try:
            os.kill(int(pid), signal.SIGKILL)
        except (ValueError, ProcessLookupError, PermissionError):
            # ValueError: pid not int; ProcessLookupError: died between
            # scan and kill; PermissionError: not our process. All
            # are acceptable -- the goal is best-effort cleanup.
            pass


@pytest.fixture
def mcp_stdio_session(
    contract_fake_server_module: Path,
) -> Callable[..., AbstractAsyncContextManager[ClientSession]]:
    """Factory yielding an async context manager around a fake-backed MCP session.

    Usage::

        async def test_x(mcp_stdio_session):
            async with mcp_stdio_session() as session:
                result = await session.initialize()

    Optional kwargs:

    * ``response_overrides``: dict mapping ``(method, path)`` to a JSON
      response body that overrides the shared ``_DEFAULT_RESPONSES``
      table for this single session. Plans 02/03/04 use this for
      per-test backend behavior (e.g., progressing job state for
      ``wait_for_job`` contract tests).
    * ``custom_script``: optional :class:`Path` to a custom fake-server
      script. Defaults to the bundled
      ``_DEFAULT_CONTRACT_SERVER_SCRIPT``.
    * ``extra_env``: optional environment overrides merged on top of
      ``os.environ`` + ``PYTHONPATH`` + the responses-JSON env var.

    The callable shape avoids anyio's "exit cancel scope in a different
    task" trap that bites async-generator fixtures wrapping
    ``stdio_client`` (Phase 52 Plan 02 Decision precedent).
    """
    project_root = Path(__file__).resolve().parent.parent.parent

    @asynccontextmanager
    async def _open(
        *,
        response_overrides: dict[tuple[str, str], dict] | None = None,
        custom_script: Path | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> AsyncIterator[ClientSession]:
        env = {
            **os.environ,
            "PYTHONPATH": str(project_root),
            "AGENT_BRAIN_MCP_CONTRACT_RESPONSES_JSON": _build_responses_env(
                response_overrides
            ),
            **(extra_env or {}),
        }
        script = custom_script or contract_fake_server_module
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(script)],
            cwd=str(project_root),
            env=env,
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                yield session

    return _open


@pytest.fixture(autouse=True)
def _contract_orphan_scan_after_each_test() -> Iterator[None]:
    """Defensive D-17 orphan scan after every contract test.

    Runs as an autouse fixture so EVERY test in this directory gets the
    safety net, regardless of whether it consumed ``mcp_stdio_session``
    directly. If the SDK's stdio_client teardown ever fails to SIGTERM
    the subprocess (e.g., signal-handling regression, anyio task-group
    bug), the orphan would otherwise leak into the next test's
    environment and mask the regression.
    """
    yield
    orphans = _scan_for_orphans()
    if orphans:
        _kill_orphans(orphans)
        raise RuntimeError(
            "Orphan fake_contract_server.py subprocesses survived "
            f"contract test teardown: {orphans}. SDK stdio_client should "
            "have SIGTERM'd them — investigate the subprocess's signal "
            "handling or the SDK version pin."
        )
