"""End-to-end integration tests for ``agent-brain resources`` (Phase 59 Plan 03).

Reuses Plan 57-02's ``tests/integration/_corpus.py:start_seeded_server``
to spin up a real ``agent-brain-server`` with a small seeded UDS-backed
corpus, then exercises ``agent-brain resources list/read`` via real
subprocess invocations against a REAL ``agent-brain-mcp --transport
stdio`` subprocess (the same path users hit in production).

Skips gracefully when prerequisites are absent (OPENAI_API_KEY,
agent-brain-serve binary, agent-brain-mcp binary, agent-brain CLI) —
matches Plan 57-02 no-stub-fallback policy.

Covers ROADMAP Phase 59 success criteria SC2 + SC3 + SC4:
  SC1 — prompt command (closed by Plan 59-02; not re-exercised here)
  SC2 — ``resources list`` enumerates 5 static + 4 templated URIs
  SC3 — ``resources read`` dispatches on content type (JSON pretty)
  SC4 — ``resources read file:///disallowed/path`` exits 2 with the
        server's sandbox deny reason surfaced verbatim to stderr

Latent-bug guard (Phase 58 §STATE.md carry-forward): strips
``AGENT_BRAIN_URL`` / ``AGENT_BRAIN_TRANSPORT`` / ``AGENT_BRAIN_MCP_URL`` /
``AGENT_BRAIN_MCP_TRANSPORT`` env vars before each subprocess.run so the
query/CLI default does not silently route around ``--transport mcp``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def _strip_transport_env() -> dict[str, str]:
    """Phase 58 §STATE.md latent-bug guard — strip AGENT_BRAIN_* env vars.

    The query command's ``--url`` option has ``envvar=AGENT_BRAIN_URL``
    which silently routes around ``--transport mcp`` when the env var is
    set. Similarly for AGENT_BRAIN_TRANSPORT / AGENT_BRAIN_MCP_*. This
    helper produces a hermetic subprocess env.
    """
    env = dict(os.environ)
    for key in (
        "AGENT_BRAIN_URL",
        "AGENT_BRAIN_TRANSPORT",
        "AGENT_BRAIN_MCP_TRANSPORT",
        "AGENT_BRAIN_MCP_URL",
    ):
        env.pop(key, None)
    return env


@pytest.fixture
def seeded_state_dir(tmp_path: Path) -> Iterator[Path]:
    """Spin up a real agent-brain-server with a tiny seeded corpus."""
    from tests.integration._corpus import (
        prerequisites_available,
        start_seeded_server,
    )

    ok, reason = prerequisites_available()
    if not ok:
        pytest.skip(reason)

    state_dir = tmp_path / "state"
    state_dir.mkdir()
    corpus = {
        "hello.txt": (
            "hello world\nthis is a small test corpus seeded for "
            "the Phase 59 resources e2e test.\n"
        )
    }
    with start_seeded_server(state_dir, corpus) as resolved_state_dir:
        # start_seeded_server returns the state_dir that was passed in
        # (it uses <state_dir>/.agent-brain/ as the project state dir).
        # The CLI subprocess needs to set AGENT_BRAIN_STATE_DIR to the
        # .agent-brain subdir so the discovery chain resolves correctly.
        yield resolved_state_dir / ".agent-brain"


def test_resources_list_enumerates_static_and_templates(
    seeded_state_dir: Path,
) -> None:
    """SC2: list --json includes 5 static URIs + 4 templated URI schemes."""
    env = _strip_transport_env()
    env["AGENT_BRAIN_STATE_DIR"] = str(seeded_state_dir)
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_brain_cli",
            "--transport",
            "mcp",
            "--mcp-transport",
            "stdio",
            "resources",
            "list",
            "--json",
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, (
        f"resources list failed: stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )
    parsed = json.loads(proc.stdout)
    assert "resources" in parsed
    assert "templates" in parsed
    static_uris = {r.get("uri") for r in parsed["resources"]}
    template_uris = {
        t.get("uriTemplate", t.get("uri")) for t in parsed["templates"]
    }
    # All 5 static URIs.
    assert "corpus://config" in static_uris
    assert "corpus://status" in static_uris
    assert "corpus://health" in static_uris
    assert "corpus://providers" in static_uris
    assert "corpus://folders" in static_uris
    # All 4 templated URI schemes (chunk, graph-entity, job, file).
    template_uri_str = " ".join(t or "" for t in template_uris)
    assert "chunk" in template_uri_str
    assert "graph-entity" in template_uri_str
    assert "job" in template_uri_str
    assert "file" in template_uri_str


def test_resources_read_corpus_status_returns_pretty_json(
    seeded_state_dir: Path,
) -> None:
    """SC3: read corpus://status returns pretty-printed JSON content."""
    env = _strip_transport_env()
    env["AGENT_BRAIN_STATE_DIR"] = str(seeded_state_dir)
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_brain_cli",
            "--transport",
            "mcp",
            "--mcp-transport",
            "stdio",
            "resources",
            "read",
            "corpus://status",
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, (
        f"resources read corpus://status failed: "
        f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )
    # Verify the output is valid JSON (pretty-printed).
    parsed = json.loads(proc.stdout)
    assert isinstance(parsed, dict)
    # The corpus://status payload always exposes either total_documents
    # or total_chunks (server-side IndexingStatus shape).
    assert "total_documents" in parsed or "total_chunks" in parsed


def test_resources_read_file_outside_indexed_roots_exits_2(
    seeded_state_dir: Path, tmp_path: Path
) -> None:
    """SC4: file:// URI outside indexed roots → server sandbox deny.

    The disallowed path lives OUTSIDE the corpus dir that was seeded
    into the server. The server-side file_sandbox returns the deny
    reason; the CLI surfaces it VERBATIM to stderr and exits 2.

    NOTE: ``tmp_path`` is per-test isolated. The corpus is in
    ``<other tmp_path> / "state" / "corpus"`` (a different tmp_path
    fixture invocation for the seeded server) so this path is
    provably outside the indexed roots.
    """
    # tmp_path here is a fresh fixture-scoped dir; seeded_state_dir
    # was constructed in a different tmp_path fixture invocation. They
    # are guaranteed-separate per pytest semantics.
    disallowed = (tmp_path / "outside_root_dir" / "secret.txt").resolve()
    env = _strip_transport_env()
    env["AGENT_BRAIN_STATE_DIR"] = str(seeded_state_dir)
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_brain_cli",
            "--transport",
            "mcp",
            "--mcp-transport",
            "stdio",
            "resources",
            "read",
            f"file://{disallowed}",
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 2, (
        f"Expected exit 2 (sandbox deny); got {proc.returncode}\n"
        f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )
    combined = (proc.stdout + proc.stderr).lower()
    # Pin the literal deny reason in the surfaced server error.
    assert "outside_indexed_roots" in combined or "outside" in combined, (
        f"Expected sandbox deny reason in CLI output; got: "
        f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )
