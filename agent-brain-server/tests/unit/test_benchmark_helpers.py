"""Unit tests for benchmark helper functions in scripts/query_benchmark.py.

Imports the helper functions by adding the scripts/ directory to sys.path
so the tests can run from agent-brain-server without any packaging.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

# Add scripts/ directory to path for import
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts"))

from query_benchmark import (  # noqa: E402
    DEFAULT_MODES,
    MODE_SUPPORT_MATRIX,
    build_json_output,
    build_run_metadata,
    compute_stats,
    format_mode_status,
    get_mode_support,
)


class TestComputeStats:
    """Tests for the compute_stats helper function."""

    def test_empty_list_returns_zeros(self) -> None:
        """compute_stats([]) should return all-zero dict."""
        result = compute_stats([])
        assert result["p50"] == 0.0
        assert result["p95"] == 0.0
        assert result["p99"] == 0.0
        assert result["mean"] == 0.0
        assert result["min"] == 0.0
        assert result["max"] == 0.0
        assert result["count"] == 0
        assert result["qps"] == 0.0

    def test_single_value(self) -> None:
        """Single-element list should have all percentiles equal to that value."""
        result = compute_stats([100.0])
        assert result["p50"] == 100.0
        assert result["p95"] == 100.0
        assert result["p99"] == 100.0
        assert result["mean"] == 100.0
        assert result["count"] == 1.0

    def test_multiple_values_p50(self) -> None:
        """p50 for [10, 20, 30, 40, 50] should be around 30."""
        result = compute_stats([10.0, 20.0, 30.0, 40.0, 50.0])
        # p50 uses nearest-rank; for 5 elements idx = int(0.50 * 5) = 2 → sorted[2] = 30
        assert result["p50"] == 30.0

    def test_qps_calculation(self) -> None:
        """QPS should be count * 1000 / total_ms."""
        latencies = [100.0, 200.0, 300.0]
        result = compute_stats(latencies)
        total_ms = sum(latencies)  # 600 ms
        expected_qps = len(latencies) * 1000.0 / total_ms  # 3000/600 = 5.0
        assert abs(result["qps"] - expected_qps) < 0.01

    def test_min_max(self) -> None:
        """min and max should be the actual extreme values."""
        result = compute_stats([5.0, 10.0, 100.0])
        assert result["min"] == 5.0
        assert result["max"] == 100.0

    def test_count_reflects_input_length(self) -> None:
        """count should equal the number of latency measurements."""
        latencies = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
        result = compute_stats(latencies)
        assert result["count"] == float(len(latencies))

    def test_all_keys_present(self) -> None:
        """Result must contain all expected keys."""
        result = compute_stats([50.0, 100.0])
        expected_keys = {"p50", "p95", "p99", "mean", "min", "max", "count", "qps"}
        assert set(result.keys()) == expected_keys


class TestFormatModeStatus:
    """Tests for the format_mode_status helper function."""

    def test_ok_status(self) -> None:
        """format_mode_status for 'ok' should return expected dict."""
        result = format_mode_status("vector", "ok")
        assert result["mode"] == "vector"
        assert result["status"] == "ok"
        assert result["reason"] == ""

    def test_unsupported_with_reason(self) -> None:
        """Unsupported status with reason should preserve reason."""
        result = format_mode_status("graph", "unsupported", "Chroma-only")
        assert result["mode"] == "graph"
        assert result["status"] == "unsupported"
        assert result["reason"] == "Chroma-only"

    def test_error_status(self) -> None:
        """Error status should be captured correctly."""
        result = format_mode_status("multi", "error", "connection timeout")
        assert result["status"] == "error"
        assert result["reason"] == "connection timeout"

    def test_all_keys_present(self) -> None:
        """Result must always have mode, status, reason keys."""
        result = format_mode_status("bm25", "ok")
        assert "mode" in result
        assert "status" in result
        assert "reason" in result


class TestBuildRunMetadata:
    """Tests for the build_run_metadata helper function."""

    def _make_metadata(self, **kwargs: object) -> dict:
        """Build metadata with sensible defaults."""
        health_data: dict = kwargs.get(  # type: ignore[assignment]
            "health_data",
            {"storage_backend": "chroma", "graph_enabled": True},
        )
        return build_run_metadata(
            server_url=str(kwargs.get("server_url", "http://127.0.0.1:8000")),
            health_data=health_data,
            chunk_count=int(kwargs.get("chunk_count", 100)),
            iterations=int(kwargs.get("iterations", 20)),
            warmups=int(kwargs.get("warmups", 3)),
            corpus_folders=list(  # type: ignore[arg-type]
                kwargs.get("corpus_folders", ["/docs"])
            ),
        )

    def test_metadata_has_all_required_fields(self) -> None:
        """Metadata must include all required fields for reproducibility."""
        result = self._make_metadata()
        required_keys = {
            "date",
            "os",
            "python_version",
            "backend",
            "graph_enabled",
            "iterations",
            "warmups",
            "corpus_identity",
            "chunk_count",
        }
        for key in required_keys:
            assert key in result, f"Missing required field: {key}"

    def test_metadata_date_is_iso(self) -> None:
        """date field should parse as a valid ISO 8601 datetime."""
        result = self._make_metadata()
        date_str = result["date"]
        # Should parse without error
        parsed = datetime.fromisoformat(str(date_str))
        assert parsed.tzinfo is not None, "Date should be timezone-aware"

    def test_metadata_backend_from_health(self) -> None:
        """backend field should come from health_data.storage_backend."""
        result = self._make_metadata(
            health_data={"storage_backend": "postgres", "graph_enabled": False}
        )
        assert result["backend"] == "postgres"

    def test_metadata_chunk_count(self) -> None:
        """chunk_count should reflect the passed-in value."""
        result = self._make_metadata(chunk_count=42)
        assert result["chunk_count"] == 42

    def test_metadata_corpus_identity(self) -> None:
        """corpus_identity should match the corpus_folders argument."""
        folders = ["/home/user/project/docs", "/home/user/code"]
        result = self._make_metadata(corpus_folders=folders)
        assert result["corpus_identity"] == folders


class TestGetModeSupport:
    """Tests for the get_mode_support helper function."""

    def test_chroma_graph_enabled_all_supported(self) -> None:
        """All 5 modes should be supported for chroma with graph enabled."""
        for mode in DEFAULT_MODES:
            supported, reason = get_mode_support("chroma", True, mode)
            assert supported is True, f"Mode {mode!r} should be supported"
            assert reason == "", f"Mode {mode!r} should have no reason"

    def test_chroma_no_graph_graph_unsupported(self) -> None:
        """graph mode should be unsupported on chroma without GraphRAG."""
        supported, reason = get_mode_support("chroma", False, "graph")
        assert supported is False
        assert "requires GraphRAG" in reason

    def test_chroma_no_graph_other_modes_supported(self) -> None:
        """Non-graph modes should be supported on chroma without GraphRAG."""
        for mode in ["vector", "bm25", "hybrid", "multi"]:
            supported, reason = get_mode_support("chroma", False, mode)
            assert supported is True, f"Mode {mode!r} should be supported on chroma"

    def test_postgres_graph_unsupported(self) -> None:
        """graph mode should be unsupported on postgres backend."""
        supported, reason = get_mode_support("postgres", False, "graph")
        assert supported is False
        assert "Chroma-only" in reason

    def test_postgres_multi_annotated(self) -> None:
        """multi mode on postgres should be supported but annotated."""
        supported, reason = get_mode_support("postgres", False, "multi")
        assert supported is True
        assert "graph contribution absent" in reason

    def test_postgres_graph_enabled_graph_still_unsupported(self) -> None:
        """graph mode on postgres should be unsupported even with graph_enabled=True."""
        supported, reason = get_mode_support("postgres", True, "graph")
        assert supported is False
        assert "Chroma-only" in reason

    def test_unknown_backend_defaults_supported(self) -> None:
        """Unknown backend should default all modes to supported."""
        supported, reason = get_mode_support("unknown_backend", False, "graph")
        assert supported is True
        assert reason == ""

    def test_none_graph_enabled_treated_as_false(self) -> None:
        """None graph_enabled should be treated as False (bool(None) == False)."""
        supported, reason = get_mode_support("chroma", None, "graph")
        # None treated as False -> same as ("chroma", False)
        assert supported is False
        assert "requires GraphRAG" in reason

    def test_case_insensitive_backend(self) -> None:
        """Backend lookup should be case-insensitive."""
        supported_lower, _ = get_mode_support("chroma", True, "vector")
        supported_upper, _ = get_mode_support("CHROMA", True, "vector")
        assert supported_lower == supported_upper


class TestModeSupportMatrix:
    """Tests for the MODE_SUPPORT_MATRIX data structure itself."""

    def test_matrix_has_four_entries(self) -> None:
        """Matrix must have exactly 4 backend/graph combos."""
        assert len(MODE_SUPPORT_MATRIX) == 4

    def test_each_entry_has_five_modes(self) -> None:
        """Each matrix entry must have exactly 5 mode keys matching DEFAULT_MODES."""
        for key, modes in MODE_SUPPORT_MATRIX.items():
            assert set(modes.keys()) == set(DEFAULT_MODES), (
                f"Entry {key} has modes {set(modes.keys())}, "
                f"expected {set(DEFAULT_MODES)}"
            )

    def test_chroma_true_key_present(self) -> None:
        """Matrix must contain the ('chroma', True) key."""
        assert ("chroma", True) in MODE_SUPPORT_MATRIX

    def test_postgres_false_key_present(self) -> None:
        """Matrix must contain the ('postgres', False) key."""
        assert ("postgres", False) in MODE_SUPPORT_MATRIX

    def test_entries_are_tuples(self) -> None:
        """Mode values must be 2-tuples of (bool, str)."""
        for key, modes in MODE_SUPPORT_MATRIX.items():
            for mode_name, entry in modes.items():
                assert isinstance(entry, tuple), (
                    f"Entry [{key}][{mode_name!r}] is not a tuple"
                )
                assert len(entry) == 2, (
                    f"Entry [{key}][{mode_name!r}] must be a 2-tuple"
                )
                supported, reason = entry
                assert isinstance(supported, bool), (
                    f"Entry [{key}][{mode_name!r}] first element must be bool"
                )
                assert isinstance(reason, str), (
                    f"Entry [{key}][{mode_name!r}] second element must be str"
                )


class TestBuildJsonOutput:
    """Tests for the build_json_output function."""

    def _make_result(
        self, mode: str, status: str = "ok", reason: str = ""
    ) -> dict:
        """Build a minimal result dict as benchmark_mode would return."""
        return {
            "mode": mode,
            "status": status,
            "client_stats": compute_stats([]),
            "server_stats": compute_stats([]),
            "reason": reason,
        }

    def _make_metadata(self) -> dict:
        """Build a minimal metadata dict."""
        return {
            "date": datetime.now(timezone.utc).isoformat(),
            "backend": "chroma",
            "graph_enabled": True,
            "iterations": 20,
            "warmups": 3,
            "chunk_count": 100,
            "corpus_identity": ["/docs"],
        }

    def test_json_output_has_required_keys(self) -> None:
        """JSON output must have metadata, results, supported_modes, unsupported_modes."""
        results = [self._make_result(m) for m in DEFAULT_MODES]
        output = build_json_output(results, self._make_metadata())
        assert "metadata" in output
        assert "results" in output
        assert "supported_modes" in output
        assert "unsupported_modes" in output

    def test_unsupported_modes_listed(self) -> None:
        """Results with status 'unsupported' should appear in unsupported_modes list."""
        results = [
            self._make_result("vector", "ok"),
            self._make_result("bm25", "ok"),
            self._make_result("hybrid", "ok"),
            self._make_result("graph", "unsupported", "UNSUPPORTED: Chroma-only"),
            self._make_result("multi", "ok"),
        ]
        output = build_json_output(results, self._make_metadata())
        unsupported_modes = [u["mode"] for u in output["unsupported_modes"]]
        assert "graph" in unsupported_modes
        assert "vector" not in unsupported_modes

    def test_supported_modes_listed(self) -> None:
        """Results with status 'ok' should appear in supported_modes list."""
        results = [
            self._make_result("vector", "ok"),
            self._make_result("bm25", "ok"),
            self._make_result("graph", "unsupported", "UNSUPPORTED: requires GraphRAG"),
        ]
        output = build_json_output(results, self._make_metadata())
        assert "vector" in output["supported_modes"]
        assert "bm25" in output["supported_modes"]
        assert "graph" not in output["supported_modes"]

    def test_results_contains_all_input_rows(self) -> None:
        """results key should contain all input result dicts."""
        results = [self._make_result(m) for m in DEFAULT_MODES]
        output = build_json_output(results, self._make_metadata())
        assert len(output["results"]) == len(results)

    def test_metadata_preserved_in_output(self) -> None:
        """metadata in output should match the input metadata dict."""
        metadata = self._make_metadata()
        output = build_json_output([], metadata)
        assert output["metadata"] == metadata

    def test_unsupported_reason_included(self) -> None:
        """unsupported_modes entries must include the reason string."""
        results = [
            self._make_result("graph", "unsupported", "UNSUPPORTED: Chroma-only"),
        ]
        output = build_json_output(results, self._make_metadata())
        assert len(output["unsupported_modes"]) == 1
        assert output["unsupported_modes"][0]["reason"] == "UNSUPPORTED: Chroma-only"
