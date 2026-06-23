"""ApiClient — thin httpx wrapper used by MCP tool/resource handlers.

Wraps an already-constructed ``httpx.Client`` (HTTP or UDS) and exposes
one method per Agent Brain endpoint that v1 exercises. Each method
calls the underlying client, applies :func:`errors.raise_for_status`
on non-2xx, and returns parsed JSON.

Plan §4.2: this client does NOT depend on ``agent_brain_cli`` — keeps
the MCP process free of Click / Rich. ~80 LOC bound.
"""

from __future__ import annotations

import asyncio
import os
import threading
import time
import weakref
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, Any

import httpx

from . import errors

# Phase 60 (MCPHYG-01) — minimum POSIX-ish env to keep Python subprocess
# startup + locale working on macOS/Linux/Windows.
#
# AGENT_BRAIN_API_KEY is auto-forwarded by ``_effective_env`` when set in
# the parent environment — this is the v10.2.1 SECURITY-01 loopback API
# auth key and dropping it would break ``agent-brain-mcp`` calling
# ``agent-brain-server`` over a bearer-protected loopback. Other
# AGENT_BRAIN_* vars (including OPENAI_API_KEY / ANTHROPIC_API_KEY)
# REQUIRE caller opt-in via the ``forward_env=[...]`` constructor kwarg.
DEFAULT_ENV_ALLOWLIST: frozenset[str] = frozenset(
    {"PATH", "HOME", "USER", "LANG", "LC_ALL", "TERM"}
)


# Phase 60 (MCPHYG-01) — module-level subprocess hygiene helpers.
# Consumed by ``McpStdioBackend._hygienic_stdio_client`` (per-call wrapper
# around ``mcp.client.stdio.stdio_client``) and ``McpStdioBackend.close()``
# (SIGTERM→SIGKILL escalation).


def _process_has_exited(process: Any) -> bool:
    """Return True if the subprocess has exited.

    Checks both ``process.returncode`` (set when the asyncio event loop
    reaps the child) AND ``psutil.pid_exists(process.pid)`` (kernel-level
    truth). ``returncode`` alone is unreliable from sync code because
    ``close()`` runs OUTSIDE the asyncio event loop — the loop never gets
    to update ``returncode`` until the caller does ``await process.wait()``.
    Phase 58-03 ``_wait_for_pid_exit`` used the same psutil.pid_exists
    pattern (commands/mcp.py:309-321).

    Fakes that lack ``.pid`` (e.g. SimpleNamespace in unit tests) still
    work via the ``returncode`` check.
    """
    if process.returncode is not None:
        return True
    pid = getattr(process, "pid", None)
    if pid is None:
        return False
    try:
        import psutil
    except ImportError:
        return False
    return not psutil.pid_exists(pid)


def _wait_for_subprocess_exit(
    process: Any, timeout: float, poll_interval: float = 0.05
) -> bool:
    """Poll ``process`` until it has exited or ``timeout`` expires.

    Returns True if the subprocess exited within ``timeout`` seconds,
    False otherwise. ``timeout == 0`` performs a single check.

    Mirrors Phase 58-03's ``_wait_for_pid_exit`` shape (commands/mcp.py:
    309-321). Uses :func:`_process_has_exited` which checks both
    ``process.returncode`` AND ``psutil.pid_exists(process.pid)`` — the
    psutil round-trip is necessary because ``close()`` runs outside the
    asyncio event loop, so ``returncode`` alone is unreliable for real
    ``asyncio.subprocess.Process`` instances.
    """
    deadline = time.monotonic() + max(0.0, timeout)
    while True:
        if _process_has_exited(process):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(poll_interval)


def _extract_subprocess_from_streams(streams: Any) -> Any | None:
    """Best-effort: extract asyncio.subprocess.Process from stdio_client streams.

    The MCP SDK 1.12.x line stores the spawned subprocess on the write
    stream's underlying transport. SDK versions are pinned in
    pyproject.toml; if the SDK changes shape, the close() escalation
    silently downgrades to no-op (registered process is None) — Pattern A
    still tears down via the SDK's normal context cleanup, so this is a
    soft-fail boundary INSIDE the extractor. The wrapper-level §3.5
    no-silent-fallback contract is enforced by an E2E extraction test
    (``test_hygienic_wrapper_registers_inflight_on_real_sdk_shape``).

    Returns None if extraction fails (subprocess hygiene degrades to
    SDK-only cleanup; still correct, just no SIGKILL escalation).
    """
    try:
        # streams is a (read_stream, write_stream) tuple.
        _read, write = streams
        # Inspect write stream for a process attribute (best-effort —
        # exact attribute name varies by SDK version).
        for attr in ("_process", "process", "_transport"):
            candidate = getattr(write, attr, None)
            if candidate is None:
                continue
            # asyncio.subprocess.Process has .returncode + .terminate + .kill
            if all(hasattr(candidate, m) for m in ("returncode", "terminate", "kill")):
                return candidate
        return None
    except Exception:
        return None


class ApiClient:
    """Synchronous Agent Brain HTTP client over a provided httpx.Client.

    The transport (UDS or TCP) is selected by the caller via
    :func:`agent_brain_mcp.config.open_backend_client`.
    """

    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def __enter__(self) -> ApiClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._request("GET", path, params=params)

    def _post(self, path: str, json: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._request("POST", path, json=json)

    def _delete(self, path: str, json: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._request("DELETE", path, json=json)

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            response = self._client.request(method, path, json=json, params=params)
        except httpx.TimeoutException as e:
            errors.raise_backend_timeout(e)
            raise  # unreachable; satisfies type checker
        except (httpx.ConnectError, httpx.NetworkError) as e:
            errors.raise_backend_unavailable(e)
            raise

        errors.raise_for_status(response)
        if not response.content:
            return {}
        result: Any = response.json()
        if isinstance(result, dict):
            return result
        return {"data": result}

    # --- Tool-backing methods ---

    def server_health(self) -> dict[str, Any]:
        return self._get("/health/")

    def server_status(self) -> dict[str, Any]:
        return self._get("/health/status")

    def server_config(self) -> dict[str, Any]:
        return self._get("/health/config")

    def server_providers(self) -> dict[str, Any]:
        return self._get("/health/providers")

    def query(self, body: dict[str, Any]) -> dict[str, Any]:
        return self._post("/query/", json=body)

    def query_count(self) -> dict[str, Any]:
        return self._get("/query/count")

    def index_folder(
        self,
        body: dict[str, Any],
        *,
        force: bool = False,
        allow_external: bool = False,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if force:
            params["force"] = "true"
        if allow_external:
            params["allow_external"] = "true"
        return self._request("POST", "/index/", json=body, params=params or None)

    def get_job(self, job_id: str) -> dict[str, Any]:
        return self._get(f"/index/jobs/{job_id}")

    def list_jobs(self, *, limit: int = 20, offset: int = 0) -> dict[str, Any]:
        return self._get("/index/jobs/", params={"limit": limit, "offset": offset})

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        return self._delete(f"/index/jobs/{job_id}")

    def list_folders(self) -> dict[str, Any]:
        return self._get("/index/folders/")

    def get_chunk(self, chunk_id: str) -> dict[str, Any]:
        """GET /query/chunk/{chunk_id} — chunk content + metadata, no embedding.

        Backs the MCP ``chunk://<chunk_id>`` URI scheme (URI-01, Phase 51).
        The server-side response shape is :class:`ChunkRecord` (Phase 50
        Plan 02). Error mapping is the existing pipeline: 404 →
        ``INVALID_PARAMS`` via :func:`errors.raise_for_status`.
        """
        return self._get(f"/query/chunk/{chunk_id}")

    def get_graph_entity(self, entity_type: str, entity_id: str) -> dict[str, Any]:
        """GET /graph/entity/{entity_type}/{entity_id} — entity + 1-hop neighbors.

        Backs the MCP ``graph-entity://<type>/<id>`` URI scheme (URI-02,
        Phase 51). The server-side response shape is
        :class:`GraphEntityRecord` (Phase 50 Plan 03). Error mapping is
        the existing pipeline: 404 → ``INVALID_PARAMS``, 503 →
        ``SERVICE_INDEXING`` (covers both ``graphrag_disabled`` and the
        ``kuzu_unavailable`` #178 fallback).

        Entity ids may contain ``/`` characters (Phase 50 decision B —
        the server's route uses a path-style ``{entity_id}`` segment).
        Callers MUST not pre-encode the id; httpx URL-quotes it once
        which is what the FastAPI route expects.
        """
        return self._get(f"/graph/entity/{entity_type}/{entity_id}")

    # --- Phase 54: tool-backing methods for the remaining 9 tools ---

    def add_documents(
        self,
        body: dict[str, Any],
        *,
        force: bool = False,
    ) -> dict[str, Any]:
        """POST /index/add — add documents from another folder to the index.

        Backs the ``add_documents`` MCP tool (TOOL-02, Phase 54). The
        ``allow_external`` query parameter was removed by issue #180;
        containment is enforced exclusively by the server-side
        ``AGENT_BRAIN_ALLOW_EXTERNAL_PATHS`` setting.
        """
        params: dict[str, Any] = {}
        if force:
            params["force"] = "true"
        return self._request("POST", "/index/add", json=body, params=params or None)

    def inject_documents(
        self,
        body: dict[str, Any],
        *,
        force: bool = False,
    ) -> dict[str, Any]:
        """POST /index/ — index a folder with injector_script/folder_metadata_file.

        Same endpoint as :meth:`index_folder`; the differentiator is
        that ``body`` MUST include at least one of ``injector_script``
        or ``folder_metadata_file`` (CONTEXT decision D — the MCP
        handler raises ``INVALID_PARAMS`` before this method is called
        if both are missing). Backs the ``inject_documents`` MCP tool
        (TOOL-03, Phase 54).

        Unallowlisted scripts (issue #181) surface as 403 → structured
        ``McpError(INVALID_PARAMS)`` via ``errors.raise_for_status``.
        """
        params: dict[str, Any] = {}
        if force:
            params["force"] = "true"
        return self._request("POST", "/index/", json=body, params=params or None)

    def cache_status(self) -> dict[str, Any]:
        """GET /index/cache/ — embedding cache hit/miss + disk statistics.

        Backs the ``cache_status`` MCP tool (TOOL-07, Phase 54). Returns
        503 → ``McpError`` via the standard pipeline when the cache
        service is not initialised.
        """
        return self._get("/index/cache/")

    def clear_cache(self) -> dict[str, Any]:
        """DELETE /index/cache/ — clear all cached embeddings.

        Backs the ``clear_cache`` MCP tool (TOOL-08, Phase 54). The MCP
        handler's ``confirm: Literal[True]`` guard ensures this method
        is only reachable after explicit destructive-op acknowledgement.
        Returns 503 → ``McpError`` when the cache service is not
        initialised.
        """
        return self._delete("/index/cache/")

    def delete_folder(self, body: dict[str, Any]) -> dict[str, Any]:
        """DELETE /index/folders/ — remove a folder from the index.

        ``FolderDeleteRequest`` is a request *body*, not a query/path
        param — see folders router source. Backs the ``remove_folder``
        MCP tool (TOOL-06, Phase 54). 409 (active job for this folder,
        FOLD-07) surfaces as ``McpError(INVALID_PARAMS)`` via the
        existing pipeline.
        """
        return self._delete("/index/folders/", json=body)


# =============================================================================
# v3 CLI-via-MCP backends (Phase 56 Plan 03 — skeletons; wired in Phase 57+)
# =============================================================================
#
# These two classes structurally satisfy the BackendClient Protocol declared
# at agent_brain_cli/client/protocol.py (Plan 56-02). They expose the same
# 12-public-method + ctx-mgr surface as agent_brain_cli.client.DocServeClient
# so a CLI command coded against DocServeClient can be transparently
# rerouted through an MCP transport in Phase 57.
#
# Method bodies (except __init__, __enter__, __exit__, close) raise
# NotImplementedError with the literal message "Wired in Phase 57+". The
# message is load-bearing — Phase 57's transport selector tests grep for it
# to confirm "I got the skeleton, not a stale stub left behind by a botched
# refactor." See ROADMAP Phase 56 success criteria #5.
#
# Both classes inherit MIN_BACKEND_VERSION = "10.2.0" verbatim from
# agent_brain_mcp.server. Bump to "10.3.0" at v3 release per design doc §3.4.
#
# IMPORTANT: this block deliberately does NOT re-import the deferred-
# annotations future. The module-header import already covers this file.
# Python forbids those imports anywhere except the file header —
# re-importing here (even with an alias) is a SyntaxError.
# =============================================================================

if TYPE_CHECKING:
    from agent_brain_cli.client.api_client import (
        FolderInfo,
        HealthStatus,
        IndexingStatus,
        IndexResponse,
        QueryResponse,
    )


def _coerce_query_response(payload: dict[str, Any]) -> QueryResponse:
    """Translate a ``search_documents`` MCP tool payload into ``QueryResponse``.

    The MCP tool's structuredContent has the same shape as the
    ``agent-brain-server`` ``POST /query/`` response, so we delegate to
    ``api_client._parse_query_result`` for each result entry.

    Late-imports the agent_brain_cli dataclasses to avoid a module-load
    cycle with agent_brain_cli (the CLI's BackendClient Protocol uses
    forward string references to these dataclasses for the same
    reason).
    """
    # Late import — avoids a top-level dep on agent_brain_cli for
    # consumers of agent_brain_mcp.client that never touch the v3
    # backends (e.g. the v1 ApiClient code path).
    from agent_brain_cli.client import api_client as _api_client

    results = [_api_client._parse_query_result(r) for r in payload.get("results", [])]
    return _api_client.QueryResponse(
        results=results,
        query_time_ms=float(payload.get("query_time_ms", 0.0)),
        total_results=int(payload.get("total_results", len(results))),
    )


def _coerce_health_status(payload: dict[str, Any]) -> HealthStatus:
    """Translate a ``server_health`` MCP tool payload into ``HealthStatus``.

    Mirrors ``DocServeClient.health()``'s parse logic so both transports
    produce identical dataclass shapes. Late-imports the dataclass per
    the same module-load cycle rationale as ``_coerce_query_response``.
    """
    from agent_brain_cli.client import api_client as _api_client

    return _api_client.HealthStatus(
        status=payload.get("status", ""),
        message=payload.get("message"),
        version=payload.get("version", "unknown"),
        timestamp=payload.get("timestamp", ""),
    )


def _coerce_indexing_status(payload: dict[str, Any]) -> IndexingStatus:
    """Translate a ``corpus://status`` MCP resource body into ``IndexingStatus``.

    Mirrors ``DocServeClient.status()``'s parse logic.
    """
    from agent_brain_cli.client import api_client as _api_client

    return _api_client.IndexingStatus(
        total_documents=int(payload.get("total_documents", 0)),
        total_chunks=int(payload.get("total_chunks", 0)),
        indexing_in_progress=bool(payload.get("indexing_in_progress", False)),
        current_job_id=payload.get("current_job_id"),
        progress_percent=float(payload.get("progress_percent", 0.0)),
        last_indexed_at=payload.get("last_indexed_at"),
        indexed_folders=list(payload.get("indexed_folders", [])),
        file_watcher=payload.get("file_watcher"),
        embedding_cache=payload.get("embedding_cache"),
    )


def _coerce_folder_info_list(payload: dict[str, Any]) -> list[FolderInfo]:
    """Translate a ``corpus://folders`` MCP resource body into ``list[FolderInfo]``.

    Mirrors ``DocServeClient.list_folders()``'s parse logic.
    """
    from agent_brain_cli.client import api_client as _api_client

    return [
        _api_client.FolderInfo(
            folder_path=f["folder_path"],
            chunk_count=int(f.get("chunk_count", 0)),
            last_indexed=f.get("last_indexed", ""),
            watch_mode=f.get("watch_mode", "off"),
            watch_debounce_seconds=f.get("watch_debounce_seconds"),
        )
        for f in payload.get("folders", [])
    ]


def _coerce_index_response(payload: dict[str, Any]) -> IndexResponse:
    """Translate an ``index_folder`` / ``inject_documents`` MCP tool payload
    into ``IndexResponse``.

    Mirrors ``DocServeClient.index()``'s parse logic.
    """
    from agent_brain_cli.client import api_client as _api_client

    return _api_client.IndexResponse(
        job_id=payload.get("job_id", ""),
        status=payload.get("status", ""),
        message=payload.get("message"),
    )


def _unwrap_payload(result: Any) -> dict[str, Any]:
    """Extract a dict payload from an MCP tool result.

    Prefer ``structuredContent`` (the SDK's typed channel). Fall back to
    parsing ``content[0].text`` as JSON when ``structuredContent`` is
    None (the SDK behavior when the tool's output_schema is not
    declared).
    """
    if result.structuredContent is not None:
        payload = result.structuredContent
        assert isinstance(payload, dict)
        return payload
    import json as _json

    text = result.content[0].text
    parsed = _json.loads(text)
    assert isinstance(parsed, dict)
    return parsed


def _unwrap_resource_body(result: Any) -> dict[str, Any]:
    """Extract a dict payload from an MCP read_resource result.

    ``result.contents[0].text`` is a JSON string for the corpus:// and
    job:// schemes (Plan 51).
    """
    import json as _json

    text = result.contents[0].text
    parsed = _json.loads(text)
    assert isinstance(parsed, dict)
    return parsed


def _build_index_body(
    *,
    folder_path: str,
    chunk_size: int,
    chunk_overlap: int,
    include_code: bool,
    force: bool,
    injector_script: str | None,
    folder_metadata_file: str | None,
    dry_run: bool,
) -> tuple[dict[str, Any], str]:
    """Build the call_tool body for ``index_folder`` or ``inject_documents``.

    The v2 MCP tool input schemas use additionalProperties=false; CLI-
    only fields (``recursive``, ``supported_languages``,
    ``code_chunk_strategy``, ``include_patterns``, ``exclude_patterns``,
    ``include_types``, ``generate_summaries``, ``watch_mode``,
    ``watch_debounce_seconds``) have no v2 wire equivalent and are
    dropped here. Phase 58+ may widen the tool schemas; for v3 the
    closing constraint is the JSON-Schema validator inside the MCP SDK.

    Returns:
        Tuple of (body, tool_name). ``tool_name`` is ``inject_documents``
        when ``injector_script`` or ``folder_metadata_file`` is set, else
        ``index_folder``. ``include_code`` is forwarded to both tools
        (their schemas both accept it).
    """
    body: dict[str, Any] = {
        "folder_path": folder_path,
        "force": force,
        "include_code": include_code,
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
    }
    if injector_script is not None or folder_metadata_file is not None:
        if injector_script is not None:
            body["injector_script"] = injector_script
        if folder_metadata_file is not None:
            body["folder_metadata_file"] = folder_metadata_file
        if dry_run:
            body["dry_run"] = True
        return body, "inject_documents"
    return body, "index_folder"


class McpStdioBackend:
    """CLI-side backend that talks to agent-brain-mcp over stdio.

    Phase 57 wired: all 10 BackendClient methods (health, status, query,
    index, list_folders, delete_folder, list_jobs, get_job, cancel_job,
    cache_status, clear_cache) plus a deliberate ``reset()`` raise that
    points at --transport uds (no reset_index MCP tool in v2; v3
    Phase 57+ open decision per design doc §4 risks).

    Each public method uses Pattern A: ``asyncio.run(self._async_*())``
    per call, spawning a fresh ``agent-brain-mcp --transport stdio``
    subprocess via the MCP SDK's ``stdio_client``. Phase 60 owns the
    persistent-subprocess hygiene refinement.

    Structurally satisfies the BackendClient Protocol at
    agent_brain_cli.client.protocol.BackendClient (Plan 56-02). Verified
    by tests/test_cli_backends_skeleton.py via isinstance() at runtime
    and by mypy strict structural conformance.

    Args:
        command: Path or shell command to launch agent-brain-mcp.
            ``str`` is split into argv[0]; ``list[str]`` is passed
            verbatim. ``--transport stdio`` is appended by
            ``_stdio_params``.
        cwd: Working directory for the subprocess. Default ``None``
            snapshots ``os.getcwd()`` at construction (Phase 60 hygiene
            — no "moving target" if the caller ``os.chdir()`` s later).
            An explicit ``cwd`` MUST exist and be a directory; otherwise
            ``__init__`` raises ``ValueError`` (fail-fast at the
            construction boundary).
        env: Subprocess env dict. If non-``None`` it wins verbatim and
            bypasses the allowlist (escape hatch for tests/advanced
            ops). When ``None``, ``_effective_env`` filters
            ``os.environ`` through ``env_allowlist`` and merges
            ``forward_env`` keys additively.
        env_allowlist: Module-level ``DEFAULT_ENV_ALLOWLIST`` is used
            when ``None``. Pass a ``frozenset[str]`` to replace
            entirely (overrides default — additive forwarding still
            happens via ``forward_env``).
        forward_env: Additive list of env keys to forward from the
            parent environment on top of the active allowlist.
            Required to propagate provider keys (e.g.
            ``OPENAI_API_KEY``, ``ANTHROPIC_API_KEY``); these never
            auto-forward by default. ``AGENT_BRAIN_API_KEY`` is the one
            exception — it auto-forwards (v10.2.1 SECURITY-01 carryover).
        grace_period_s: SIGTERM→SIGKILL grace window (seconds) for
            ``close()`` escalation (consumed by Plan 60-02). Default
            ``5.0`` mirrors Phase 58-03 ``mcp stop --grace`` precedent
            and v10.2 HTTP-02 grace. Must be ``> 0``; ``ValueError``
            otherwise.
    """

    def __init__(
        self,
        command: str | list[str],
        *,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        env_allowlist: frozenset[str] | None = None,
        forward_env: list[str] | None = None,
        grace_period_s: float = 5.0,
    ) -> None:
        self.command = command
        # Phase 60 (MCPHYG-01): pin cwd. None → snapshot os.getcwd() at
        # construction so callers' later os.chdir() does NOT move the
        # target.
        if cwd is None:
            self.cwd = os.getcwd()
        else:
            cwd_path = Path(cwd)
            if not cwd_path.exists():
                raise ValueError(f"cwd does not exist: {cwd!r}")
            if not cwd_path.is_dir():
                raise ValueError(f"cwd is not a directory: {cwd!r}")
            self.cwd = cwd
        self.env = env
        # Phase 60 (MCPHYG-01): env hygiene. None → DEFAULT_ENV_ALLOWLIST;
        # caller may pass a frozenset to replace entirely. forward_env is
        # additive on top of the active allowlist.
        self.env_allowlist = (
            env_allowlist if env_allowlist is not None else DEFAULT_ENV_ALLOWLIST
        )
        self.forward_env = list(forward_env) if forward_env else []
        # Phase 60 (MCPHYG-01): grace period persisted at __init__;
        # consumed by Plan 60-02 close() escalation. ValueError on
        # non-positive to fail-fast at the construction boundary.
        if grace_period_s <= 0:
            raise ValueError(f"grace_period_s must be > 0; got {grace_period_s!r}")
        self.grace_period_s = float(grace_period_s)
        self._closed = False
        # Phase 60 (MCPHYG-01): in-flight subprocess tracker. Pattern A
        # spawns a fresh subprocess per call, so at most ONE subprocess
        # is alive on this backend at a time. weakref so we don't extend
        # the SDK's lifecycle; threading.Lock so close() from another
        # thread doesn't race with the async helper registering.
        self._inflight_ref: weakref.ref[Any] | None = None
        self._inflight_lock = threading.Lock()

    def __enter__(self) -> McpStdioBackend:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    def _register_inflight(self, process: Any) -> None:
        """Set the in-flight subprocess weakref (called by the hygienic wrapper).

        Pattern A invariant: at most ONE subprocess per backend at a time.
        """
        with self._inflight_lock:
            self._inflight_ref = weakref.ref(process)

    def _unregister_inflight(self) -> None:
        """Clear the in-flight subprocess weakref.

        Called when the hygienic wrapper exits cleanly — the SDK has
        already torn the subprocess down via its own context cleanup.
        """
        with self._inflight_lock:
            self._inflight_ref = None

    @asynccontextmanager
    async def _hygienic_stdio_client(self, params: Any) -> AsyncIterator[Any]:
        """Wrap the SDK's stdio_client to register the spawned subprocess.

        Drop-in replacement for ``stdio_client(params)`` inside each
        ``_async_*`` helper. Registers the underlying
        ``asyncio.subprocess.Process`` on ``self._inflight_ref`` so
        ``close()`` from another thread can escalate SIGTERM → SIGKILL.

        Pattern A preserved — still fresh subprocess per call. The wrapper
        does NOT keep the subprocess alive after the async context exits;
        it merely registers a weakref for the duration of the call.
        """
        from mcp.client.stdio import stdio_client

        async with stdio_client(params) as streams:
            # The MCP SDK 1.12.x stdio_client owns an
            # asyncio.subprocess.Process internally. Best-effort
            # discovery via the (read, write) streams' transport.
            process = _extract_subprocess_from_streams(streams)
            if process is not None:
                self._register_inflight(process)
            try:
                yield streams
            finally:
                self._unregister_inflight()

    def close(self) -> None:
        """Tear down any in-flight MCP subprocess. Idempotent.

        Phase 60 (MCPHYG-01) close() escalation:
        1. Idempotent fast path — no in-flight subprocess → return.
        2. Send SIGTERM via ``process.terminate()``.
        3. Poll ``process.returncode`` for ``self.grace_period_s``.
        4. If still alive, send SIGKILL via ``process.kill()``.

        Safe to call from another thread while a sync method is mid-flight
        on the main thread — the threading.Lock guards the weakref.
        """
        with self._inflight_lock:
            ref = self._inflight_ref
        process = ref() if ref is not None else None

        if process is None or _process_has_exited(process):
            # No in-flight subprocess, or it already exited.
            self._closed = True
            return

        # Path 1: SIGTERM the in-flight subprocess.
        try:
            process.terminate()
        except (ProcessLookupError, OSError):
            self._closed = True
            return

        # Path 2: poll for grace_period_s.
        if _wait_for_subprocess_exit(process, self.grace_period_s):
            self._closed = True
            return

        # Path 3: refused to die — SIGKILL.
        try:
            process.kill()
        except (ProcessLookupError, OSError):
            pass
        # Best-effort short wait so callers see the dead state.
        _wait_for_subprocess_exit(process, 1.0)
        self._closed = True

    # --- Shared helpers (Pattern A — asyncio.run per call) ---

    def _effective_env(self) -> dict[str, str]:
        """Build the subprocess env dict honoring the allowlist + forwards.

        Precedence:
        1. If ``self.env`` is non-None, return it verbatim (caller fully
           controls the env — escape hatch for tests / advanced ops).
        2. Otherwise: filter ``os.environ`` through ``self.env_allowlist``,
           additively merge any caller ``forward_env`` keys, and
           auto-forward ``AGENT_BRAIN_API_KEY`` if present (v10.2.1
           SECURITY-01 carryover).
        """
        if self.env is not None:
            return dict(self.env)
        active: dict[str, str] = {
            k: v for k, v in os.environ.items() if k in self.env_allowlist
        }
        for key in self.forward_env:
            if key in os.environ:
                active[key] = os.environ[key]
        # SECURITY-01 carryover: server-auth key always forwards if set.
        if "AGENT_BRAIN_API_KEY" in os.environ:
            active["AGENT_BRAIN_API_KEY"] = os.environ["AGENT_BRAIN_API_KEY"]
        return active

    def _stdio_params(self) -> Any:
        """Build StdioServerParameters from ``self.command`` / cwd / env.

        Shared by every async helper so the subprocess spec stays
        consistent across all 11 wired methods. Phase 60 (MCPHYG-01)
        routes the env through ``_effective_env`` so every wired method
        inherits the allowlist hygiene by going through this chokepoint.
        """
        from mcp.client.stdio import StdioServerParameters

        if isinstance(self.command, str):
            command_str = self.command
            extra_args: list[str] = []
        else:
            command_str = self.command[0]
            extra_args = list(self.command[1:])
        return StdioServerParameters(
            command=command_str,
            args=[*extra_args, "--transport", "stdio"],
            cwd=self.cwd,
            env=self._effective_env(),
        )

    # --- BackendClient surface (12 methods) ---

    def health(self) -> HealthStatus:
        return asyncio.run(self._async_health())

    async def _async_health(self) -> HealthStatus:
        from mcp import ClientSession

        async with self._hygienic_stdio_client(self._stdio_params()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool("server_health", {})
        return _coerce_health_status(_unwrap_payload(result))

    def status(self) -> IndexingStatus:
        return asyncio.run(self._async_status())

    async def _async_status(self) -> IndexingStatus:
        from mcp import ClientSession
        from pydantic import AnyUrl

        async with self._hygienic_stdio_client(self._stdio_params()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.read_resource(AnyUrl("corpus://status"))
        return _coerce_indexing_status(_unwrap_resource_body(result))

    def query(
        self,
        query_text: str,
        top_k: int = 5,
        similarity_threshold: float = 0.7,
        mode: str = "hybrid",
        alpha: float = 0.5,
        source_types: list[str] | None = None,
        languages: list[str] | None = None,
        file_paths: list[str] | None = None,
        explain: bool = False,
    ) -> QueryResponse:
        return asyncio.run(
            self._async_query(
                query_text=query_text,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
                mode=mode,
                alpha=alpha,
                source_types=source_types,
                languages=languages,
                file_paths=file_paths,
                explain=explain,
            )
        )

    async def _async_query(
        self,
        *,
        query_text: str,
        top_k: int,
        similarity_threshold: float,
        mode: str,
        alpha: float,
        source_types: list[str] | None,
        languages: list[str] | None,
        file_paths: list[str] | None,
        explain: bool,
    ) -> QueryResponse:
        """Async helper for :meth:`query` (Pattern A sync facade — Phase
        57 CONTEXT decision).

        Each call spawns a fresh ``agent-brain-mcp --transport stdio``
        subprocess via the MCP SDK's ``stdio_client``, opens a
        ``ClientSession``, calls the ``search_documents`` tool, then
        tears the subprocess down. Phase 60 owns the persistent-
        subprocess hygiene refinement; Phase 57 ships the simplest
        correct code path.
        """
        # Late import — keeps the MCP SDK dep contained to the wire
        # path; consumers of the McpStdioBackend constructor that
        # never call query() do not pay the import cost.
        from mcp import ClientSession

        tool_args: dict[str, Any] = {
            "query": query_text,
            "top_k": top_k,
            "similarity_threshold": similarity_threshold,
            "mode": mode,
            "alpha": alpha,
            "explain": explain,
        }
        if source_types is not None:
            tool_args["source_types"] = source_types
        if languages is not None:
            tool_args["languages"] = languages
        if file_paths is not None:
            tool_args["file_paths"] = file_paths

        async with self._hygienic_stdio_client(self._stdio_params()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool("search_documents", tool_args)

        return _coerce_query_response(_unwrap_payload(result))

    def index(
        self,
        folder_path: str,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        recursive: bool = True,
        include_code: bool = False,
        supported_languages: list[str] | None = None,
        code_chunk_strategy: str = "ast_aware",
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
        include_types: list[str] | None = None,
        generate_summaries: bool = False,
        force: bool = False,
        injector_script: str | None = None,
        folder_metadata_file: str | None = None,
        dry_run: bool = False,
        watch_mode: str | None = None,
        watch_debounce_seconds: int | None = None,
    ) -> IndexResponse:
        # The MCP v2 tool input schemas (IndexFolderInput,
        # InjectDocumentsInput) use additionalProperties=false. They
        # accept a strict subset of the CLI BackendClient.index()
        # parameter set. CLI-only parameters that have no v2 MCP
        # equivalent (recursive, supported_languages, code_chunk_strategy,
        # include_patterns, exclude_patterns, include_types,
        # generate_summaries, watch_mode, watch_debounce_seconds) are
        # dropped here rather than forwarded — forwarding them would
        # fail JSON Schema validation in the SDK. Phase 58+ may widen
        # the MCP tool schemas to add these; for v3 the wire layer is
        # the closing constraint.
        body, tool_name = _build_index_body(
            folder_path=folder_path,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            include_code=include_code,
            force=force,
            injector_script=injector_script,
            folder_metadata_file=folder_metadata_file,
            dry_run=dry_run,
        )
        return asyncio.run(self._async_index(tool_name=tool_name, body=body))

    async def _async_index(
        self, *, tool_name: str, body: dict[str, Any]
    ) -> IndexResponse:
        from mcp import ClientSession

        async with self._hygienic_stdio_client(self._stdio_params()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, body)
        return _coerce_index_response(_unwrap_payload(result))

    def list_folders(self) -> list[FolderInfo]:
        return asyncio.run(self._async_list_folders())

    async def _async_list_folders(self) -> list[FolderInfo]:
        from mcp import ClientSession
        from pydantic import AnyUrl

        async with self._hygienic_stdio_client(self._stdio_params()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.read_resource(AnyUrl("corpus://folders"))
        return _coerce_folder_info_list(_unwrap_resource_body(result))

    def delete_folder(self, folder_path: str) -> dict[str, Any]:
        return asyncio.run(self._async_delete_folder(folder_path))

    async def _async_delete_folder(self, folder_path: str) -> dict[str, Any]:
        from mcp import ClientSession

        # remove_folder is destructive — Phase 54 Plan 03 schema
        # requires confirm=True (RemoveFolderInput.confirm: Literal[True]).
        # CONTEXT.md Claude's-discretion note: pass-through for parity
        # with --transport uds; no CLI-side confirmation prompt.
        async with self._hygienic_stdio_client(self._stdio_params()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(
                    "remove_folder",
                    {"folder_path": folder_path, "confirm": True},
                )
        return _unwrap_payload(result)

    def reset(self) -> IndexResponse:
        # Design doc §4-risks: reset() has no MCP tool equivalent in v2.
        # Phase 57+ open decision per CONTEXT.md §decisions — explicit
        # NotImplementedError pointer rather than a silent fallback or a
        # not-yet-existing tool call.
        raise NotImplementedError(
            "--transport mcp does not support reset; use --transport uds "
            "or http (no reset_index MCP tool in v2; v3 Phase 57+ open "
            "decision per design doc §4 risks)"
        )

    def list_jobs(self, limit: int = 20) -> list[dict[str, Any]]:
        return asyncio.run(self._async_list_jobs(limit))

    async def _async_list_jobs(self, limit: int) -> list[dict[str, Any]]:
        from mcp import ClientSession

        async with self._hygienic_stdio_client(self._stdio_params()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool("list_jobs", {"limit": limit})
        payload = _unwrap_payload(result)
        jobs = payload.get("jobs", [])
        assert isinstance(jobs, list)
        return jobs

    def get_job(self, job_id: str) -> dict[str, Any]:
        return asyncio.run(self._async_get_job(job_id))

    async def _async_get_job(self, job_id: str) -> dict[str, Any]:
        from mcp import ClientSession
        from pydantic import AnyUrl

        async with self._hygienic_stdio_client(self._stdio_params()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.read_resource(AnyUrl(f"job://{job_id}"))
        return _unwrap_resource_body(result)

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        return asyncio.run(self._async_cancel_job(job_id))

    async def _async_cancel_job(self, job_id: str) -> dict[str, Any]:
        from mcp import ClientSession

        # cancel_job is destructive — v1's destructive-op guard requires
        # confirm=True (CancelJobInput.confirm: Literal[True], v1 §6.2).
        # CONTEXT.md Claude's-discretion note: pass-through for parity
        # with --transport uds.
        async with self._hygienic_stdio_client(self._stdio_params()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(
                    "cancel_job", {"job_id": job_id, "confirm": True}
                )
        return _unwrap_payload(result)

    def cache_status(self) -> dict[str, Any]:
        return asyncio.run(self._async_cache_status())

    async def _async_cache_status(self) -> dict[str, Any]:
        from mcp import ClientSession

        async with self._hygienic_stdio_client(self._stdio_params()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool("cache_status", {})
        return _unwrap_payload(result)

    def clear_cache(self) -> dict[str, Any]:
        return asyncio.run(self._async_clear_cache())

    async def _async_clear_cache(self) -> dict[str, Any]:
        from mcp import ClientSession

        # confirm=True is REQUIRED by the clear_cache tool's
        # Pydantic schema (Phase 54 Plan 03 destructive-op guard).
        # CONTEXT.md Claude's-discretion note: pass-through for parity
        # with --transport uds; no CLI-side confirmation prompt.
        async with self._hygienic_stdio_client(self._stdio_params()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool("clear_cache", {"confirm": True})
        return _unwrap_payload(result)

    # --- Phase 59 Plan 02: McpBackend Protocol surface (wired) ---
    #
    # Each public method is a 1-line ``asyncio.run(self._async_*())``
    # facade (Pattern A — Plan 57-02 CONTEXT decision, confirmed across
    # the full 10-method × 2-backend surface in Plan 57-03). Each
    # ``_async_*`` helper opens ``stdio_client(self._stdio_params())``,
    # opens a ``ClientSession``, calls one MCP wire method, then
    # ``model_dump(mode="json", exclude_none=False)``-translates the
    # Pydantic result to ``dict[str, Any]`` / ``list[dict[str, Any]]``.
    # The Plan 59-01 NotImplementedError sentinel has been fully removed
    # — replaced byte-for-byte by these wire bodies.

    def get_prompt(
        self, name: str, arguments: dict[str, str] | None = None
    ) -> dict[str, Any]:
        return asyncio.run(self._async_get_prompt(name, arguments))

    async def _async_get_prompt(
        self, name: str, arguments: dict[str, str] | None
    ) -> dict[str, Any]:
        from mcp import ClientSession

        async with self._hygienic_stdio_client(self._stdio_params()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.get_prompt(name, arguments)
        return result.model_dump(mode="json", exclude_none=False)

    def list_prompts(self) -> list[dict[str, Any]]:
        return asyncio.run(self._async_list_prompts())

    async def _async_list_prompts(self) -> list[dict[str, Any]]:
        from mcp import ClientSession

        async with self._hygienic_stdio_client(self._stdio_params()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.list_prompts()
        return [p.model_dump(mode="json", exclude_none=False) for p in result.prompts]

    def list_resources(self) -> list[dict[str, Any]]:
        return asyncio.run(self._async_list_resources())

    async def _async_list_resources(self) -> list[dict[str, Any]]:
        from mcp import ClientSession

        async with self._hygienic_stdio_client(self._stdio_params()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.list_resources()
        return [r.model_dump(mode="json", exclude_none=False) for r in result.resources]

    def list_resource_templates(self) -> list[dict[str, Any]]:
        return asyncio.run(self._async_list_resource_templates())

    async def _async_list_resource_templates(self) -> list[dict[str, Any]]:
        from mcp import ClientSession

        async with self._hygienic_stdio_client(self._stdio_params()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.list_resource_templates()
        return [
            t.model_dump(mode="json", exclude_none=False)
            for t in result.resourceTemplates
        ]

    def read_resource(self, uri: str) -> dict[str, Any]:
        return asyncio.run(self._async_read_resource(uri))

    async def _async_read_resource(self, uri: str) -> dict[str, Any]:
        from mcp import ClientSession
        from pydantic import AnyUrl

        async with self._hygienic_stdio_client(self._stdio_params()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.read_resource(AnyUrl(uri))
        return result.model_dump(mode="json", exclude_none=False)


# Phase 69 Plan 03 — client-side OAuth opt-in env var.
# Mirrors the server's AGENT_BRAIN_AUTH naming convention (config.py AuthMode).
# Default OFF: basic/none deployments never get a surprise browser launch
# (Context decision A). Set AGENT_BRAIN_MCP_AUTH=oauth to enable.
MCP_CLIENT_AUTH_ENV = "AGENT_BRAIN_MCP_AUTH"


class McpHttpBackend:
    """CLI-side backend that talks to agent-brain-mcp over Streamable HTTP.

    Phase 57 wired: all 10 BackendClient methods + a deliberate
    ``reset()`` raise — same shape as ``McpStdioBackend`` but uses
    ``mcp.client.streamable_http.streamablehttp_client`` instead of
    ``stdio_client``. Each public method uses Pattern A:
    ``asyncio.run(self._async_*())`` per call.

    Phase 69 adds a single ``_http_session()`` async context manager that
    centralises all 17 former per-method transport call sites and injects an
    optional ``OAuthClientProvider`` via the ``auth=`` seam (Context decision
    B).  When ``AGENT_BRAIN_MCP_AUTH=oauth`` is unset (the default),
    ``auth=None`` and behaviour is byte-identical to pre-Phase-69
    (Context decision A).

    Structurally satisfies the BackendClient Protocol at
    agent_brain_cli.client.protocol.BackendClient (Plan 56-02).

    Args:
        url: Full HTTP URL of the MCP listener including the mount path,
            e.g. "http://127.0.0.1:9999/mcp" (the v2 default mount path
            is /mcp per agent_brain_mcp.http.MCP_MOUNT_PATH). Loopback
            only — design doc §1.3 explicitly defers public-bind auth to
            v10.4 (#188).
        timeout: Per-request timeout in seconds. Default 30.0 matches
            DocServeClient's default. Currently advisory — the MCP SDK
            transport does not surface a configurable per-call timeout;
            Phase 60 may wire this through if the SDK adds the knob.
        state_dir: Project state directory.  Used for mcp.runtime.json URL
            discovery (Phase 58) and as the ``FileTokenStorage`` root when
            ``AGENT_BRAIN_MCP_AUTH=oauth`` (Phase 69).
    """

    def __init__(
        self,
        url: str | None = None,
        *,
        timeout: float = 30.0,
        state_dir: Path | None = None,
    ) -> None:
        """CLI-side backend that talks to agent-brain-mcp over Streamable HTTP.

        Args:
            url: Full HTTP URL of the MCP listener including the mount path,
                e.g. "http://127.0.0.1:9999/mcp". When None, discovery is
                attempted via ``state_dir/mcp.runtime.json`` (Phase 58 §2.4).
            timeout: Per-request timeout in seconds (advisory).
            state_dir: Project state directory used for mcp.runtime.json
                discovery when ``url`` is None (Phase 58 CLI-MCP-08) and for
                FileTokenStorage when OAuth is enabled (Phase 69 Plan 03).

        Raises:
            ValueError: when both ``url`` and ``state_dir`` are None.
            RuntimeError: when ``url`` is None and the discovery file is
                missing or malformed (verbatim v3 design doc §3.5 wording).
        """
        if url is None:
            if state_dir is None:
                raise ValueError("must pass either url or state_dir")
            url = self._discover_url(state_dir)
        self.url = url
        self.timeout = timeout
        self._closed = False
        # Phase 69 Plan 03 — OAuth opt-in + lazy provider cache.
        self._state_dir = state_dir
        self._oauth_enabled = os.environ.get(MCP_CLIENT_AUTH_ENV, "").lower() == "oauth"
        self._auth_provider: Any | None = None

    @staticmethod
    def _discover_url(state_dir: Path) -> str:
        """Resolve url from ``<state_dir>/mcp.runtime.json`` (Phase 58 §2.4).

        Lazy-imports ``agent_brain_cli.mcp_runtime`` to keep the dep
        direction soft (standalone agent-brain-mcp usage still works when
        the operator passes ``url`` explicitly).

        Raises:
            RuntimeError: when agent-brain-cli is not installed, the
                discovery file is missing, or it is malformed
                (missing/invalid host or port).
        """
        try:
            from agent_brain_cli.mcp_runtime import (
                MCP_RUNTIME_FILE,
                read_mcp_runtime,
            )
        except ImportError as exc:
            raise RuntimeError(
                "agent-brain-cli not installed; pass url explicitly"
            ) from exc

        runtime = read_mcp_runtime(state_dir)
        if runtime is None:
            raise RuntimeError(
                f"discovery file not found at {state_dir}/{MCP_RUNTIME_FILE}; "
                f"run 'agent-brain mcp start' or pass --mcp-url"
            )
        host = runtime.get("host")
        port = runtime.get("port")
        if not isinstance(host, str) or not isinstance(port, int):
            raise RuntimeError(
                f"mcp.runtime.json at {state_dir}/{MCP_RUNTIME_FILE} is "
                f"malformed: missing host/port"
            )
        return f"http://{host}:{port}/mcp"

    def __enter__(self) -> McpHttpBackend:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._closed = True

    # ------------------------------------------------------------------
    # Phase 69 Plan 03 — OAuth opt-in + single auth-injection seam
    # ------------------------------------------------------------------

    def _get_auth(self) -> httpx.Auth | None:
        """Return the OAuthClientProvider when OAuth is enabled, else None.

        Builds the provider lazily ONCE per McpHttpBackend instance and
        caches it in ``self._auth_provider`` (reused across Pattern A calls
        within the same invocation).

        When ``AGENT_BRAIN_MCP_AUTH`` is not set to ``"oauth"`` (the default),
        returns ``None`` — auth=None in ``streamablehttp_client`` is the
        pre-Phase-69 byte-identical path (Context decision A, default OFF).

        Returns:
            ``OAuthClientProvider`` instance (implements ``httpx.Auth``) when
            OAuth is enabled, or ``None`` when disabled (the default).

        Raises:
            RuntimeError: When ``AGENT_BRAIN_MCP_AUTH=oauth`` is set but
                ``state_dir`` is ``None`` — token storage cannot be keyed
                without a state directory.
        """
        if not self._oauth_enabled:
            return None
        if self._state_dir is None:
            # OAuth requested but no state_dir to key storage → cannot persist
            raise RuntimeError(
                "AGENT_BRAIN_MCP_AUTH=oauth requires a state_dir for token storage"
            )
        if self._auth_provider is None:
            from agent_brain_mcp.oauth.oauth_client import build_oauth_client_provider

            self._auth_provider = build_oauth_client_provider(self.url, self._state_dir)
        return (
            self._auth_provider
        )  # noqa: return-value — Any stored, httpx.Auth returned

    @asynccontextmanager
    async def _http_session(self) -> AsyncIterator[Any]:
        """Single auth-injection seam for all HTTP tool calls (Context decision B).

        Centralises the 17 former per-method transport call sites; injects
        the optional ``OAuthClientProvider`` (``auth=None`` when OAuth opt-in
        is OFF — byte-identical to the pre-Phase-69 path).

        Preserves the lazy SDK import pattern so HTTP/UDS-only CLI invocations
        never pay the MCP SDK import cost when this method is not reached.

        Yields:
            An initialised ``ClientSession`` ready for tool calls and resource
            reads.
        """
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        auth = self._get_auth()
        async with streamablehttp_client(self.url, auth=auth) as (read, write, *_):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session

    def query(
        self,
        query_text: str,
        top_k: int = 5,
        similarity_threshold: float = 0.7,
        mode: str = "hybrid",
        alpha: float = 0.5,
        source_types: list[str] | None = None,
        languages: list[str] | None = None,
        file_paths: list[str] | None = None,
        explain: bool = False,
    ) -> QueryResponse:
        return asyncio.run(
            self._async_query(
                query_text=query_text,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
                mode=mode,
                alpha=alpha,
                source_types=source_types,
                languages=languages,
                file_paths=file_paths,
                explain=explain,
            )
        )

    async def _async_query(
        self,
        *,
        query_text: str,
        top_k: int,
        similarity_threshold: float,
        mode: str,
        alpha: float,
        source_types: list[str] | None,
        languages: list[str] | None,
        file_paths: list[str] | None,
        explain: bool,
    ) -> QueryResponse:
        """Async helper for :meth:`query` (Pattern A sync facade — Phase
        57 CONTEXT decision).

        Each call opens a fresh ``streamablehttp_client`` against
        ``self.url``, opens a ``ClientSession``, calls the
        ``search_documents`` tool, then tears down. Phase 60 owns the
        persistent-connection hygiene refinement; Phase 57 ships the
        simplest correct code path. Mirrors :meth:`McpStdioBackend.
        _async_query` exactly except for the transport call.
        """
        tool_args: dict[str, Any] = {
            "query": query_text,
            "top_k": top_k,
            "similarity_threshold": similarity_threshold,
            "mode": mode,
            "alpha": alpha,
            "explain": explain,
        }
        if source_types is not None:
            tool_args["source_types"] = source_types
        if languages is not None:
            tool_args["languages"] = languages
        if file_paths is not None:
            tool_args["file_paths"] = file_paths

        async with self._http_session() as session:
            result = await session.call_tool("search_documents", tool_args)

        return _coerce_query_response(_unwrap_payload(result))

    def index(
        self,
        folder_path: str,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        recursive: bool = True,
        include_code: bool = False,
        supported_languages: list[str] | None = None,
        code_chunk_strategy: str = "ast_aware",
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
        include_types: list[str] | None = None,
        generate_summaries: bool = False,
        force: bool = False,
        injector_script: str | None = None,
        folder_metadata_file: str | None = None,
        dry_run: bool = False,
        watch_mode: str | None = None,
        watch_debounce_seconds: int | None = None,
    ) -> IndexResponse:
        # See McpStdioBackend.index for the rationale behind the
        # narrowed body — the v2 MCP tool schemas use
        # additionalProperties=false and only a subset of the CLI
        # BackendClient.index parameters map to the wire.
        body, tool_name = _build_index_body(
            folder_path=folder_path,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            include_code=include_code,
            force=force,
            injector_script=injector_script,
            folder_metadata_file=folder_metadata_file,
            dry_run=dry_run,
        )
        return asyncio.run(self._async_index(tool_name=tool_name, body=body))

    async def _async_index(
        self, *, tool_name: str, body: dict[str, Any]
    ) -> IndexResponse:
        async with self._http_session() as session:
            result = await session.call_tool(tool_name, body)
        return _coerce_index_response(_unwrap_payload(result))

    def health(self) -> HealthStatus:
        return asyncio.run(self._async_health())

    async def _async_health(self) -> HealthStatus:
        async with self._http_session() as session:
            result = await session.call_tool("server_health", {})
        return _coerce_health_status(_unwrap_payload(result))

    def status(self) -> IndexingStatus:
        return asyncio.run(self._async_status())

    async def _async_status(self) -> IndexingStatus:
        from pydantic import AnyUrl

        async with self._http_session() as session:
            result = await session.read_resource(AnyUrl("corpus://status"))
        return _coerce_indexing_status(_unwrap_resource_body(result))

    def list_folders(self) -> list[FolderInfo]:
        return asyncio.run(self._async_list_folders())

    async def _async_list_folders(self) -> list[FolderInfo]:
        from pydantic import AnyUrl

        async with self._http_session() as session:
            result = await session.read_resource(AnyUrl("corpus://folders"))
        return _coerce_folder_info_list(_unwrap_resource_body(result))

    def delete_folder(self, folder_path: str) -> dict[str, Any]:
        return asyncio.run(self._async_delete_folder(folder_path))

    async def _async_delete_folder(self, folder_path: str) -> dict[str, Any]:
        # remove_folder is destructive — confirm=True pass-through per
        # CONTEXT discretion note (same shape as McpStdioBackend).
        async with self._http_session() as session:
            result = await session.call_tool(
                "remove_folder",
                {"folder_path": folder_path, "confirm": True},
            )
        return _unwrap_payload(result)

    def reset(self) -> IndexResponse:
        # Design doc §4-risks: reset() has no MCP tool equivalent in v2.
        # Phase 57+ open decision per CONTEXT.md §decisions — verbatim
        # wording duplicated across both backends by design (test pins
        # the literal string on each backend independently).
        raise NotImplementedError(
            "--transport mcp does not support reset; use --transport uds "
            "or http (no reset_index MCP tool in v2; v3 Phase 57+ open "
            "decision per design doc §4 risks)"
        )

    def list_jobs(self, limit: int = 20) -> list[dict[str, Any]]:
        return asyncio.run(self._async_list_jobs(limit))

    async def _async_list_jobs(self, limit: int) -> list[dict[str, Any]]:
        async with self._http_session() as session:
            result = await session.call_tool("list_jobs", {"limit": limit})
        payload = _unwrap_payload(result)
        jobs = payload.get("jobs", [])
        assert isinstance(jobs, list)
        return jobs

    def get_job(self, job_id: str) -> dict[str, Any]:
        return asyncio.run(self._async_get_job(job_id))

    async def _async_get_job(self, job_id: str) -> dict[str, Any]:
        from pydantic import AnyUrl

        async with self._http_session() as session:
            result = await session.read_resource(AnyUrl(f"job://{job_id}"))
        return _unwrap_resource_body(result)

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        return asyncio.run(self._async_cancel_job(job_id))

    async def _async_cancel_job(self, job_id: str) -> dict[str, Any]:
        # cancel_job is destructive — confirm=True pass-through (v1
        # §6.2 guard, same shape as McpStdioBackend).
        async with self._http_session() as session:
            result = await session.call_tool(
                "cancel_job", {"job_id": job_id, "confirm": True}
            )
        return _unwrap_payload(result)

    def cache_status(self) -> dict[str, Any]:
        return asyncio.run(self._async_cache_status())

    async def _async_cache_status(self) -> dict[str, Any]:
        async with self._http_session() as session:
            result = await session.call_tool("cache_status", {})
        return _unwrap_payload(result)

    def clear_cache(self) -> dict[str, Any]:
        return asyncio.run(self._async_clear_cache())

    async def _async_clear_cache(self) -> dict[str, Any]:
        # clear_cache is destructive — confirm=True pass-through
        # (Phase 54 Plan 03 guard, same shape as McpStdioBackend).
        async with self._http_session() as session:
            result = await session.call_tool("clear_cache", {"confirm": True})
        return _unwrap_payload(result)

    # --- Phase 59 Plan 02: McpBackend Protocol surface (wired) ---
    #
    # Same Pattern A shape as McpStdioBackend's wires above, but using
    # _http_session() (Phase 69 centralisation) instead of the former
    # per-method inline transport setup. The model_dump translation is
    # identical.

    def get_prompt(
        self, name: str, arguments: dict[str, str] | None = None
    ) -> dict[str, Any]:
        return asyncio.run(self._async_get_prompt(name, arguments))

    async def _async_get_prompt(
        self, name: str, arguments: dict[str, str] | None
    ) -> dict[str, Any]:
        async with self._http_session() as session:
            result = await session.get_prompt(name, arguments)
        dumped: dict[str, Any] = result.model_dump(mode="json", exclude_none=False)
        return dumped

    def list_prompts(self) -> list[dict[str, Any]]:
        return asyncio.run(self._async_list_prompts())

    async def _async_list_prompts(self) -> list[dict[str, Any]]:
        async with self._http_session() as session:
            result = await session.list_prompts()
        return [p.model_dump(mode="json", exclude_none=False) for p in result.prompts]

    def list_resources(self) -> list[dict[str, Any]]:
        return asyncio.run(self._async_list_resources())

    async def _async_list_resources(self) -> list[dict[str, Any]]:
        async with self._http_session() as session:
            result = await session.list_resources()
        return [r.model_dump(mode="json", exclude_none=False) for r in result.resources]

    def list_resource_templates(self) -> list[dict[str, Any]]:
        return asyncio.run(self._async_list_resource_templates())

    async def _async_list_resource_templates(self) -> list[dict[str, Any]]:
        async with self._http_session() as session:
            result = await session.list_resource_templates()
        return [
            t.model_dump(mode="json", exclude_none=False)
            for t in result.resourceTemplates
        ]

    def read_resource(self, uri: str) -> dict[str, Any]:
        return asyncio.run(self._async_read_resource(uri))

    async def _async_read_resource(self, uri: str) -> dict[str, Any]:
        from pydantic import AnyUrl

        async with self._http_session() as session:
            result = await session.read_resource(AnyUrl(uri))
        dumped: dict[str, Any] = result.model_dump(mode="json", exclude_none=False)
        return dumped


__all__: list[str] = ["ApiClient", "McpStdioBackend", "McpHttpBackend"]
