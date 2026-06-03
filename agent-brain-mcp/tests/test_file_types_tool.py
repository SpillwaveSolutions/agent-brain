"""Phase 54 Plan 02 — handler tests for ``list_file_types`` (TOOL-09).

The handler is the only Phase 54 tool with NO HTTP roundtrip
(CONTEXT decision H — the preset table is pure static data vendored
from the CLI). Tests therefore use a dummy ``ApiClient`` that would
explode if any HTTP method was called on it — a positive check that
the handler is genuinely fetch-free.
"""

from __future__ import annotations

from typing import Any

import httpx

from agent_brain_mcp.client import ApiClient
from agent_brain_mcp.schemas import ListFileTypesInput
from agent_brain_mcp.tools.file_types import (
    FILE_TYPE_PRESETS,
    handle_list_file_types,
)


def _make_unused_client() -> tuple[ApiClient, list[httpx.Request]]:
    """Return an ``ApiClient`` + captured-request list. If the handler
    issues an HTTP call (which would violate decision H), the captured
    list will be non-empty and the test fails.
    """
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(500, json={"detail": "list_file_types must not HTTP"})

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, base_url="http://test-agent-brain")
    return ApiClient(client), captured


class TestListFileTypesHandler:
    def test_returns_full_vendored_dict(self) -> None:
        api, captured = _make_unused_client()
        out = handle_list_file_types(api, ListFileTypesInput())
        assert out.presets == FILE_TYPE_PRESETS
        # No HTTP — pure static data per CONTEXT decision H.
        assert captured == []

    def test_preset_count_matches_dict_size(self) -> None:
        api, _captured = _make_unused_client()
        out = handle_list_file_types(api, ListFileTypesInput())
        assert out.preset_count == len(FILE_TYPE_PRESETS)
        assert out.preset_count >= 11  # CLI baseline (Plan 01 floor)

    def test_extension_count_matches_total_patterns(self) -> None:
        api, _captured = _make_unused_client()
        out = handle_list_file_types(api, ListFileTypesInput())
        expected = sum(len(v) for v in FILE_TYPE_PRESETS.values())
        assert out.extension_count == expected
        # Sanity bound — CLI ships ≥ 30 patterns across the 16 presets.
        assert out.extension_count >= 30


class TestListFileTypesDefensiveCopy:
    def test_mutating_output_does_not_mutate_vendored_dict(self) -> None:
        """The handler returns a defensive copy of FILE_TYPE_PRESETS so
        callers cannot accidentally corrupt the module-level state.
        """
        api, _captured = _make_unused_client()
        out = handle_list_file_types(api, ListFileTypesInput())
        # Mutate the output's "python" entry — should NOT touch the
        # module-level dict.
        out.presets["python"].append("*.mutation_canary")
        assert "*.mutation_canary" not in FILE_TYPE_PRESETS["python"]

        # Adding a new preset key on the output must not leak either.
        out.presets["__fake__"] = ["*.canary"]
        assert "__fake__" not in FILE_TYPE_PRESETS


def _assert_no_metadata_keys(out: Any) -> None:
    """Helper guarding against accidental field drift."""
    # ``presets`` is a flat dict[str, list[str]] — no nested metadata.
    for name, patterns in out.presets.items():
        assert isinstance(name, str)
        assert isinstance(patterns, list)
        for p in patterns:
            assert isinstance(p, str)
            assert p.startswith("*.")
