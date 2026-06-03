"""Phase 54 Plan 01 — schema contract tests for the 9 remaining tools.

For every input model:
    * minimal valid construction succeeds
    * passing an extra field raises ``ValidationError`` (Pydantic-runtime
      enforcement of ``model_config = ConfigDict(extra="forbid")``)
    * the JSON Schema returned by :func:`json_schema` contains
      ``"additionalProperties": false`` (MCP-client pre-validation gate)
    * each numeric / Literal constraint pins the value documented in the
      plan + CONTEXT (e.g., ``WaitForJobInput.poll_interval_seconds`` is
      ``ge=0.5, le=2.0``).

For every output model: representative round-trip.

These tests are the locking mechanism for Plans 02/03/04 — once committed,
they refuse to silently let downstream agents drift a constraint
without updating the test (which would force re-review).
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from agent_brain_mcp.schemas import (
    AddDocumentsInput,
    AddDocumentsOutput,
    CacheStatusInput,
    CacheStatusOutput,
    ClearCacheInput,
    ClearCacheOutput,
    ExplainResultInput,
    ExplainResultOutput,
    FolderInfoMcp,
    InjectDocumentsInput,
    InjectDocumentsOutput,
    ListFileTypesInput,
    ListFileTypesOutput,
    ListFoldersInput,
    ListFoldersOutput,
    RemoveFolderInput,
    RemoveFolderOutput,
    WaitForJobInput,
    WaitForJobOutput,
    json_schema,
)

# Sentinel argument-bags for "minimal valid construction" — one per input
# model. Empty dict for the 4 no-arg inputs; minimal required-only payload
# for the rest.
_MINIMAL_VALID: dict[type[BaseModel], dict[str, object]] = {
    ExplainResultInput: {"query": "auth flow", "chunk_id": "chunk_001"},
    AddDocumentsInput: {"paths": ["/abs/repo/docs"]},
    InjectDocumentsInput: {
        "folder_path": "/abs/repo",
        "injector_script": "/abs/repo/inject.py",
    },
    WaitForJobInput: {"job_id": "job_abc"},
    ListFoldersInput: {},
    RemoveFolderInput: {"folder_path": "/abs/repo/docs", "confirm": True},
    CacheStatusInput: {},
    ClearCacheInput: {"confirm": True},
    ListFileTypesInput: {},
}


_ALL_INPUTS: list[type[BaseModel]] = list(_MINIMAL_VALID.keys())


# ----------------------------- Universal input contracts ------------------


@pytest.mark.parametrize("model", _ALL_INPUTS, ids=lambda m: m.__name__)
def test_input_minimal_construction_succeeds(model: type[BaseModel]) -> None:
    """Every input model accepts the documented minimal-required payload."""
    instance = model(**_MINIMAL_VALID[model])  # type: ignore[arg-type]
    # Round-trip through model_dump so any computed-field divergence trips
    # the test immediately rather than during downstream serialization.
    dumped = instance.model_dump()
    assert isinstance(dumped, dict)


@pytest.mark.parametrize("model", _ALL_INPUTS, ids=lambda m: m.__name__)
def test_input_rejects_extra_field(model: type[BaseModel]) -> None:
    """``ConfigDict(extra='forbid')`` is wired on every input model."""
    payload = dict(_MINIMAL_VALID[model])
    payload["totally_unknown_field"] = "drift_detector"
    with pytest.raises(ValidationError) as exc_info:
        model(**payload)
    # Pydantic v2 names this error "extra_forbidden" in error details.
    assert any(err["type"] == "extra_forbidden" for err in exc_info.value.errors())


@pytest.mark.parametrize("model", _ALL_INPUTS, ids=lambda m: m.__name__)
def test_input_json_schema_has_additional_properties_false(
    model: type[BaseModel],
) -> None:
    """MCP-client pre-validation gate — ``additionalProperties: false``."""
    schema = json_schema(model)
    assert schema.get("additionalProperties") is False, model.__name__


# ----------------------------- Per-input constraint pins ------------------


class TestExplainResultInputConstraints:
    """ExplainResultInput — TOOL-01, CONTEXT decision F."""

    def test_default_mode_is_hybrid(self) -> None:
        m = ExplainResultInput(query="q", chunk_id="c")
        assert m.mode == "hybrid"

    def test_default_top_k_is_50(self) -> None:
        m = ExplainResultInput(query="q", chunk_id="c")
        assert m.top_k == 50

    def test_top_k_le_200(self) -> None:
        ExplainResultInput(query="q", chunk_id="c", top_k=200)
        with pytest.raises(ValidationError):
            ExplainResultInput(query="q", chunk_id="c", top_k=201)

    def test_top_k_ge_1(self) -> None:
        with pytest.raises(ValidationError):
            ExplainResultInput(query="q", chunk_id="c", top_k=0)

    def test_alpha_default_is_half(self) -> None:
        m = ExplainResultInput(query="q", chunk_id="c")
        assert m.alpha == 0.5

    def test_alpha_bounds(self) -> None:
        ExplainResultInput(query="q", chunk_id="c", alpha=0.0)
        ExplainResultInput(query="q", chunk_id="c", alpha=1.0)
        with pytest.raises(ValidationError):
            ExplainResultInput(query="q", chunk_id="c", alpha=-0.01)
        with pytest.raises(ValidationError):
            ExplainResultInput(query="q", chunk_id="c", alpha=1.01)

    def test_mode_literal_rejects_unknown(self) -> None:
        with pytest.raises(ValidationError):
            ExplainResultInput(query="q", chunk_id="c", mode="rerank")


class TestAddDocumentsInputConstraints:
    """AddDocumentsInput — TOOL-02, allow_external intentionally absent (#180)."""

    def test_paths_min_length_1(self) -> None:
        with pytest.raises(ValidationError):
            AddDocumentsInput(paths=[])

    def test_force_default_false(self) -> None:
        m = AddDocumentsInput(paths=["/x"])
        assert m.force is False

    def test_no_allow_external_field(self) -> None:
        """Issue #180 removed allow_external server-side — expose it MCP-side
        and we silently drift."""
        assert "allow_external" not in AddDocumentsInput.model_fields


class TestInjectDocumentsInputConstraints:
    """InjectDocumentsInput — TOOL-03, CONTEXT decision D."""

    def test_requires_injector_or_metadata(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            InjectDocumentsInput(folder_path="/x")
        assert "At least one of injector_script" in str(exc_info.value)

    def test_injector_alone_accepted(self) -> None:
        InjectDocumentsInput(folder_path="/x", injector_script="/inj.py")

    def test_metadata_alone_accepted(self) -> None:
        InjectDocumentsInput(folder_path="/x", folder_metadata_file="/meta.json")

    def test_both_accepted(self) -> None:
        InjectDocumentsInput(
            folder_path="/x",
            injector_script="/inj.py",
            folder_metadata_file="/meta.json",
        )

    def test_no_allow_external_field(self) -> None:
        """Issue #180 also removed allow_external from POST /index/; the
        inject flow piggybacks on that same endpoint."""
        assert "allow_external" not in InjectDocumentsInput.model_fields

    def test_dry_run_default_false(self) -> None:
        m = InjectDocumentsInput(folder_path="/x", injector_script="/i.py")
        assert m.dry_run is False

    def test_include_code_default_true(self) -> None:
        m = InjectDocumentsInput(folder_path="/x", injector_script="/i.py")
        assert m.include_code is True

    def test_chunk_size_bounds_mirror_indexrequest(self) -> None:
        # IndexRequest: ge=128, le=2048
        InjectDocumentsInput(
            folder_path="/x", injector_script="/i.py", chunk_size=128
        )
        InjectDocumentsInput(
            folder_path="/x", injector_script="/i.py", chunk_size=2048
        )
        with pytest.raises(ValidationError):
            InjectDocumentsInput(
                folder_path="/x", injector_script="/i.py", chunk_size=127
            )
        with pytest.raises(ValidationError):
            InjectDocumentsInput(
                folder_path="/x", injector_script="/i.py", chunk_size=2049
            )

    def test_chunk_overlap_bounds_mirror_indexrequest(self) -> None:
        # IndexRequest: ge=0, le=200
        InjectDocumentsInput(
            folder_path="/x", injector_script="/i.py", chunk_overlap=0
        )
        InjectDocumentsInput(
            folder_path="/x", injector_script="/i.py", chunk_overlap=200
        )
        with pytest.raises(ValidationError):
            InjectDocumentsInput(
                folder_path="/x", injector_script="/i.py", chunk_overlap=-1
            )
        with pytest.raises(ValidationError):
            InjectDocumentsInput(
                folder_path="/x", injector_script="/i.py", chunk_overlap=201
            )

    def test_folder_path_min_length(self) -> None:
        with pytest.raises(ValidationError):
            InjectDocumentsInput(folder_path="", injector_script="/i.py")


class TestWaitForJobInputConstraints:
    """WaitForJobInput — TOOL-04, CONTEXT decision E (MCP spec ≤2s cadence)."""

    def test_poll_interval_default_1s(self) -> None:
        m = WaitForJobInput(job_id="j")
        assert m.poll_interval_seconds == 1.0

    def test_poll_interval_ge_half(self) -> None:
        WaitForJobInput(job_id="j", poll_interval_seconds=0.5)
        with pytest.raises(ValidationError):
            WaitForJobInput(job_id="j", poll_interval_seconds=0.49)

    def test_poll_interval_le_two(self) -> None:
        WaitForJobInput(job_id="j", poll_interval_seconds=2.0)
        with pytest.raises(ValidationError):
            WaitForJobInput(job_id="j", poll_interval_seconds=2.01)

    def test_timeout_seconds_default_none(self) -> None:
        m = WaitForJobInput(job_id="j")
        assert m.timeout_seconds is None

    def test_timeout_seconds_ge_one(self) -> None:
        WaitForJobInput(job_id="j", timeout_seconds=1)
        with pytest.raises(ValidationError):
            WaitForJobInput(job_id="j", timeout_seconds=0)


class TestDestructiveConfirmGuards:
    """RemoveFolderInput + ClearCacheInput — destructive ops require confirm=True."""

    def test_remove_folder_rejects_missing_confirm(self) -> None:
        with pytest.raises(ValidationError):
            RemoveFolderInput(folder_path="/x")  # type: ignore[call-arg]

    def test_remove_folder_rejects_confirm_false(self) -> None:
        with pytest.raises(ValidationError):
            RemoveFolderInput(folder_path="/x", confirm=False)  # type: ignore[arg-type]

    def test_remove_folder_accepts_confirm_true(self) -> None:
        m = RemoveFolderInput(folder_path="/x", confirm=True)
        assert m.confirm is True

    def test_remove_folder_path_min_length(self) -> None:
        with pytest.raises(ValidationError):
            RemoveFolderInput(folder_path="", confirm=True)

    def test_clear_cache_rejects_missing_confirm(self) -> None:
        with pytest.raises(ValidationError):
            ClearCacheInput()  # type: ignore[call-arg]

    def test_clear_cache_rejects_confirm_false(self) -> None:
        with pytest.raises(ValidationError):
            ClearCacheInput(confirm=False)  # type: ignore[arg-type]

    def test_clear_cache_accepts_confirm_true(self) -> None:
        m = ClearCacheInput(confirm=True)
        assert m.confirm is True


class TestEmptyInputs:
    """No-arg inputs: ListFoldersInput, CacheStatusInput, ListFileTypesInput.

    Should accept ``model()`` and reject every positional/keyword arg
    (extra=forbid).
    """

    def test_list_folders_accepts_no_args(self) -> None:
        ListFoldersInput()

    def test_cache_status_accepts_no_args(self) -> None:
        CacheStatusInput()

    def test_list_file_types_accepts_no_args(self) -> None:
        ListFileTypesInput()


# ----------------------------- Output round-trips -------------------------


class TestExplainResultOutput:
    def test_round_trip_minimal(self) -> None:
        m = ExplainResultOutput(
            chunk_id="c1", text="t", source="s.py", score=0.9, reason="bm25 hit"
        )
        d = m.model_dump()
        assert d["chunk_id"] == "c1"
        assert d["matched_terms"] is None
        assert d["graph_fallback"] is None

    def test_round_trip_full(self) -> None:
        m = ExplainResultOutput(
            chunk_id="c1",
            text="t",
            source="s.py",
            score=0.9,
            reason="hybrid fusion",
            matched_terms=["auth", "login"],
            fusion={"vector_score_weighted": 0.4, "bm25_score_weighted": 0.6},
            graph_path=["User", "calls", "login"],
            rerank_movement=2,
            graph_fallback=False,
        )
        dumped = m.model_dump()
        assert dumped["fusion"]["vector_score_weighted"] == 0.4


class TestAddDocumentsOutput:
    def test_round_trip(self) -> None:
        m = AddDocumentsOutput(job_id="j", status="queued", message="ok")
        assert m.job_id == "j"


class TestInjectDocumentsOutput:
    def test_round_trip_dry_run_shape(self) -> None:
        m = InjectDocumentsOutput(
            job_id="dry_run",
            status="completed",
            message="enriched 3/3 chunks",
        )
        assert m.job_id == "dry_run"
        assert m.status == "completed"


class TestWaitForJobOutput:
    def test_round_trip_terminal(self) -> None:
        m = WaitForJobOutput(
            job_id="j",
            status="done",
            progress_percent=100.0,
            message=None,
            started_at="2026-06-03T00:00:00Z",
            completed_at="2026-06-03T00:01:00Z",
            elapsed_seconds=60.0,
        )
        assert m.final is True

    def test_final_default_true(self) -> None:
        m = WaitForJobOutput(job_id="j", status="done", elapsed_seconds=1.0)
        assert m.final is True


class TestListFoldersOutput:
    def test_round_trip(self) -> None:
        m = ListFoldersOutput(
            folders=[
                FolderInfoMcp(
                    folder_path="/x",
                    chunk_count=10,
                    last_indexed="2026-06-03T00:00:00Z",
                ),
            ],
            total=1,
        )
        assert m.total == 1
        assert m.folders[0].watch_mode == "off"  # default mirror of FolderInfo

    def test_empty_default(self) -> None:
        m = ListFoldersOutput(total=0)
        assert m.folders == []

    def test_total_ge_zero(self) -> None:
        with pytest.raises(ValidationError):
            ListFoldersOutput(total=-1)


class TestRemoveFolderOutput:
    def test_uses_chunks_deleted_not_chunks_removed(self) -> None:
        """Mirrors FolderDeleteResponse 1:1 — field name is chunks_deleted."""
        assert "chunks_deleted" in RemoveFolderOutput.model_fields
        assert "chunks_removed" not in RemoveFolderOutput.model_fields

    def test_round_trip(self) -> None:
        m = RemoveFolderOutput(
            folder_path="/x", chunks_deleted=42, message="removed 42 chunks"
        )
        assert m.chunks_deleted == 42


class TestCacheStatusOutput:
    def test_round_trip(self) -> None:
        m = CacheStatusOutput(
            hits=10,
            misses=2,
            hit_rate=0.83,
            mem_entries=12,
            entry_count=1234,
            size_bytes=4096,
        )
        assert m.hits == 10

    def test_allows_extra_for_future_server_keys(self) -> None:
        """ConfigDict(extra='allow') so future server additions to the
        cache-status payload don't break MCP clients."""
        m = CacheStatusOutput(
            hits=1,
            misses=1,
            hit_rate=0.5,
            mem_entries=1,
            entry_count=1,
            size_bytes=1,
            future_field="extra",  # type: ignore[call-arg]
        )
        assert m.model_dump()["future_field"] == "extra"


class TestClearCacheOutput:
    def test_round_trip(self) -> None:
        m = ClearCacheOutput(count=42, size_bytes=4096, size_mb=0.0039)
        assert m.count == 42


class TestListFileTypesOutput:
    def test_round_trip(self) -> None:
        presets = {"python": ["*.py"], "docs": ["*.md"]}
        m = ListFileTypesOutput(presets=presets, preset_count=2, extension_count=2)
        assert m.preset_count == 2
        assert m.presets["python"] == ["*.py"]
