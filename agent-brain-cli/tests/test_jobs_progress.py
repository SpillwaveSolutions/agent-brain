"""Regression tests for #150 — jobs CLI handling of structured progress.

The server emits a ``JobProgress`` dict (``percent_complete`` computed field
plus ``files_processed`` / ``files_total``); the v10.0.4 CLI assumed a float
and crashed with ``TypeError: unsupported format string passed to dict``.
These tests pin the v10.0.5 behaviour.
"""

from __future__ import annotations

from typing import Any

import pytest

from agent_brain_cli.commands.jobs import _create_job_detail_panel, _format_progress


@pytest.mark.parametrize(
    ("progress", "total", "expected_in"),
    [
        (None, None, "-"),
        (None, 5, "-"),
        (0.0, None, "0.0%"),
        (42.5, None, "42.5%"),
        (42.5, 100, "42.5% (100 files)"),
        (
            {"percent_complete": 33.3, "files_processed": 5, "files_total": 15},
            None,
            "33.3% (5/15 files)",
        ),
        (
            {"percent_complete": 50.0, "files_processed": 0, "files_total": 0},
            None,
            "50.0%",
        ),
        ({"foo": "bar"}, None, "foo=bar"),
        ("unexpected_string", None, "unexpected_string"),
    ],
)
def test_format_progress_shapes(
    progress: Any, total: int | None, expected_in: str
) -> None:
    """#150 — _format_progress must never raise on any plausible payload."""
    assert _format_progress(progress, total) == expected_in


def test_create_job_detail_panel_with_structured_progress_dict() -> None:
    """The exact crash from #150: progress field is a dict, not a float."""
    job = {
        "job_id": "job_67905668063c",
        "status": "running",
        "progress": {
            "percent_complete": 33.3,
            "files_processed": 5,
            "files_total": 15,
            "chunks_created": 120,
            "current_file": "docs/intro.md",
        },
        "total_files": 15,
        "processed_files": 5,
    }
    # Must not raise — this is the v10.0.4 regression.
    panel = _create_job_detail_panel(job)
    assert panel is not None


def test_create_job_detail_panel_with_legacy_float_progress() -> None:
    """Older servers that still send a float must keep working."""
    job = {
        "job_id": "job_legacy",
        "status": "running",
        "progress": 75.0,
        "total_files": 4,
        "processed_files": 3,
    }
    panel = _create_job_detail_panel(job)
    assert panel is not None


def test_create_job_detail_panel_with_missing_progress() -> None:
    """A queued job has no progress field yet — must not crash."""
    job = {"job_id": "job_pending", "status": "queued"}
    panel = _create_job_detail_panel(job)
    assert panel is not None
