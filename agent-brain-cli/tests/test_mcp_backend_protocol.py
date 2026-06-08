"""Tests pinning the new ``McpBackend`` Protocol (Phase 59 Plan 01).

Sibling to ``test_backend_client_protocol.py`` — that file pins the
``BackendClient`` Protocol (tools surface) introduced in Plan 56-02; this
file pins the ``McpBackend`` Protocol (prompts + resources surface)
introduced in Plan 59-01. The two Protocols are intentionally separate
per the Phase 59 CONTEXT decisions: ``DocServeClient`` (HTTP/UDS) does
NOT and structurally cannot speak MCP prompts/resources, so it must NOT
satisfy ``McpBackend`` at runtime.

The full architectural-boundary pinning test (including the negative
``DocServeClient ⊄ McpBackend`` case) lives in
``agent-brain-mcp/tests/test_mcp_backend_protocol_skeleton.py`` where
both Protocols and both MCP backend classes are reachable in one file.
This file keeps the Protocol-shape introspection close to the
``BackendClient`` precedent so future drift is loud.
"""

from __future__ import annotations

from agent_brain_cli.client.protocol import BackendClient, McpBackend

EXPECTED_MCP_PROTOCOL_METHODS: frozenset[str] = frozenset(
    {
        "get_prompt",
        "list_prompts",
        "list_resources",
        "list_resource_templates",
        "read_resource",
    }
)


def test_mcp_backend_protocol_declares_expected_methods() -> None:
    """McpBackend must declare exactly the 5 MCP-only methods.

    Surface drift here breaks the Phase 59 Plan 02 wire bodies AND the
    Phase 59 Plan 03 ``resources`` sub-group. Adding or removing a
    method is intentional friction.
    """
    if hasattr(McpBackend, "__protocol_attrs__"):
        declared = frozenset(McpBackend.__protocol_attrs__)
    else:
        declared = frozenset(
            name for name, value in vars(McpBackend).items() if callable(value)
        )
    missing = EXPECTED_MCP_PROTOCOL_METHODS - declared
    extra = declared - EXPECTED_MCP_PROTOCOL_METHODS - {"__init_subclass__"}
    assert not missing, f"McpBackend missing required methods: {missing}"
    assert not extra, (
        f"McpBackend declares unexpected methods: {extra} — "
        "if intentional, update EXPECTED_MCP_PROTOCOL_METHODS in this "
        "test AND the Phase 59 CONTEXT decisions."
    )


def test_mcp_backend_is_distinct_from_backend_client() -> None:
    """The two Protocols are intentionally separate classes.

    Verifies the architectural decision that ``McpBackend`` is NOT a
    subclass of ``BackendClient`` and that the two are independent
    identities. Plan 59-02 commands import ``McpBackend`` deliberately
    rather than ``BackendClient``; if they ever became the same class
    the type-system enforcement of the separation would dissolve.
    """
    assert McpBackend is not BackendClient
    # Protocol "inheritance" is structural at runtime, so we check class
    # identity and the absence of the BackendClient-only methods.
    if hasattr(McpBackend, "__protocol_attrs__"):
        mcp_attrs = frozenset(McpBackend.__protocol_attrs__)
        backend_only = {
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
            "health",
            "status",
        }
        # McpBackend must not advertise the tools-surface methods.
        overlap = mcp_attrs & backend_only
        assert not overlap, (
            f"McpBackend leaked tools-surface methods: {overlap} — "
            "the two Protocols must remain orthogonal."
        )


def test_mcp_backend_is_runtime_checkable() -> None:
    """``@runtime_checkable`` must be applied so ``isinstance`` works.

    Plan 59-01 pins the architectural boundary with
    ``isinstance(DocServeClient(...), McpBackend) == False`` — this
    only works if ``McpBackend`` is decorated. The CPython attribute
    used to record the decoration is ``_is_runtime_protocol``.
    """
    assert getattr(McpBackend, "_is_runtime_protocol", False), (
        "McpBackend must be decorated with @runtime_checkable; "
        "without it the isinstance pinning tests are no-ops."
    )


def test_stub_missing_get_prompt_fails_isinstance() -> None:
    """A stub missing ``.get_prompt`` must NOT satisfy McpBackend.

    Validates ``@runtime_checkable`` actually enforces the surface,
    mirroring the BackendClient precedent
    (``test_stub_missing_query_fails_isinstance``).
    """

    class StubMissingGetPrompt:
        def list_prompts(self) -> list[dict[str, object]]:
            return []

        def list_resources(self) -> list[dict[str, object]]:
            return []

        def list_resource_templates(self) -> list[dict[str, object]]:
            return []

        def read_resource(self, uri: str) -> dict[str, object]:
            return {}

        # Deliberately missing: get_prompt — at least one omission is
        # required to prove the negative case under runtime_checkable.

    stub = StubMissingGetPrompt()
    assert not isinstance(stub, McpBackend), (
        "Stub missing .get_prompt should NOT satisfy McpBackend — "
        "runtime_checkable enforcement broken."
    )
