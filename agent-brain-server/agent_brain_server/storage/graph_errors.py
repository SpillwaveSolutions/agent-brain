"""Structured error types for graph index operations (Phase 64 / GSTAB-01).

Provides GraphBuildFailedError, raised when the isolated graph-build
subprocess exits with a non-zero code (including SIGSEGV, which exits
as code 139 = 128 + signal 11). This keeps the server process alive and
surfaces a clear operator message naming the failure and the simple-store
fallback.

The existing KuzuUnavailableError in graph_store.py (line 36) remains the
second line of defense for non-fatal pybind11 corruption (IndexError /
RuntimeError) caught inside the child process. This module handles the
outer layer: native crashes that kill the child entirely.
"""


class GraphBuildFailedError(RuntimeError):
    """Raised when the isolated graph-build worker fails (native crash or
    non-zero child exit). Carries a clear operator message naming the kuzu
    failure and the simple-store fallback. The server stays up; the job
    degrades to "no graph this run".

    Attributes:
        exit_code: The child process exit code, or None if the failure was
            not a subprocess exit (e.g. timeout before process started).
    """

    def __init__(self, message: str, *, exit_code: int | None = None) -> None:
        """Initialize GraphBuildFailedError.

        Args:
            message: Operator-facing message describing the failure.
            exit_code: Child process exit code (e.g. 139 for SIGSEGV).
        """
        super().__init__(message)
        self.exit_code = exit_code
