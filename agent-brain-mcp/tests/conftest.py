"""Shared pytest fixtures for agent-brain-mcp tests."""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import pytest

# Default backend responses used by most tests. Individual tests can
# pass their own ``responses`` dict to override one or more paths.
_DEFAULT_RESPONSES: dict[tuple[str, str], dict[str, Any]] = {
    ("GET", "/health/"): {
        "status": "healthy",
        "message": "ok",
        "version": "10.0.7",
        "mode": "project",
        "instance_id": "test123",
    },
    ("GET", "/health/status"): {
        "total_documents": 42,
        "total_chunks": 420,
        "indexing_in_progress": False,
        "current_job_id": None,
        "progress_percent": 0.0,
        "indexed_folders": ["/tmp/test"],
    },
    ("GET", "/health/config"): {
        "storage_backend": "chroma",
        "stores": {"vector": True, "bm25": True, "graph": False},
        "reranker_enabled": False,
        "embedding_model": "text-embedding-3-large",
        "rerank_model": None,
        "graph_extractor": None,
        "watcher_running": False,
    },
    ("GET", "/health/providers"): {
        "config_source": None,
        "strict_mode": False,
        "validation_errors": [],
        "providers": [],
        "timestamp": "2026-05-28T00:00:00Z",
    },
    ("GET", "/query/count"): {"total_documents": 42, "total_chunks": 420},
    ("POST", "/query/"): {
        "query": "test",
        "mode": "hybrid",
        "total_results": 1,
        "query_time_ms": 12.3,
        "results": [
            {
                "text": "hit",
                "source": "/tmp/test/file.py",
                "score": 0.99,
                "chunk_id": "chunk_001",
                "metadata": {"line": 1},
            }
        ],
    },
    ("POST", "/index/"): {
        "job_id": "job_abc",
        "status": "queued",
        "message": "Folder queued for indexing",
    },
    ("GET", "/index/jobs/job_abc"): {
        "job_id": "job_abc",
        "status": "running",
        "progress_percent": 50.0,
        "message": "Processing...",
    },
    # Phase 51 (51-01) job:// resource fixtures. The detailed body
    # mirrors a real JobDetailResponse so the read shape contract is
    # validated end-to-end through the parameterized dispatcher.
    ("GET", "/index/jobs/job_51_full"): {
        "job_id": "job_51_full",
        "status": "running",
        "progress_percent": 73.5,
        "message": "Indexing /tmp/repo (147 / 200 files)",
        "folder_path": "/tmp/repo",
        "started_at": "2026-06-03T05:00:00Z",
        "updated_at": "2026-06-03T05:02:34Z",
        "files_processed": 147,
        "files_total": 200,
    },
    ("GET", "/index/jobs/"): {
        "jobs": [
            {"job_id": "j1", "status": "completed", "progress_percent": 100.0},
            {"job_id": "j2", "status": "running", "progress_percent": 30.0},
        ]
    },
    ("DELETE", "/index/jobs/job_abc"): {
        "cancelled": True,
        "message": "Job cancelled",
    },
    ("GET", "/index/folders/"): {
        "folders": [
            {
                "folder_path": "/tmp/test",
                "chunk_count": 420,
                "last_indexed": "2026-05-28T00:00:00Z",
                "watch_mode": "off",
                "watch_debounce_seconds": 30,
            }
        ]
    },
    # Phase 51 Plan 02 (URI-01) chunk:// fixtures. Body mirrors the
    # ChunkRecord wire shape from Phase 50 Plan 02. Embedding is
    # intentionally absent per Phase 50 decision C.
    ("GET", "/query/chunk/chunk_001"): {
        "chunk_id": "chunk_001",
        "parent_doc_id": "/tmp/test/file.py",
        "source": "/tmp/test/file.py",
        "content": "def hello():\n    return 'world'\n",
        "summary": "Greets the world.",
        "folder_id": "/tmp/test",
        "token_count": 12,
        "language": "python",
    },
    # Phase 51 Plan 02 (URI-02) graph-entity:// fixtures. Body mirrors
    # GraphEntityRecord wire shape from Phase 50 Plan 03 — entity node
    # plus 1-hop incoming/outgoing neighbors.
    ("GET", "/graph/entity/Function/foo"): {
        "entity": {
            "type": "Function",
            "id": "foo",
            "properties": {"module": "demo", "language": "python"},
        },
        "neighbors": {
            "incoming": [
                {
                    "type": "Function",
                    "id": "caller",
                    "predicate": "calls",
                    "properties": {"source_chunk_id": "chunk_010"},
                }
            ],
            "outgoing": [
                {
                    "type": "Class",
                    "id": "Helper",
                    "predicate": "uses",
                    "properties": {},
                }
            ],
        },
    },
    # Entity id with embedded "/" — Phase 50 decision B allows
    # hierarchical ids. Used by the slash-in-id test case.
    ("GET", "/graph/entity/Function/AuthService/login"): {
        "entity": {
            "type": "Function",
            "id": "AuthService/login",
            "properties": {},
        },
        "neighbors": {"incoming": [], "outgoing": []},
    },
    # --- Phase 55 Plan 01 (VAL-01 scaffolding) -------------------------
    # Stubs for the v2 endpoints the 9 new MCP tools (Phase 54) call.
    # All shapes mirror the Phase 50-54 Pydantic models 1:1 so contract
    # tests in Plans 02 (16-tool matrix), 03 (subscription lifecycle),
    # and 04 (HTTP transport) can rely on schema correctness without
    # bringing up a live ``agent-brain-serve``. Additive only —
    # existing entries above are untouched.
    #
    # ``DELETE /index/folders/`` -> ``FolderDeleteResponse`` per
    # ``agent_brain_server/models/folders.py``. Wraps remove_folder.
    ("DELETE", "/index/folders/"): {
        "folder_path": "/tmp/test",
        "chunks_deleted": 42,
        "message": "Successfully removed 42 chunks for /tmp/test",
    },
    # ``GET /index/cache/`` -> embedding cache status. Shape from
    # ``agent_brain_server/api/routers/cache.py::_cache_status_impl``;
    # MCP-side mirror at
    # ``agent_brain_mcp/schemas.py::CacheStatusOutput``. The
    # extra-allow config on the MCP schema permits future server
    # additions; this stub stays minimal so Plans 02/03/04 can override
    # with richer payloads when needed.
    ("GET", "/index/cache/"): {
        "hits": 100,
        "misses": 25,
        "hit_rate": 0.8,
        "mem_entries": 50,
        "entry_count": 1024,
        "size_bytes": 2_097_152,
    },
    # ``DELETE /index/cache/`` -> clear-cache result. Shape from
    # ``agent_brain_server/api/routers/cache.py::_clear_cache_impl``;
    # MCP-side mirror at ``schemas.py::ClearCacheOutput``.
    ("DELETE", "/index/cache/"): {
        "count": 1024,
        "size_bytes": 2_097_152,
        "size_mb": 2.0,
    },
    # ``POST /index/add`` -> ``IndexResponse`` shape (job_id + status
    # + message). Wraps the ``add_documents`` MCP tool which posts a
    # ``{"paths": [...]}`` body. MockTransport ignores the body; tests
    # that need body-shape assertions construct a per-test client.
    ("POST", "/index/add"): {
        "job_id": "job_add_001",
        "status": "queued",
        "message": "Documents queued for indexing",
    },
    # --- Additional ``/index/jobs/{id}`` variants for ``wait_for_job``
    # contract tests. The base ``job_abc`` entry above stays at
    # ``running`` for backwards compat with the v1 query-time guard
    # tests; these aliases cover terminal-status assertions Plans 02
    # and 04 will write against.
    ("GET", "/index/jobs/job_done"): {
        "job_id": "job_done",
        "status": "completed",
        "progress_percent": 100.0,
        "message": "Indexing complete.",
        "started_at": "2026-06-03T05:00:00Z",
        "completed_at": "2026-06-03T05:01:00Z",
    },
    ("GET", "/index/jobs/job_failed"): {
        "job_id": "job_failed",
        "status": "failed",
        "progress_percent": 25.0,
        "message": "Embedding provider rejected payload.",
        "started_at": "2026-06-03T05:00:00Z",
        "completed_at": "2026-06-03T05:00:15Z",
    },
    ("GET", "/index/jobs/job_cancelled"): {
        "job_id": "job_cancelled",
        "status": "cancelled",
        "progress_percent": 60.0,
        "message": "Cancelled by client.",
        "started_at": "2026-06-03T05:00:00Z",
        "completed_at": "2026-06-03T05:00:30Z",
    },
}


def make_httpx_client(
    *,
    responses: dict[tuple[str, str], dict[str, Any]] | None = None,
    status_overrides: dict[tuple[str, str], int] | None = None,
    error_paths: dict[tuple[str, str], Exception] | None = None,
) -> httpx.Client:
    """Build an httpx.Client whose MockTransport returns the given JSON
    or raises the given exceptions.

    Args:
        responses: Override default JSON responses by (METHOD, path).
        status_overrides: Force a specific HTTP status for a (METHOD, path).
        error_paths: Raise a transport-level exception for a path.
    """
    merged = dict(_DEFAULT_RESPONSES)
    if responses:
        merged.update(responses)
    overrides = status_overrides or {}
    errors = error_paths or {}

    def handler(request: httpx.Request) -> httpx.Response:
        key = (request.method, request.url.path)
        if key in errors:
            raise errors[key]
        status = overrides.get(key, 200)
        body = merged.get(key, {"detail": f"not configured: {key}"})
        return httpx.Response(status, json=body)

    transport = httpx.MockTransport(handler)
    return httpx.Client(transport=transport, base_url="http://test-agent-brain")


@pytest.fixture
def mock_client_factory() -> Callable[..., httpx.Client]:
    """Pytest fixture returning the make_httpx_client factory."""
    return make_httpx_client


@pytest.fixture
def fake_httpx_client() -> httpx.Client:
    """A default httpx.Client wired to default responses."""
    return make_httpx_client()


# --- Phase 51 Plan 03 (URI-04) file:// fixtures ---------------------------


@dataclass
class FileSandboxScenario:
    """Filesystem scenario for ``file://`` sandbox tests.

    Plan 51-03 needs a tmp directory that simulates "operator has
    indexed folder X but folder Y is off-limits." We expose the layout
    explicitly so individual tests can compose URIs against specific
    files without re-deriving paths.

    Attributes:
        allowed_root: Canonical absolute path that the stub
            ``/index/folders/`` endpoint reports as the only indexed
            root. Test ``file://`` reads against files inside this
            directory should succeed.
        denied_root: A sibling directory NOT in the indexed-folder
            list. Reads against files here should be denied with
            ``outside_indexed_roots``.
        allowed_text: A small UTF-8 text file inside ``allowed_root``
            (``.txt`` MIME). Used by the text-success test.
        allowed_binary: A small binary file inside ``allowed_root``
            (``.bin`` extension, will be sniffed as
            ``application/octet-stream``). Used by the
            binary-success test.
        big_text: A text file inside ``allowed_root`` whose size
            exceeds :data:`DEFAULT_MAX_READ_BYTES`. Used by the
            size-cap test.
        hidden_file: A dot-file inside ``allowed_root`` (named
            ``.secret``). Phase 50's sandbox rule allows hidden files
            INSIDE an indexed root (root policy wins) — so this read
            should actually succeed. The ``hidden_file`` deny only
            fires for hidden files OUTSIDE every root.
        outside_hidden: A dot-file inside ``denied_root`` (``.env``-
            style). This one should trigger ``hidden_file`` denial.
        denied_file: A regular file inside ``denied_root``. Should
            trigger ``outside_indexed_roots`` denial.
        symlink_escape: A symlink LIVING INSIDE ``allowed_root`` whose
            target is ``denied_file`` outside. Phase 50's policy:
            ``symlink_escape`` reason fires because the literal path
            is a symlink whose canonical target escapes every root.
        traversal_attempt: An unresolved string path inside
            ``allowed_root`` that contains ``..`` segments resolving
            outside (e.g. ``<allowed>/../<denied>/secret.txt``).
            Canonicalization should collapse the ``..`` and the result
            should fall outside all roots → ``outside_indexed_roots``.
    """

    allowed_root: Path
    denied_root: Path
    allowed_text: Path
    allowed_binary: Path
    big_text: Path
    hidden_file: Path
    outside_hidden: Path
    denied_file: Path
    symlink_escape: Path
    traversal_attempt: str


@pytest.fixture
def tmp_path_with_indexed_root(tmp_path: Path) -> FileSandboxScenario:
    """Build a tmp directory tree exercising every sandbox rule.

    Layout (under ``tmp_path``)::

        sandbox/
          allowed/                       <- indexed root
            allowed.txt                  (small text)
            allowed.bin                  (small binary)
            big.txt                      (> DEFAULT_MAX_READ_BYTES)
            .secret                      (hidden file INSIDE root -> allowed)
            escape -> ../denied/secret.txt   (symlink escapes -> denied)
          denied/                        <- NOT indexed
            secret.txt
            .env

    The ``tmp_path_with_indexed_root`` fixture does NOT stub the HTTP
    layer — tests that need the stub call
    :func:`make_file_sandbox_httpx_client` with the returned scenario.
    Separation of concerns: the scenario owns the filesystem layout,
    the helper owns the network mock.

    The ``big.txt`` size is deliberately a tiny bit over the cap
    (cap + 1 byte) so the test runs fast — pyfilesystem writes are
    cheap up to a few MB but multi-GB writes would slow CI. Phase 50
    cap is 10 MiB.
    """
    from agent_brain_server.security.file_sandbox import DEFAULT_MAX_READ_BYTES

    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    allowed = sandbox / "allowed"
    allowed.mkdir()
    denied = sandbox / "denied"
    denied.mkdir()

    allowed_text = allowed / "allowed.txt"
    allowed_text.write_text("hello from allowed root\n", encoding="utf-8")

    allowed_binary = allowed / "allowed.bin"
    allowed_binary.write_bytes(b"\x00\x01\x02\x03BINARYDATA\xff\xfe")

    big_text = allowed / "big.txt"
    # Write cap + 1 byte to trip the size limit. Writing the cap exactly
    # would PASS (the rule is strictly >, not >=).
    big_text.write_bytes(b"A" * (DEFAULT_MAX_READ_BYTES + 1))

    hidden_file = allowed / ".secret"
    hidden_file.write_text("hidden but inside root\n", encoding="utf-8")

    denied_file = denied / "secret.txt"
    denied_file.write_text("you should not see this\n", encoding="utf-8")

    outside_hidden = denied / ".env"
    outside_hidden.write_text("SECRET_KEY=hunter2\n", encoding="utf-8")

    symlink_escape = allowed / "escape"
    # Relative symlink: from allowed/, target is ../denied/secret.txt.
    # ``Path.resolve`` follows the link; the canonical target is
    # ``denied/secret.txt`` (outside the indexed root).
    symlink_escape.symlink_to(denied_file)

    # Pre-canonical traversal attempt — string with literal ``..``
    # segments. Sandbox check canonicalizes it; result falls in
    # ``denied`` so is_path_allowed returns
    # (False, "outside_indexed_roots").
    traversal_attempt = str(allowed / ".." / "denied" / "secret.txt")

    return FileSandboxScenario(
        allowed_root=allowed.resolve(),
        denied_root=denied.resolve(),
        allowed_text=allowed_text.resolve(),
        allowed_binary=allowed_binary.resolve(),
        big_text=big_text.resolve(),
        hidden_file=hidden_file.resolve(),
        outside_hidden=outside_hidden,  # NOT canonicalized; we want the literal path
        denied_file=denied_file.resolve(),
        symlink_escape=symlink_escape,  # literal symlink — do NOT resolve here
        traversal_attempt=traversal_attempt,
    )


def make_file_sandbox_httpx_client(
    scenario: FileSandboxScenario,
    *,
    folders_call_counter: list[int] | None = None,
) -> httpx.Client:
    """Build an httpx.Client whose ``/index/folders/`` reports the
    scenario's allowed root as the only indexed folder.

    Args:
        scenario: The fixture-produced :class:`FileSandboxScenario`.
        folders_call_counter: Optional 1-element list used as a
            mutable counter. Each ``GET /index/folders/`` request
            increments ``folders_call_counter[0]``. Used by the
            roots-refresh-on-each-read regression test to assert that
            two consecutive ``file://`` reads result in two calls to
            ``list_folders``.

    The transport returns:

    - ``GET /index/folders/`` → ``{"folders": [{"folder_path":
      "<allowed_root>", ...}]}`` (canonical absolute path).
    - All other paths → 404 with a stub detail (the file:// handler
      should never hit any other endpoint).
    """
    counter = folders_call_counter

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/index/folders/":
            if counter is not None:
                counter[0] += 1
            return httpx.Response(
                200,
                json={
                    "folders": [
                        {
                            "folder_path": str(scenario.allowed_root),
                            "chunk_count": 1,
                            "last_indexed": "2026-06-03T00:00:00Z",
                            "watch_mode": "off",
                            "watch_debounce_seconds": 30,
                        }
                    ]
                },
            )
        return httpx.Response(
            404,
            json={"detail": f"sandbox test fixture has no stub for {path}"},
        )

    transport = httpx.MockTransport(handler)
    return httpx.Client(transport=transport, base_url="http://test-agent-brain")


# --- Phase 53 Plan 02 (HTTP listener) shared fixture ---------------------


@pytest.fixture
def free_loopback_port() -> int:
    """Return a free TCP port on ``127.0.0.1``, then close the probe socket.

    Phase 53 Plan 02 needs an unbound port to pass to ``run_http``
    without colliding with whatever else is on the dev box. We probe
    by binding ``AF_INET`` on ``("127.0.0.1", 0)``, reading
    :meth:`socket.socket.getsockname` for the kernel-assigned port,
    and closing the probe before returning. There's a TOCTOU window
    between close and the next bind, but in practice (single-process
    test suite, ephemeral-port range) collisions are vanishingly
    rare; the port-in-use test deliberately stays bound to test the
    failure path.

    NB: Plan 02 deliberately does NOT support ``--port 0`` (D-12
    forbids dynamic ports in production), so tests have to find a
    free port themselves rather than letting uvicorn pick one.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = int(s.getsockname()[1])
    s.close()
    return port


# --- Phase 53 Plan 03 (SDK round-trip smoke) HTTP subprocess fixture -----


# Fake MCP server script wired to a MockTransport httpx backend — mirrors the
# stdio e2e harness at ``tests/test_e2e_stdio.py`` but boots ``run_http``
# instead of ``run_stdio``. Bypasses ``main_async``'s version-compat check
# (it would otherwise need a real ``agent-brain-serve`` to answer ``/health/``)
# by calling ``build_server()`` + ``run_http()`` directly. The same
# approach was used by Phase 52 for stdio e2e — proves the wire protocol
# without standing up the full backend stack.
_FAKE_HTTP_SERVER_SCRIPT = """
import asyncio
import os
import sys

import httpx

from agent_brain_mcp.http import run_http
from agent_brain_mcp.server import build_server

_RESPONSES = {
    ("GET", "/health/"): {
        "status": "healthy", "version": "10.2.0",
        "message": "ok", "mode": "project", "instance_id": "e2e-http",
    },
    ("GET", "/health/status"): {
        "total_documents": 42, "total_chunks": 420,
        "indexing_in_progress": False, "current_job_id": None,
        "progress_percent": 0.0, "indexed_folders": [],
    },
    ("GET", "/health/config"): {
        "storage_backend": "chroma",
        "stores": {"vector": True, "bm25": True, "graph": False},
        "reranker_enabled": False,
        "embedding_model": "text-embedding-3-large",
        "rerank_model": None, "graph_extractor": None,
        "watcher_running": False,
    },
    ("GET", "/health/providers"): {
        "config_source": None, "strict_mode": False,
        "validation_errors": [], "providers": [],
        "timestamp": "2026-06-03T00:00:00Z",
    },
    ("GET", "/query/count"): {"total_documents": 42, "total_chunks": 420},
    ("GET", "/index/folders/"): {
        "folders": [{"folder_path": "/tmp/x", "chunk_count": 1,
                     "last_indexed": "2026-06-03", "watch_mode": "off",
                     "watch_debounce_seconds": 30}],
    },
}


def _handler(request):
    key = (request.method, request.url.path)
    body = _RESPONSES.get(key, {"detail": "not configured: " + str(key)})
    return httpx.Response(200, json=body)


async def main():
    host = os.environ["AGENT_BRAIN_MCP_E2E_HOST"]
    port = int(os.environ["AGENT_BRAIN_MCP_E2E_PORT"])
    client = httpx.Client(
        transport=httpx.MockTransport(_handler),
        base_url="http://e2e",
    )
    # Phase 53: pass both axis labels so initialize._meta carries them.
    server, manager = build_server(
        client, backend_transport="http", listen_transport="http"
    )
    try:
        await run_http(server, manager, host=host, port=port)
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
"""


@pytest.fixture(scope="session")
def fake_http_server_module(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Write the fake-server script to a tmp path; session-scoped for reuse."""
    base = tmp_path_factory.mktemp("mcp-http-e2e")
    script = base / "fake_mcp_http_server.py"
    script.write_text(_FAKE_HTTP_SERVER_SCRIPT)
    return script


@contextmanager
def _mcp_subprocess(
    port: int,
    fake_server_script: Path,
    *,
    host: str = "127.0.0.1",
    extra_env: dict[str, str] | None = None,
    readiness_timeout_s: float = 10.0,
) -> Iterator[subprocess.Popen[bytes]]:
    """Spawn the fake MCP HTTP server subprocess and wait for ``/healthz`` 200.

    Phase 53 Plan 03's HTTP-01 round-trip needs to drive the official MCP
    SDK's :func:`mcp.client.streamable_http.streamablehttp_client` against
    a real listener — that means a real subprocess. The fake-server
    script (:data:`_FAKE_HTTP_SERVER_SCRIPT`) wires
    :func:`agent_brain_mcp.server.build_server` to a
    :class:`httpx.MockTransport` backend and calls
    :func:`agent_brain_mcp.http.run_http` directly, bypassing
    ``main_async``'s version-compat check (which would otherwise need a
    real ``agent-brain-serve`` reachable at startup). Same pattern as
    Phase 52's stdio e2e harness at ``tests/test_e2e_stdio.py``.

    Teardown is SIGINT → wait 3s → SIGKILL fallback. The 3-second SIGINT
    grace window is enough for uvicorn's graceful shutdown to drain
    in-flight requests AND for ``run_http``'s ``finally`` block to run
    ``subscription_manager.cleanup_all()`` (Plan 02 contract).

    Args:
        port: TCP port the subprocess should bind. Caller supplies a
            free port via the ``free_loopback_port`` fixture.
        fake_server_script: Path to the fake-server Python script
            (yielded by the ``fake_http_server_module`` fixture).
        host: Bind host. Defaults to ``127.0.0.1`` (the only value
            that round-trips through Plan 02's loopback validator AND
            the official SDK client's DNS-rebinding-protection check).
        extra_env: Optional environment overrides merged on top of
            ``os.environ`` for the child.
        readiness_timeout_s: How long to wait for ``/healthz`` to
            answer with 200 before giving up. 10s is generous for a
            cold uvicorn start; CI runners typically reach 200 in 1-2s.

    Yields:
        The :class:`subprocess.Popen` handle. The MCP server is
        guaranteed to have answered ``/healthz`` with 200 before the
        yield runs, so the SDK client can immediately ``initialize``.

    Raises:
        RuntimeError: if ``/healthz`` never returns 200 within
            ``readiness_timeout_s`` OR the subprocess exits early. The
            subprocess's stderr is captured in the error message so CI
            logs show the bind failure or backend-version-floor
            rejection directly.
    """
    project_root = Path(__file__).resolve().parent.parent
    env = {
        **os.environ,
        "PYTHONPATH": str(project_root),
        "AGENT_BRAIN_MCP_E2E_HOST": host,
        "AGENT_BRAIN_MCP_E2E_PORT": str(port),
        **(extra_env or {}),
    }
    cmd = [sys.executable, str(fake_server_script)]
    proc = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(project_root),
    )
    try:
        url = f"http://{host}:{port}/healthz"
        deadline = time.time() + readiness_timeout_s
        while time.time() < deadline:
            # If the subprocess died before binding /healthz, no point
            # waiting out the timeout — report the early death.
            if proc.poll() is not None:
                stderr = b""
                if proc.stderr is not None:
                    stderr = proc.stderr.read()
                raise RuntimeError(
                    f"MCP HTTP subprocess exited with code "
                    f"{proc.returncode} before /healthz at {url} became "
                    f"ready. stderr=\n{stderr.decode(errors='replace')}"
                )
            try:
                r = httpx.get(url, timeout=0.5)
                if r.status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.1)
        else:
            stderr = b""
            if proc.stderr is not None:
                stderr = proc.stderr.read()
            proc.terminate()
            raise RuntimeError(
                f"MCP HTTP listener did not become ready at {url} "
                f"within {readiness_timeout_s}s. stderr=\n"
                f"{stderr.decode(errors='replace')}"
            )
        yield proc
    finally:
        if proc.poll() is None:
            # Graceful shutdown — gives ``run_http``'s finally block
            # the 3s grace window to drain polling tasks via
            # ``subscription_manager.cleanup_all()`` (Plan 02 contract).
            proc.send_signal(signal.SIGINT)
            try:
                proc.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


@pytest.fixture
def mcp_http_subprocess(
    free_loopback_port: int,
    fake_http_server_module: Path,
) -> Callable[..., Any]:
    """Factory returning a context manager that runs an HTTP MCP subprocess.

    Usage::

        def test_http(mcp_http_subprocess, free_loopback_port):
            with mcp_http_subprocess() as proc:
                url = f"http://127.0.0.1:{free_loopback_port}/mcp"
                # drive the SDK client against url ...

    The factory binds ``free_loopback_port`` so a single test gets a
    single (port, subprocess) pair.

    Args (to the returned callable):
        host: Bind host. Defaults to ``127.0.0.1``.
        extra_env: Optional env-var overrides.
    """

    def _factory(
        *,
        host: str = "127.0.0.1",
        extra_env: dict[str, str] | None = None,
    ) -> Any:
        return _mcp_subprocess(
            free_loopback_port,
            fake_http_server_module,
            host=host,
            extra_env=extra_env,
        )

    return _factory
