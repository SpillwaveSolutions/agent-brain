"""Phase 55 Plan 02 — single source of truth for the 16-tool contract matrix.

Both Layer 1 (in-process — :mod:`tests.test_each_tool`) and Layer 2
(SDK-driven — :mod:`tests.contract.test_tools_contract`) parametrize
over this list. Adding/removing tools updates exactly one place; both
layers re-run cleanly.

Each :class:`ToolCase` row pins:

* ``name`` — the tool's registered name (matches ``TOOL_REGISTRY`` key).
* ``sample_arguments`` — a minimal-valid invocation that satisfies the
  tool's :class:`pydantic.BaseModel` input model AND the
  ``_DEFAULT_RESPONSES`` stubs in :mod:`tests.conftest` (so the happy
  path actually round-trips through the fake backend).
* ``negative_arguments`` — an invalid invocation that exercises the
  inputSchema rejection branch (Phase 55 CONTEXT D-02 / VAL-01 §6.3).
  Most rows omit a required field; a few use wrong types where the
  required-field path is degenerate (e.g., a tool with all optional
  fields).
* ``expected_structured_keys`` — keys that MUST appear in the
  ``CallToolResult.structuredContent`` for the happy path. Derived
  from each tool's output model's required fields; optional
  ``None``-valued fields are still present after ``model_dump(mode=
  "json", exclude_none=False)`` (see ``server.call_tool`` line ~316).
* ``expected_error_code`` — MCP error code the negative branch should
  surface. Defaults to ``-32602`` (INVALID_PARAMS) per the v1 design
  doc §6.3 — every tool whose negative path doesn't use
  ``-32602`` overrides this field.

Backend-stub mapping (read alongside ``tests/conftest.py``):

* ``search_documents`` / ``explain_result`` → ``POST /query/`` returns
  chunk ``chunk_001`` (the explain-target match).
* ``query_count`` → ``GET /query/count``.
* ``server_health`` → ``GET /health/``.
* ``index_folder`` → ``POST /index/`` returns ``job_abc`` queued.
* ``add_documents`` → ``POST /index/add`` returns ``job_add_001``.
* ``inject_documents`` → ``POST /index/`` returns ``job_abc`` queued.
* ``get_job`` → ``GET /index/jobs/job_abc`` (status=running).
* ``list_jobs`` → ``GET /index/jobs/``.
* ``cancel_job`` → ``DELETE /index/jobs/job_abc`` returns cancelled=True.
* ``wait_for_job`` → ``GET /index/jobs/job_done`` (immediate terminal,
  so the polling loop exits in one iteration without sleeping).
* ``list_folders`` / ``remove_folder`` → ``GET / DELETE /index/folders/``.
* ``cache_status`` / ``clear_cache`` → ``GET / DELETE /index/cache/``.
* ``list_file_types`` → vendored ``FILE_TYPE_PRESETS`` (zero HTTP).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from agent_brain_mcp.errors import INVALID_PARAMS


@dataclass(frozen=True)
class ToolCase:
    """One row in the 16-tool matrix."""

    name: str
    sample_arguments: dict[str, object]
    negative_arguments: dict[str, object]
    expected_structured_keys: tuple[str, ...]
    expected_error_code: int = INVALID_PARAMS
    # When True, the negative path is allowed to either return
    # ``isError=True`` OR raise ``McpError``. Default True because both
    # paths are spec-conformant — the SDK may convert validation errors
    # to either shape depending on whether the inputSchema rejection
    # fires client-side or server-side.
    negative_may_raise: bool = field(default=True)


# ---------------------------------------------------------------------
# v1 tools (7) — covered by the original ``test_each_tool.py`` matrix
# pre-Plan 02. The sample_arguments rows match the v1 invocations
# verbatim so the Layer 1 refactor stays no-op for these entries.
# ---------------------------------------------------------------------
_V1_TOOLS: list[ToolCase] = [
    ToolCase(
        name="search_documents",
        sample_arguments={"query": "test", "mode": "hybrid"},
        # ``query`` is required (no default). Drop it to hit the
        # inputSchema rejection branch.
        negative_arguments={"mode": "hybrid"},
        expected_structured_keys=(
            "query",
            "mode",
            "total_results",
            "results",
        ),
    ),
    ToolCase(
        name="query_count",
        sample_arguments={},
        # ``QueryCountInput`` has ``extra=forbid`` — any unexpected
        # key triggers a Pydantic ``Extra inputs are not permitted``.
        negative_arguments={"unexpected_field": "x"},
        expected_structured_keys=("total_documents", "total_chunks"),
    ),
    ToolCase(
        name="index_folder",
        sample_arguments={"folder_path": "/tmp/test"},
        # ``folder_path`` required.
        negative_arguments={"force": True},
        expected_structured_keys=("job_id", "status", "folder_path"),
    ),
    ToolCase(
        name="get_job",
        sample_arguments={"job_id": "job_abc"},
        # ``job_id`` required.
        negative_arguments={},
        expected_structured_keys=("job_id", "status"),
    ),
    ToolCase(
        name="list_jobs",
        sample_arguments={"limit": 20},
        # ``limit`` is bounded ``ge=1, le=100``; 0 trips the constraint.
        negative_arguments={"limit": 0},
        expected_structured_keys=("jobs",),
    ),
    ToolCase(
        name="cancel_job",
        sample_arguments={"job_id": "job_abc", "confirm": True},
        # Missing required ``confirm: Literal[True]``.
        negative_arguments={"job_id": "job_abc"},
        expected_structured_keys=("job_id", "cancelled"),
    ),
    ToolCase(
        name="server_health",
        sample_arguments={},
        # ``ServerHealthInput`` is ``extra=forbid``.
        negative_arguments={"unexpected_field": "x"},
        expected_structured_keys=("status", "version"),
    ),
]


# ---------------------------------------------------------------------
# Phase 54 read-only tools (4 of 9) — TOOL-01 / TOOL-05 / TOOL-07 /
# TOOL-09. All four advertise ``readOnlyHint: True``.
# ---------------------------------------------------------------------
_PHASE_54_READ_ONLY_TOOLS: list[ToolCase] = [
    ToolCase(
        name="explain_result",
        # ``POST /query/`` stub returns chunk_id=chunk_001 (see
        # ``tests/conftest.py``). Matching that here keeps the
        # post-filter happy.
        sample_arguments={
            "query": "test",
            "chunk_id": "chunk_001",
            "mode": "hybrid",
        },
        # ``chunk_id`` required.
        negative_arguments={"query": "test", "mode": "hybrid"},
        expected_structured_keys=("chunk_id", "text", "source", "score", "reason"),
    ),
    ToolCase(
        name="list_folders",
        sample_arguments={},
        # ``ListFoldersInput`` is ``extra=forbid``.
        negative_arguments={"unexpected_field": "x"},
        expected_structured_keys=("folders", "total"),
    ),
    ToolCase(
        name="cache_status",
        sample_arguments={},
        # ``CacheStatusInput`` is ``extra=forbid``.
        negative_arguments={"unexpected_field": "x"},
        expected_structured_keys=(
            "hits",
            "misses",
            "hit_rate",
            "mem_entries",
            "entry_count",
            "size_bytes",
        ),
    ),
    ToolCase(
        name="list_file_types",
        sample_arguments={},
        # ``ListFileTypesInput`` is ``extra=forbid``.
        negative_arguments={"unexpected_field": "x"},
        expected_structured_keys=("presets", "preset_count", "extension_count"),
    ),
]


# ---------------------------------------------------------------------
# Phase 54 mutating tools (4 of 9) — TOOL-02 / TOOL-03 / TOOL-06 /
# TOOL-08. ``add_documents`` / ``inject_documents`` are job-spawning
# (``openWorldHint: True``); ``remove_folder`` / ``clear_cache`` are
# destructive (``destructiveHint: True``) and Pydantic-gated via
# ``confirm: Literal[True]``.
# ---------------------------------------------------------------------
_PHASE_54_MUTATING_TOOLS: list[ToolCase] = [
    ToolCase(
        name="add_documents",
        sample_arguments={"paths": ["/tmp/test"]},
        # ``paths`` is ``min_length=1``; empty list trips the constraint.
        negative_arguments={"paths": []},
        expected_structured_keys=("job_id", "status"),
    ),
    ToolCase(
        name="inject_documents",
        # ``@model_validator`` requires injector_script OR
        # folder_metadata_file; we supply the metadata path so no real
        # file is needed (the handler resolves but does not stat it;
        # the fake backend ignores the body).
        sample_arguments={
            "folder_path": "/tmp/test",
            "folder_metadata_file": "/tmp/test/meta.json",
        },
        # Both injector_script AND folder_metadata_file omitted →
        # @model_validator raises ValueError. The MCP server converts
        # ValidationError to McpError(INVALID_PARAMS) (see
        # server.call_tool ~line 287).
        negative_arguments={"folder_path": "/tmp/test"},
        expected_structured_keys=("job_id", "status"),
    ),
    ToolCase(
        name="remove_folder",
        sample_arguments={"folder_path": "/tmp/test", "confirm": True},
        # Missing required ``confirm: Literal[True]``.
        negative_arguments={"folder_path": "/tmp/test"},
        expected_structured_keys=("folder_path", "chunks_deleted", "message"),
    ),
    ToolCase(
        name="clear_cache",
        sample_arguments={"confirm": True},
        # Missing required ``confirm: Literal[True]``.
        negative_arguments={},
        expected_structured_keys=("count", "size_bytes", "size_mb"),
    ),
]


# ---------------------------------------------------------------------
# Phase 54 progress-emitting tool (1 of 9) — TOOL-04. The ONLY
# ``emits_progress=True`` entry; the only async handler.
# ---------------------------------------------------------------------
_PHASE_54_WAIT_TOOL: list[ToolCase] = [
    ToolCase(
        name="wait_for_job",
        # ``job_done`` is a terminal-status stub (status="completed")
        # so the polling loop exits in ONE iteration. Using ``job_abc``
        # would loop forever (status="running"). The fast poll interval
        # keeps the test snappy if the first poll race ever needed a
        # second iteration.
        sample_arguments={"job_id": "job_done", "poll_interval_seconds": 0.5},
        # ``job_id`` required.
        negative_arguments={"poll_interval_seconds": 1.0},
        expected_structured_keys=(
            "job_id",
            "status",
            "final",
            "elapsed_seconds",
        ),
    ),
]


# ---------------------------------------------------------------------
# Composite matrix — order matches the registry insertion order in
# ``agent_brain_mcp/tools/__init__.py::TOOL_REGISTRY``. Phase 55 plan 02
# acceptance: 16 entries, one per registered tool.
# ---------------------------------------------------------------------
TOOLS: list[ToolCase] = (
    _V1_TOOLS
    + _PHASE_54_READ_ONLY_TOOLS
    + _PHASE_54_MUTATING_TOOLS
    + _PHASE_54_WAIT_TOOL
)


# Self-pin: any future tool added to the registry MUST be added to
# the matrix or this assertion fires at import time (== before the
# parametrize decorator collects). Import-time guards beat
# "discovered at test time" because the test list is already locked.
def _assert_matrix_covers_registry() -> None:
    """Fail fast if the matrix and ``TOOL_REGISTRY`` drift apart."""
    from agent_brain_mcp.tools import TOOL_REGISTRY

    registry_names = set(TOOL_REGISTRY.keys())
    matrix_names = {case.name for case in TOOLS}
    missing = registry_names - matrix_names
    extra = matrix_names - registry_names
    if missing or extra:
        raise RuntimeError(
            "tests.contract._tool_matrix.TOOLS is out of sync with "
            "TOOL_REGISTRY. Update _tool_matrix.py to match.\n"
            f"  missing from matrix: {sorted(missing)}\n"
            f"  extra in matrix: {sorted(extra)}"
        )


_assert_matrix_covers_registry()


__all__ = ["TOOLS", "ToolCase"]
