"""``wait_for_job`` handler — TOOL-04, Phase 54 Plan 04.

The only Phase 54 tool that consumes Phase 52's progress-notification
infrastructure, and the **first async handler** in the codebase. Polls
``GET /index/jobs/{id}`` once per ``poll_interval_seconds`` (default
1.0s, le=2.0s — under the MCP spec ≤2s notification cadence), emits a
``notifications/progress`` after every poll, and returns the final
``JobRecord`` when the job reaches a terminal status.

Terminal-status set (Phase 54 CONTEXT decision E):

    succeeded, failed, cancelled, dry_run, completed, done

The set is the union of:

1. The plan's enumerated terminals (``succeeded``, ``failed``,
   ``cancelled``, ``dry_run``) — these are the MCP-facing names called
   out in the tool description and acceptance criteria.
2. Phase 52's ``TERMINAL_JOB_STATUSES`` constant — ``completed``,
   ``failed``, ``cancelled``. ``completed`` is what the agent-brain
   server actually emits (see ``JobStatus.DONE`` = ``"done"`` in
   ``agent_brain_server/models/job.py:JobStatus``, plus the job runner
   that emits ``"completed"`` as a status alias). We honor both because
   the server's terminology has drifted across versions; the MCP tool
   handles every name a real server might return.
3. ``done`` — the literal value of ``JobStatus.DONE`` in
   ``agent_brain_server/models/job.py``. Equivalent to ``completed`` /
   ``succeeded`` semantically; included so an MCP caller against a
   server that returns the raw enum value doesn't loop forever.

Cancellation contract (CONTEXT decision E): when the MCP request is
cancelled via ``notifications/cancelled``, the handler receives
:class:`asyncio.CancelledError`. The ``finally`` clause makes a
best-effort ``client.cancel_job(args.job_id)`` call so the server-side
indexing job is also torn down, then re-raises. A failure of
``cancel_job`` is swallowed (logged) — the primary failure (the
cancellation) MUST propagate so the MCP wire cancellation flow stays
intact.

Time math uses :func:`time.monotonic` (NTP-immune) for both the
timeout decision and the ``elapsed_seconds`` returned to the caller.
``time.time()`` would let an NTP step break the timeout silently.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from ..client import ApiClient
from ..schemas import WaitForJobInput, WaitForJobOutput

logger = logging.getLogger(__name__)


# Per CONTEXT decision E plus the server's actual ``JobStatus`` enum
# values (see module docstring). Keep this superset to absorb upstream
# drift; the MCP tool's contract is "return when the job reaches *any*
# terminal status the server might emit."
_TERMINAL_STATES: frozenset[str] = frozenset(
    {
        "succeeded",
        "failed",
        "cancelled",
        "dry_run",
        "completed",
        "done",
    }
)


# Type alias for the progress-notification closure injected by
# :func:`server.call_tool`. Signature matches the MCP spec's
# ``notifications/progress`` payload shape minus the ``progressToken``
# (which the closure captures from request meta and injects into every
# call). ``message`` is ``str | None`` because the server's job record
# may not always carry a progress message.
ProgressNotifier = Callable[[float, float, str | None], Awaitable[None]]
"""Callable that emits one ``notifications/progress`` to the client.

The injected closure is responsible for:

1. Capturing the ``progressToken`` from the MCP request meta (it's
   built per-request, so the token is baked in).
2. Capturing the ``related_request_id`` (the JSON-RPC id of the
   ``tools/call`` that triggered the wait).
3. No-op when the client did NOT attach a progressToken (notifications
   would have no recipient — per MCP spec, progress is opt-in).

Called as ``await notify(progress, total, message)``.
"""


def _project_job_output(
    record: dict[str, Any],
    *,
    job_id: str,
    final: bool,
    elapsed_seconds: float,
    status_override: str | None = None,
) -> WaitForJobOutput:
    """Build a :class:`WaitForJobOutput` from a server job record.

    Defends against the field-collision risk noted in plan §"Risk Notes":
    the server's ``JobRecord`` carries many fields beyond the MCP-facing
    output model; we project ONLY the fields declared on
    :class:`WaitForJobOutput` and inject the explicit ``final`` and
    ``elapsed_seconds`` ourselves. Also defends against the server
    omitting fields (record dict missing keys → MCP output uses the
    field's default, which is ``None`` for every projected field).

    Args:
        record: Raw job record dict from ``GET /index/jobs/{id}`` (may
            be empty if no poll has succeeded yet — caller passes
            ``{}``).
        job_id: Fallback ``job_id`` when the record dict is missing
            one (e.g., on timeout before any successful poll).
        final: Value for the ``final`` output field. ``True`` for
            terminal completion, ``False`` for timeout.
        elapsed_seconds: Wall-clock seconds the wait spent polling.
        status_override: When non-None, the ``status`` field in the
            output is set to this value instead of the record's. Used
            for timeout (forces ``"timeout"``).

    Returns:
        A validated :class:`WaitForJobOutput` ready to return.
    """
    output_fields = WaitForJobOutput.model_fields.keys()
    payload: dict[str, Any] = {k: v for k, v in record.items() if k in output_fields}
    payload["job_id"] = payload.get("job_id") or job_id
    if status_override is not None:
        payload["status"] = status_override
    elif "status" not in payload:
        # Defensive fallback — every well-formed server response sets
        # status; this only fires if the record is empty/malformed.
        payload["status"] = "unknown"
    payload["final"] = final
    payload["elapsed_seconds"] = elapsed_seconds
    return WaitForJobOutput.model_validate(payload)


async def handle_wait_for_job(
    client: ApiClient,
    args: WaitForJobInput,
    *,
    notify: ProgressNotifier,
) -> WaitForJobOutput:
    """Block until ``args.job_id`` reaches a terminal status, emitting progress.

    Polling loop:

    1. Call ``client.get_job(job_id)`` via :func:`asyncio.to_thread`
       (the client method is sync httpx, blocking the event loop is
       not OK).
    2. Convert ``progress_percent`` (0-100 from the server) to the
       MCP spec's [0.0, 1.0] ``progress`` value and emit one
       ``notifications/progress`` per poll.
    3. If ``status in _TERMINAL_STATES`` — emit one final notification
       with ``progress=1.0`` and return ``WaitForJobOutput(...,
       final=True)``.
    4. If ``timeout_seconds`` is set and exceeded — return
       ``WaitForJobOutput(status="timeout", final=False, ...)`` with
       the last-known record. Do NOT raise (CONTEXT decision E).
    5. Otherwise ``await asyncio.sleep(poll_interval_seconds)`` and
       loop.

    Cancellation propagation: see module docstring. The ``finally``
    clause is best-effort and never masks the primary
    :class:`asyncio.CancelledError`.
    """
    start = time.monotonic()
    last_record: dict[str, Any] = {}
    cancelled = False
    try:
        while True:
            record = await asyncio.to_thread(client.get_job, args.job_id)
            last_record = record

            # MCP spec: progress is [0.0, 1.0]; the server returns
            # progress_percent in [0, 100]. Coerce defensively — the
            # field is typed float | None in JobRecord but a missing
            # key would yield None → division error.
            raw_pct = record.get("progress_percent")
            progress = (float(raw_pct) / 100.0) if raw_pct is not None else 0.0
            # Clamp to [0, 1] — server should already guarantee this,
            # but a stale or fuzz-tested response shouldn't break the
            # notification.
            progress = max(0.0, min(1.0, progress))
            message_raw = record.get("message")
            message = str(message_raw) if message_raw is not None else None
            await notify(progress, 1.0, message)

            if record.get("status") in _TERMINAL_STATES:
                # Final notification — always progress=1.0 so the
                # client UI hits 100% even when the server stopped
                # short (e.g., dry_run finishes at whatever percent
                # the validator left it at).
                await notify(1.0, 1.0, message)
                elapsed = time.monotonic() - start
                return _project_job_output(
                    record,
                    job_id=args.job_id,
                    final=True,
                    elapsed_seconds=elapsed,
                )

            if args.timeout_seconds is not None:
                elapsed = time.monotonic() - start
                if elapsed >= args.timeout_seconds:
                    # Soft timeout — return last-known state with
                    # status="timeout" and final=False (CONTEXT
                    # decision E). Do NOT raise; clients use
                    # notifications/cancelled as the hard abort.
                    return _project_job_output(
                        last_record,
                        job_id=args.job_id,
                        final=False,
                        elapsed_seconds=elapsed,
                        status_override="timeout",
                    )

            await asyncio.sleep(args.poll_interval_seconds)
    except asyncio.CancelledError:
        # Client sent notifications/cancelled (or the server is shutting
        # down). Best-effort cancel of the underlying indexing job so
        # we don't leak a runaway worker on the server side. NEVER let
        # the cleanup raise — it would mask the primary cancellation.
        cancelled = True
        raise
    finally:
        if cancelled:
            try:
                await asyncio.to_thread(client.cancel_job, args.job_id)
            except Exception:
                # Cleanup is best-effort. The MCP wire-cancellation
                # already won — losing the server-side cancel just
                # means the indexing job may finish on its own; not a
                # correctness issue, just a wasted background worker.
                logger.exception(
                    "wait_for_job cleanup: best-effort cancel_job(%s) failed",
                    args.job_id,
                )
