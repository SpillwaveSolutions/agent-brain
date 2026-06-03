"""Unit tests for ``handle_wait_for_job`` — Phase 54 Plan 04 TOOL-04.

Coverage areas (acceptance criteria from Plan 04):

1. Happy path — 3-step job lifecycle emits ≥3 progress notifications +
   final.
2. Failed terminal — status="failed" with final progress=1.0.
3. Cancelled terminal — status="cancelled" propagates through output.
4. Dry-run terminal — status="dry_run" treated as terminal.
5. Timeout — soft cap returns ``status="timeout"``, ``final=False``,
   does NOT raise.
6. Cancellation propagation — ``asyncio.CancelledError`` triggers a
   best-effort ``client.cancel_job`` call and re-raises.
7. Pydantic validation — ``poll_interval_seconds > 2.0`` rejected
   pre-handler (locked by Plan 01).
8. Notification shape — ``progress in [0, 1]``, ``total=1.0``,
   ``message`` round-trips.

Tests use a captured-notify mock + sync ``asyncio.to_thread``-wrapped
``client.get_job`` stubs. Polling cadence is overridden to 0.01s via
``poll_interval_seconds`` so tests run sub-second.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from agent_brain_mcp.schemas import WaitForJobInput, WaitForJobOutput
from agent_brain_mcp.tools.wait import handle_wait_for_job


class _CapturingNotifier:
    """Mock ``ProgressNotifier`` that records every notification."""

    def __init__(self) -> None:
        self.calls: list[tuple[float, float, str | None]] = []

    async def __call__(
        self, progress: float, total: float, message: str | None
    ) -> None:
        self.calls.append((progress, total, message))


def _make_client_yielding(records: list[dict[str, Any]]) -> MagicMock:
    """Build a mock ApiClient whose ``get_job`` returns each record in turn.

    The last record is repeated indefinitely after the queue drains so
    a terminal-status record at the tail keeps the handler from
    crashing on a queue-exhaustion edge case if the test miscounts.
    """
    client = MagicMock()
    iterator = iter(records)
    last = records[-1] if records else {}

    def _get_job(_job_id: str) -> dict[str, Any]:
        try:
            return next(iterator)
        except StopIteration:
            return last

    client.get_job.side_effect = _get_job
    return client


@pytest.mark.asyncio
class TestHappyPath:
    async def test_three_step_happy_path_emits_progress_then_returns(self) -> None:
        """3-step succeeded path → ≥3 progress emissions + 1 final.

        After the terminal poll, handler emits one MORE notification at
        progress=1.0 (the explicit final), so the call count is poll_count
        + 1 = 4 in the canonical case.
        """
        records = [
            {
                "job_id": "j1",
                "status": "running",
                "progress_percent": 25.0,
                "message": "Reading files",
            },
            {
                "job_id": "j1",
                "status": "running",
                "progress_percent": 75.0,
                "message": "Embedding chunks",
            },
            {
                "job_id": "j1",
                "status": "succeeded",
                "progress_percent": 100.0,
                "message": "Done.",
            },
        ]
        client = _make_client_yielding(records)
        notifier = _CapturingNotifier()
        args = WaitForJobInput(job_id="j1", poll_interval_seconds=0.5)

        output = await handle_wait_for_job(client, args, notify=notifier)

        # 3 polls → 3 per-poll notifications + 1 final = 4
        assert len(notifier.calls) == 4
        # First three carry the polled progress (0.25 / 0.75 / 1.0)
        progresses = [c[0] for c in notifier.calls]
        assert progresses[0] == pytest.approx(0.25)
        assert progresses[1] == pytest.approx(0.75)
        assert progresses[2] == pytest.approx(1.0)
        # Final emission is always 1.0
        assert progresses[-1] == pytest.approx(1.0)
        # Every emission carries total=1.0
        assert {c[1] for c in notifier.calls} == {1.0}
        # Output mirrors the terminal record + final/elapsed.
        assert output.status == "succeeded"
        assert output.final is True
        assert output.job_id == "j1"
        assert output.progress_percent == pytest.approx(100.0)
        assert output.elapsed_seconds >= 0.0
        # 3 polls means 2 sleeps between polls (post-third the
        # terminal-status branch returns before the next sleep).
        assert client.get_job.call_count == 3
        # No cancellation path was taken → no cancel_job
        client.cancel_job.assert_not_called()


@pytest.mark.asyncio
class TestTerminalStates:
    async def test_failed_terminal_returns_failed_output(self) -> None:
        records = [
            {
                "job_id": "j-fail",
                "status": "failed",
                "progress_percent": 42.0,
                "message": "Parse error in file.py",
            },
        ]
        client = _make_client_yielding(records)
        notifier = _CapturingNotifier()
        args = WaitForJobInput(job_id="j-fail", poll_interval_seconds=0.5)

        output = await handle_wait_for_job(client, args, notify=notifier)

        assert output.status == "failed"
        assert output.final is True
        # Last notification is the final (progress=1.0)
        assert notifier.calls[-1][0] == pytest.approx(1.0)
        # First (per-poll) notification carried the polled 0.42
        assert notifier.calls[0][0] == pytest.approx(0.42)

    async def test_cancelled_terminal_returns_cancelled_output(self) -> None:
        records = [
            {
                "job_id": "j-cancel",
                "status": "cancelled",
                "progress_percent": 17.0,
                "message": "Cancelled by user",
            },
        ]
        client = _make_client_yielding(records)
        notifier = _CapturingNotifier()
        args = WaitForJobInput(job_id="j-cancel", poll_interval_seconds=0.5)

        output = await handle_wait_for_job(client, args, notify=notifier)

        assert output.status == "cancelled"
        assert output.final is True

    async def test_dry_run_terminal_returns_dry_run_output(self) -> None:
        records = [
            {
                "job_id": "dry_run",
                "status": "dry_run",
                "progress_percent": 100.0,
                "message": "Validation report: 5 files OK, 0 errors",
            },
        ]
        client = _make_client_yielding(records)
        notifier = _CapturingNotifier()
        args = WaitForJobInput(job_id="dry_run", poll_interval_seconds=0.5)

        output = await handle_wait_for_job(client, args, notify=notifier)

        assert output.status == "dry_run"
        assert output.final is True
        assert output.job_id == "dry_run"

    async def test_completed_status_treated_as_terminal(self) -> None:
        """The server's actual ``JobStatus.DONE`` (= ``"done"``) wire value.

        Plan 04 module docstring documents that the terminal set is a
        superset to absorb server-version drift. This test pins it.
        """
        records = [
            {
                "job_id": "j-completed",
                "status": "completed",
                "progress_percent": 100.0,
                "message": "Complete",
            },
        ]
        client = _make_client_yielding(records)
        notifier = _CapturingNotifier()
        args = WaitForJobInput(job_id="j-completed", poll_interval_seconds=0.5)

        output = await handle_wait_for_job(client, args, notify=notifier)

        assert output.status == "completed"
        assert output.final is True

    async def test_done_status_treated_as_terminal(self) -> None:
        """Pin the ``JobStatus.DONE = "done"`` server-enum value."""
        records = [
            {
                "job_id": "j-done",
                "status": "done",
                "progress_percent": 100.0,
                "message": "All set",
            },
        ]
        client = _make_client_yielding(records)
        notifier = _CapturingNotifier()
        args = WaitForJobInput(job_id="j-done", poll_interval_seconds=0.5)

        output = await handle_wait_for_job(client, args, notify=notifier)

        assert output.status == "done"
        assert output.final is True


@pytest.mark.asyncio
class TestTimeout:
    async def test_timeout_returns_timeout_status_without_raising(self) -> None:
        """Soft timeout: last-known state + status=timeout + final=False."""
        # Job is perpetually running — we'll only poll twice before timeout.
        records = [
            {
                "job_id": "j-tmo",
                "status": "running",
                "progress_percent": 50.0,
                "message": "Working",
            },
        ] * 100  # plenty
        client = _make_client_yielding(records)
        notifier = _CapturingNotifier()
        args = WaitForJobInput(
            job_id="j-tmo",
            poll_interval_seconds=0.5,
            timeout_seconds=1,
        )

        # 1-second timeout with 0.5s poll cadence → expect about 2-3 polls.
        output = await handle_wait_for_job(client, args, notify=notifier)

        assert output.status == "timeout"
        assert output.final is False
        # Last-known progress carried through
        assert output.progress_percent == pytest.approx(50.0)
        assert output.job_id == "j-tmo"
        assert output.elapsed_seconds >= 1.0
        # No cancellation path → no cancel_job
        client.cancel_job.assert_not_called()


@pytest.mark.asyncio
class TestCancellationPropagation:
    async def test_cancelled_error_triggers_best_effort_cancel_job(self) -> None:
        """Handler asyncio.cancel()'ed → cancel_job called, CancelledError re-raised."""
        # Job never completes; we let the handler start polling then cancel it.
        records = [
            {
                "job_id": "j-cancel-propagate",
                "status": "running",
                "progress_percent": 10.0,
                "message": "Indexing",
            },
        ] * 100
        client = _make_client_yielding(records)
        notifier = _CapturingNotifier()
        args = WaitForJobInput(
            job_id="j-cancel-propagate",
            poll_interval_seconds=0.5,
        )

        task = asyncio.create_task(
            handle_wait_for_job(client, args, notify=notifier),
        )
        # Let the handler tick at least once.
        await asyncio.sleep(0.1)
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        # Best-effort cancel_job was called as part of cleanup.
        client.cancel_job.assert_called_once_with("j-cancel-propagate")

    async def test_cancelled_error_propagates_even_if_cancel_job_fails(
        self,
    ) -> None:
        """A failing best-effort cancel_job MUST NOT mask the original cancellation."""
        records = [
            {
                "job_id": "j-cancel-fail",
                "status": "running",
                "progress_percent": 5.0,
                "message": "Indexing",
            },
        ] * 100
        client = _make_client_yielding(records)
        # cancel_job raises (network down, server gone, whatever)
        client.cancel_job.side_effect = RuntimeError("backend unreachable")
        notifier = _CapturingNotifier()
        args = WaitForJobInput(
            job_id="j-cancel-fail",
            poll_interval_seconds=0.5,
        )

        task = asyncio.create_task(
            handle_wait_for_job(client, args, notify=notifier),
        )
        await asyncio.sleep(0.1)
        task.cancel()

        # The PRIMARY CancelledError MUST surface — cleanup failure is silent.
        with pytest.raises(asyncio.CancelledError):
            await task
        client.cancel_job.assert_called_once_with("j-cancel-fail")


class TestPydanticInputValidation:
    """Constraints on ``WaitForJobInput`` are locked by Plan 01.

    Plan 04 verifies them here so a Plan 01 regression would surface in
    the TOOL-04 test module specifically — easier diagnosis.
    """

    def test_poll_interval_above_2_seconds_rejected(self) -> None:
        with pytest.raises(ValidationError):
            WaitForJobInput(job_id="x", poll_interval_seconds=5.0)

    def test_poll_interval_below_half_second_rejected(self) -> None:
        with pytest.raises(ValidationError):
            WaitForJobInput(job_id="x", poll_interval_seconds=0.1)

    def test_negative_timeout_rejected(self) -> None:
        with pytest.raises(ValidationError):
            WaitForJobInput(job_id="x", timeout_seconds=0)

    def test_default_poll_interval_is_one_second(self) -> None:
        args = WaitForJobInput(job_id="x")
        assert args.poll_interval_seconds == 1.0


@pytest.mark.asyncio
class TestNotificationShape:
    """Capture a notification call and pin the MCP-spec payload shape."""

    async def test_notify_carries_progress_total_message(self) -> None:
        records = [
            {
                "job_id": "j-shape",
                "status": "running",
                "progress_percent": 33.3,
                "message": "Indexing /tmp/x",
            },
            {
                "job_id": "j-shape",
                "status": "succeeded",
                "progress_percent": 100.0,
                "message": "Done indexing /tmp/x",
            },
        ]
        client = _make_client_yielding(records)
        notifier = _CapturingNotifier()
        args = WaitForJobInput(job_id="j-shape", poll_interval_seconds=0.5)

        await handle_wait_for_job(client, args, notify=notifier)

        # All emissions have float progress in [0, 1], total=1.0, str|None message
        for progress, total, message in notifier.calls:
            assert 0.0 <= progress <= 1.0
            assert total == 1.0
            assert message is None or isinstance(message, str)
        # First notification carries the polled message
        assert notifier.calls[0][2] == "Indexing /tmp/x"
        # Final notification (after terminal) carries the terminal message
        assert notifier.calls[-1][2] == "Done indexing /tmp/x"

    async def test_progress_clamped_to_one_when_server_overshoots(self) -> None:
        """Defensive clamp — a buggy server reporting 150% must not break notify."""
        records = [
            {
                "job_id": "j-clamp",
                "status": "succeeded",
                "progress_percent": 150.0,  # Server bug: > 100%
                "message": "weird",
            },
        ]
        client = _make_client_yielding(records)
        notifier = _CapturingNotifier()
        args = WaitForJobInput(job_id="j-clamp", poll_interval_seconds=0.5)

        await handle_wait_for_job(client, args, notify=notifier)

        # Clamp pinned by the handler
        for progress, _total, _message in notifier.calls:
            assert progress <= 1.0

    async def test_missing_progress_percent_defaults_to_zero(self) -> None:
        """Server omits the field on early polls → handler treats as 0%."""
        records = [
            {
                "job_id": "j-noprog",
                "status": "running",
                # progress_percent absent
                "message": "Just starting",
            },
            {
                "job_id": "j-noprog",
                "status": "succeeded",
                "progress_percent": 100.0,
                "message": "Done",
            },
        ]
        client = _make_client_yielding(records)
        notifier = _CapturingNotifier()
        args = WaitForJobInput(job_id="j-noprog", poll_interval_seconds=0.5)

        output = await handle_wait_for_job(client, args, notify=notifier)

        # First emission used 0.0 (None → 0)
        assert notifier.calls[0][0] == pytest.approx(0.0)
        # Output succeeded
        assert output.status == "succeeded"


@pytest.mark.asyncio
class TestOutputProjection:
    """Pin :func:`_project_job_output` against the field-collision risk."""

    async def test_extra_record_fields_are_ignored(self) -> None:
        """A server record with extra fields (e.g., folder_path) MUST NOT
        break the explicit kwargs (`final`, `elapsed_seconds`) that the
        handler injects.
        """
        records = [
            {
                "job_id": "j-extras",
                "status": "succeeded",
                "progress_percent": 100.0,
                "message": "Done",
                # Extra fields the server might add — must be silently ignored
                "folder_path": "/tmp/x",
                "files_total": 42,
                "extra_unknown": {"a": 1},
                # If these were spread directly, they'd collide
                "final": "this should NOT win",
                "elapsed_seconds": 999.0,
            },
        ]
        client = _make_client_yielding(records)
        notifier = _CapturingNotifier()
        args = WaitForJobInput(job_id="j-extras", poll_interval_seconds=0.5)

        output = await handle_wait_for_job(client, args, notify=notifier)

        # Handler's explicit kwargs win over the record's bogus copies
        assert output.final is True  # Not "this should NOT win"
        assert output.elapsed_seconds < 5.0  # Not 999.0
        # WaitForJobOutput is happy (no validation error)
        assert isinstance(output, WaitForJobOutput)
