"""Path-containment behavior of JobQueueService._validate_path.

Issue #180: the HTTP API no longer exposes ``allow_external`` as a per-request
query parameter. Path containment is now a deployment-time decision controlled
by ``settings.AGENT_BRAIN_ALLOW_EXTERNAL_PATHS``. These tests pin the
underlying ``_validate_path`` behavior so any future change has to think about
both modes explicitly.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from agent_brain_server.job_queue.job_service import JobQueueService


class TestValidatePath:
    """Direct exercise of JobQueueService._validate_path."""

    def test_internal_path_resolves_regardless_of_flag(self, tmp_path: Path) -> None:
        """A path under the project root resolves cleanly with allow_external=False."""
        service = JobQueueService(store=AsyncMock(), project_root=tmp_path)

        subdir = tmp_path / "docs"
        subdir.mkdir()

        resolved = service._validate_path(str(subdir), allow_external=False)
        assert resolved == subdir.resolve()

    def test_external_path_rejected_when_flag_false(self, tmp_path: Path) -> None:
        """A path outside the project root raises ValueError when not allowed."""
        service = JobQueueService(store=AsyncMock(), project_root=tmp_path)

        with tempfile.TemporaryDirectory() as elsewhere:
            with pytest.raises(ValueError) as exc:
                service._validate_path(elsewhere, allow_external=False)
            assert "outside project root" in str(exc.value)

    def test_external_path_allowed_when_flag_true(self, tmp_path: Path) -> None:
        """A path outside the project root resolves when allow_external=True."""
        service = JobQueueService(store=AsyncMock(), project_root=tmp_path)

        with tempfile.TemporaryDirectory() as elsewhere:
            resolved = service._validate_path(elsewhere, allow_external=True)
            assert resolved == Path(elsewhere).resolve()

    def test_no_project_root_skips_validation(self, tmp_path: Path) -> None:
        """When project_root is None, any path is accepted (legacy CLI mode)."""
        service = JobQueueService(store=AsyncMock(), project_root=None)

        with tempfile.TemporaryDirectory() as elsewhere:
            # External path is allowed even with allow_external=False
            # because there is no project root to compare against.
            resolved = service._validate_path(elsewhere, allow_external=False)
            assert resolved == Path(elsewhere).resolve()
