"""Shared pytest fixtures for agent-brain-mcp tests."""

from __future__ import annotations

import socket
from collections.abc import Callable
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
