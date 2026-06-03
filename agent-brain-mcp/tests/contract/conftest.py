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
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from pathlib import Path
from typing import Any

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamablehttp_client

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


# ----------------------------------------------------------------------
# Fast-cadence subscription script (Plan 03)
# ----------------------------------------------------------------------
#
# Phase 52's ``CorpusStatusPolicy`` ships a 30s cadence which is too slow
# for a contract suite that targets <30s total runtime. Plan 03 needs the
# subscriptions tests to verify the SUBSCRIBE → NOTIFY → UNSUBSCRIBE
# round-trip at every URI shape in seconds, not minutes.
#
# This script is a thin wrapper around the bundled fake-server pattern:
# it monkeypatches the three concrete policy ``interval_s`` attributes
# BEFORE ``build_server`` runs, then runs run_stdio against the same
# httpx.MockTransport backend. The cadence overrides are read from env
# vars so each Plan 03 test can dial the cadence to its assertion window.
#
# Defaults — chosen by Plan 03's risk analysis (CONTEXT D-07 cadence×1.5
# tolerance + CI runner jitter budget):
#   AGENT_BRAIN_MCP_CADENCE_JOB_S      → JobPolicy.interval_s         (default 0.5s)
#   AGENT_BRAIN_MCP_CADENCE_STATUS_S   → CorpusStatusPolicy.interval_s (default 0.5s)
#   AGENT_BRAIN_MCP_CADENCE_FOLDERS_S  → CorpusFoldersPolicy.interval_s (default 0.5s)
#
# Note: Phase 52's ``CorpusFoldersPolicy.interval_s`` is normally injected
# from ``mcp_subscription_settings.folders_active_interval_s`` at module
# import. The monkeypatch in this script happens AFTER the policies
# module imports (and thus after the registry instantiation), so we
# update the registry's policy instance directly.
_FAST_CADENCE_SUBSCRIPTION_SCRIPT = """
import asyncio
import json
import logging
import os
import sys

import httpx

# Plan 03 disconnect-cleanup test reads stderr for the Phase 52 log
# line emitted by server.run_stdio's finally block
# (``"subscription cleanup: cancelled %d polling task(s) on session
# close"``). The MCP package itself does NOT configure logging, so the
# default root logger has no handler and ``logger.info(...)`` calls
# would silently drop. We attach a StreamHandler on stderr at INFO
# level here BEFORE importing the server module so the cleanup log
# line surfaces to the parent test's stderr drain.
#
# This is test-only logging configuration — production MCP servers
# inherit whatever logging the MCP runtime (LLM client, plugin host)
# configures.
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(name)s %(levelname)s %(message)s",
)

from agent_brain_mcp.server import build_server, run_stdio
from agent_brain_mcp.subscriptions.policies import SUBSCRIPTION_POLICIES


def _load_responses() -> dict:
    raw = os.environ.get("AGENT_BRAIN_MCP_CONTRACT_RESPONSES_JSON", "{}")
    table = json.loads(raw)
    return {tuple(k.split(" ", 1)): v for k, v in table.items()}


_RESPONSES = _load_responses()


def _handler(request):
    key = (request.method, request.url.path)
    body = _RESPONSES.get(key, {"detail": "not configured: " + str(key)})
    return httpx.Response(200, json=body)


def _cadence(env_name: str, default: float) -> float:
    raw = os.environ.get(env_name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


# Plan 03 cadence override — must run BEFORE build_server reads the
# registry. SUBSCRIPTION_POLICIES holds the *instances* the wire
# handler dispatches against, so mutating the dataclass field on each
# instance is sufficient (no need to swap the registry entries).
SUBSCRIPTION_POLICIES["job://"].interval_s = _cadence(
    "AGENT_BRAIN_MCP_CADENCE_JOB_S", 0.5
)
SUBSCRIPTION_POLICIES["corpus://status"].interval_s = _cadence(
    "AGENT_BRAIN_MCP_CADENCE_STATUS_S", 0.5
)
SUBSCRIPTION_POLICIES["corpus://folders"].interval_s = _cadence(
    "AGENT_BRAIN_MCP_CADENCE_FOLDERS_S", 0.5
)


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
def fast_cadence_subscription_module(
    tmp_path_factory: pytest.TempPathFactory,
) -> Path:
    """Write the fast-cadence subscription script once per test session.

    Plan 03 subscription lifecycle tests use this script via
    ``mcp_stdio_session(custom_script=fast_cadence_subscription_module)``
    to compress Phase 52's 30s ``corpus://status`` cadence into the
    contract suite's sub-second budget. The script name
    (``fake_subscription_server.py``) is intentionally distinct from the
    default ``fake_contract_server.py`` so the orphan-scan pgrep pattern
    catches BOTH variants — see :func:`_scan_for_orphans`.
    """
    base = tmp_path_factory.mktemp("mcp-contract-sub")
    script = base / "fake_subscription_server.py"
    script.write_text(_FAST_CADENCE_SUBSCRIPTION_SCRIPT)
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
    """Return PIDs of any surviving contract-test subprocesses.

    Uses ``pgrep -f`` to match against the full command line. The
    pattern is script-name-scoped so it does NOT match the parent
    ``pytest`` process or unrelated tests' subprocesses. Empty list
    when no orphans survived teardown.

    Plan 03 adds ``fake_subscription_server.py`` for the fast-cadence
    subscription lifecycle tests; the regex alternation catches both
    script names so subscription-lifecycle orphans surface in the same
    autouse scan that catches default contract-test orphans.
    """
    result = subprocess.run(
        # ``pgrep -f`` accepts an extended regex; the alternation
        # matches every bundled fake-server script name. Each ends in
        # ``_server.py`` but we anchor on the distinctive prefix to
        # avoid matching unrelated *_server.py scripts in the same
        # python process tree. Plan 04 adds ``fake_mcp_http_server.py``
        # so HTTP-transport contract orphans surface in the same scan.
        [
            "pgrep",
            "-f",
            "fake_(contract|subscription)_server.py|fake_mcp_http_server.py",
        ],
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
      ``_DEFAULT_CONTRACT_SERVER_SCRIPT``. Plan 03 passes the
      ``fast_cadence_subscription_module`` fixture path here.
    * ``extra_env``: optional environment overrides merged on top of
      ``os.environ`` + ``PYTHONPATH`` + the responses-JSON env var.
    * ``message_handler``: optional SDK ``MessageHandlerFnT`` callback
      forwarded into :class:`ClientSession`. Plan 03 subscription
      lifecycle tests pass a collector that filters
      :class:`mcp.types.ResourceUpdatedNotification` off the SDK's
      incoming-message stream. ``None`` (default) uses the SDK's
      ``_default_message_handler`` — no behavior change for Plans 02/04.

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
        message_handler: Callable[[Any], Awaitable[None]] | None = None,
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
            # Forward ``message_handler`` to the SDK's ``ClientSession``
            # so Plan 03 subscription tests can capture
            # ``notifications/resources/updated`` without poking SDK
            # internals. The kwarg type ``MessageHandlerFnT`` (SDK
            # internal) accepts ``RequestResponder | ServerNotification
            # | Exception`` — Plan 03's callback filters on
            # ``ServerNotification`` and unwraps ``.root``.
            session_kwargs: dict[str, Any] = {}
            if message_handler is not None:
                session_kwargs["message_handler"] = message_handler
            async with ClientSession(read, write, **session_kwargs) as session:
                yield session

    return _open


@pytest.fixture
def mcp_stdio_subprocess_handle(
    fast_cadence_subscription_module: Path,
) -> Callable[..., AbstractAsyncContextManager[subprocess.Popen[bytes]]]:
    """Factory yielding a raw :class:`subprocess.Popen` handle for a
    fake-backed MCP server subprocess.

    Plan 03's disconnect-cleanup test needs to forcibly close stdin
    WITHOUT going through ``ClientSession.__aexit__()`` — the whole
    point of the test is to verify Phase 52's ``run_stdio`` ``finally``
    block cancels the polling task on a raw EOF, not on a graceful
    unsubscribe. Going through the SDK's ``stdio_client`` would call
    its own SIGTERM teardown which masks the disconnect-cleanup
    scenario.

    The yielded ``Popen`` has ``stdin``, ``stdout``, ``stderr`` all set
    to ``PIPE`` so the test can:

    * write framed JSON-RPC requests to ``stdin`` (initialize +
      subscribe);
    * close ``stdin`` to trigger the run_stdio EOF path;
    * scrape ``stderr`` for the Phase 52 disconnect-cleanup log line
      (``"subscription cleanup: cancelled N polling task(s) on session
      close"``) — the verification mechanism used when no debug
      endpoint exists (CONTEXT D-06 fallback).

    Optional kwargs:

    * ``custom_script``: defaults to ``fast_cadence_subscription_module``.
    * ``response_overrides``: same shape as ``mcp_stdio_session``.
    * ``extra_env``: same shape as ``mcp_stdio_session``.

    Teardown contract: SIGTERM on context exit; if the subprocess does
    not exit within 5s, SIGKILL. The autouse orphan-scan catches any
    surviving subprocess.
    """
    project_root = Path(__file__).resolve().parent.parent.parent

    @asynccontextmanager
    async def _spawn(
        *,
        custom_script: Path | None = None,
        response_overrides: dict[tuple[str, str], dict] | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> AsyncIterator[subprocess.Popen[bytes]]:
        env = {
            **os.environ,
            "PYTHONPATH": str(project_root),
            "AGENT_BRAIN_MCP_CONTRACT_RESPONSES_JSON": _build_responses_env(
                response_overrides
            ),
            **(extra_env or {}),
        }
        script = custom_script or fast_cadence_subscription_module
        proc = subprocess.Popen(
            [sys.executable, str(script)],
            cwd=str(project_root),
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            yield proc
        finally:
            # Defensive teardown: SIGTERM → 5s wait → SIGKILL. The test
            # may have already closed stdin (causing run_stdio's
            # finally to fire and the subprocess to exit cleanly); in
            # that case ``proc.terminate()`` is a no-op on an already-
            # dead process.
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=2.0)

    return _spawn


# ----------------------------------------------------------------------
# Plan 04 — Streamable HTTP transport contract session fixture
# ----------------------------------------------------------------------
#
# Wraps Phase 53 Plan 03's ``mcp_http_subprocess`` factory (defined in
# ``tests/conftest.py``, cascaded into ``tests/contract/`` via pytest's
# parent-conftest discovery) and the SDK's
# :func:`mcp.client.streamable_http.streamablehttp_client` into a single
# async-context-manager fixture analogous to ``mcp_stdio_session``.
#
# Plan 04 is the FIRST USAGE of ``streamablehttp_client`` in the contract
# suite. Phase 53 Plan 03 used it in ``test_transport_selection.py`` under
# the ``e2e_http`` marker; Plan 04 introduces a parallel ``contract``-
# marked fixture so the HTTP wire surface is verified alongside the stdio
# tools/resources contract assertions.
#
# Defensive ``*_`` unpack on ``streamablehttp_client``'s yield tuple
# (current shape in mcp 1.12.x: ``(read, write, session_id_factory)``)
# absorbs any future trailing-element addition (per Phase 53 Plan 03
# risk #1) so SDK upgrades don't break Plan 04 silently.
@pytest.fixture
def mcp_http_session(
    mcp_http_subprocess: Callable[..., AbstractAsyncContextManager[Any]],
    free_loopback_port: int,
) -> Callable[..., AbstractAsyncContextManager[ClientSession]]:
    """Factory yielding an async context manager around a fake-backed HTTP MCP session.

    Usage::

        async def test_x(mcp_http_session):
            async with mcp_http_session() as session:
                result = await session.initialize()
                tools = await session.list_tools()

    The factory binds ``free_loopback_port`` so each test gets its own
    (port, subprocess, SDK session) triple. The fake-server subprocess
    (Phase 53's ``fake_mcp_http_server.py`` via
    ``fake_http_server_module``) wires
    :func:`agent_brain_mcp.server.build_server` to an
    :class:`httpx.MockTransport` backend and calls
    :func:`agent_brain_mcp.http.run_http` directly — same fake-backend
    contract as ``mcp_stdio_session`` per Phase 55 CONTEXT D-04, just
    over the HTTP transport instead of stdio.

    The subprocess is held inside ``mcp_http_subprocess`` (which probes
    ``/healthz`` until 200 OK before yielding) so by the time
    ``streamablehttp_client`` opens the SDK connection, uvicorn is
    already bound and answering.

    The host is fixed at ``127.0.0.1`` — Phase 53 D-08 loopback
    whitelist (anything else would be rejected at CLI parse anyway).

    The mount path is :data:`agent_brain_mcp.http.MCP_MOUNT_PATH`
    (``/mcp``) — Phase 53 D-07.

    Optional kwargs (passed through to the underlying subprocess
    factory):

    * ``host``: bind host. Defaults to ``127.0.0.1``.
    * ``extra_env``: env-var overrides merged into ``os.environ`` for
      the child.

    Teardown contract:

    1. SDK ``streamablehttp_client.__aexit__()`` drains the in-flight
       streams + closes the underlying httpx connection.
    2. ``mcp_http_subprocess`` context exit sends SIGINT to the child,
       waits 3s, then SIGKILLs if still alive (matches Phase 53 Plan
       03's harness — the 3s window is enough for
       ``run_http``'s ``finally`` block to run
       ``subscription_manager.cleanup_all()``).
    3. Autouse ``_contract_orphan_scan_after_each_test`` catches any
       surviving ``fake_mcp_http_server.py`` orphans.
    """

    @asynccontextmanager
    async def _open(
        *,
        host: str = "127.0.0.1",
        extra_env: dict[str, str] | None = None,
    ) -> AsyncIterator[ClientSession]:
        # Phase 53 Plan 03 contract: the subprocess context manager is a
        # SYNC ``contextmanager`` (httpx liveness probe is sync), so we
        # enter it inline and rely on its ``finally`` for teardown.
        sub_cm = mcp_http_subprocess(host=host, extra_env=extra_env)
        with sub_cm:
            url = f"http://{host}:{free_loopback_port}{_HTTP_MOUNT_PATH}"
            # The SDK yields ``(read, write, session_id_factory)`` in
            # mcp 1.12.x. The ``*_`` absorbs any future trailing
            # elements so additive SDK signature evolution doesn't break
            # this fixture silently (Phase 53 Plan 03 risk #1).
            async with streamablehttp_client(url) as (read, write, *_):
                async with ClientSession(read, write) as session:
                    yield session

    return _open


# Mount-path constant for Plan 04's HTTP session fixture. Pinned to the
# string literal rather than re-importing
# :data:`agent_brain_mcp.http.MCP_MOUNT_PATH` so this conftest stays
# import-cheap for the stdio-only contract tests (the production HTTP
# module pulls in uvicorn + starlette which would otherwise be loaded
# at collection time for every Plan 02/03 stdio test). Plan 04's
# ``test_http_mount_path_matches_production_constant`` test pins this
# against the production constant so any drift surfaces immediately.
_HTTP_MOUNT_PATH: str = "/mcp"


@pytest.fixture(autouse=True)
def _contract_orphan_scan_after_each_test() -> Iterator[None]:
    """Defensive D-17 orphan scan after every contract test.

    Runs as an autouse fixture so EVERY test in this directory gets the
    safety net, regardless of whether it consumed ``mcp_stdio_session``
    directly. If the SDK's stdio_client teardown ever fails to SIGTERM
    the subprocess (e.g., signal-handling regression, anyio task-group
    bug), the orphan would otherwise leak into the next test's
    environment and mask the regression.

    Plan 03 extension: the regex matched BOTH bundled stdio scripts
    (``fake_contract_server.py`` and ``fake_subscription_server.py``)
    so subscription-lifecycle orphans surface in the same pass.

    Plan 04 extension: the regex now also matches
    ``fake_mcp_http_server.py`` (the Phase 53 HTTP fake-server script
    Plan 04 reuses for the Streamable HTTP contract suite) so HTTP-
    transport orphans surface in the same pass.
    """
    yield
    orphans = _scan_for_orphans()
    if orphans:
        _kill_orphans(orphans)
        raise RuntimeError(
            "Orphan fake_(contract|subscription)_server.py or "
            "fake_mcp_http_server.py subprocesses survived contract "
            f"test teardown: {orphans}. SDK stdio_client / "
            "streamablehttp_client and/or the Plan 03 disconnect-cleanup "
            "teardown should have SIGTERM'd them — investigate signal "
            "handling or the SDK pin."
        )
