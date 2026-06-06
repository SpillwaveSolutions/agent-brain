"""Tests that BackendClient (Phase 56 Plan 02) is structurally satisfied
by the existing DocServeClient.

This is the contract Plan 56-03's McpStdioBackend + McpHttpBackend
must also satisfy. Pinning it in a test BEFORE the v3 backends land
guarantees future drift is caught by CI, not by a downstream Phase 57
integration failure.
"""

from __future__ import annotations

from agent_brain_cli.client import BackendClient, DocServeClient

EXPECTED_PROTOCOL_METHODS: frozenset[str] = frozenset(
    {
        "__enter__",
        "__exit__",
        "close",
        "health",
        "status",
        "query",
        "index",
        "list_folders",
        "delete_folder",
        "reset",
        "list_jobs",
        "get_job",
        "cancel_job",
        "cache_status",
        "clear_cache",
    }
)


def test_doc_serve_client_satisfies_backend_client_protocol() -> None:
    """DocServeClient must satisfy BackendClient via structural typing."""
    client = DocServeClient(base_url="http://127.0.0.1:8000")
    assert isinstance(client, BackendClient), (
        "DocServeClient must structurally satisfy BackendClient — "
        "if this breaks, a method signature drifted. Diff DocServeClient "
        "against BackendClient in agent_brain_cli/client/protocol.py."
    )


def test_backend_client_protocol_declares_expected_methods() -> None:
    """BackendClient must declare exactly the 15 expected methods.

    Surface drift here is a contract break for v3 backends (Plan 56-03)
    AND for Phase 57's transport selector. Adding a method without
    updating this test is intentional friction.
    """
    # Protocol attribute introspection: prefer __protocol_attrs__ (3.12+)
    # else fall back to scanning class dict for non-dunder callables.
    if hasattr(BackendClient, "__protocol_attrs__"):
        declared = frozenset(BackendClient.__protocol_attrs__)
    else:
        declared = frozenset(
            name
            for name, value in vars(BackendClient).items()
            if callable(value) or name in {"__enter__", "__exit__"}
        )
    missing = EXPECTED_PROTOCOL_METHODS - declared
    extra = declared - EXPECTED_PROTOCOL_METHODS - {"__init_subclass__"}
    assert not missing, f"BackendClient missing required methods: {missing}"
    assert not extra, (
        f"BackendClient declares unexpected methods: {extra} — "
        "if intentional, update EXPECTED_PROTOCOL_METHODS in this test "
        "AND the v3 design doc §2.2."
    )


def test_stub_missing_query_fails_isinstance() -> None:
    """A stub missing the .query method must fail BackendClient isinstance.

    Validates @runtime_checkable actually enforces the surface. If this
    starts passing on the stub, runtime_checkable was dropped from the
    Protocol decorator.
    """

    class StubMissingQuery:
        def __enter__(self) -> StubMissingQuery:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def close(self) -> None:
            return None

        # Deliberately missing: query(), and many others. isinstance
        # only checks the union — so we omit at least one (query) to
        # prove the negative case.

    stub = StubMissingQuery()
    assert not isinstance(stub, BackendClient), (
        "Stub missing .query should NOT satisfy BackendClient — "
        "runtime_checkable enforcement broken."
    )
