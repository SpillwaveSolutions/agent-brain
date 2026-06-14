"""Tests for RFC 9728 PRM + RFC 8414 OASM document builders (Phase 66 Plan 02).

Verifies that :func:`build_prm_document` and :func:`build_oasm_document`
produce RFC-valid, config-derived JSON documents with all required fields
and exact spec-mandated values.

Key invariants:
  - PRM ``scopes_supported`` is exactly the 4 locked agent-brain:* scopes
  - OASM ``code_challenge_methods_supported`` is exactly ``["S256"]``
    (absence or empty list causes compliant MCP SDK clients to abort)
  - All endpoint URIs derive from the ``issuer`` parameter (forward-refs
    to Phase 67 routes — NOT hardcoded)
  - Both builders are pure functions (no env-var side effects)
"""

from __future__ import annotations

from agent_brain_mcp.oauth_metadata import build_oasm_document, build_prm_document

# ---------------------------------------------------------------------------
# PRM document tests (RFC 9728)
# ---------------------------------------------------------------------------


class TestBuildPrmDocument:
    """Verify build_prm_document() shape and field values."""

    def test_has_required_keys(self) -> None:
        """PRM document must have exactly the three RFC 9728 §3.2 required fields."""
        doc = build_prm_document(
            resource="https://mcp.example.com/mcp",
            authorization_servers=["https://mcp.example.com"],
        )
        assert set(doc.keys()) == {
            "resource",
            "authorization_servers",
            "scopes_supported",
        }

    def test_resource_field_matches_input(self) -> None:
        """PRM ``resource`` must equal the passed resource URI verbatim."""
        uri = "https://mcp.example.com/mcp"
        doc = build_prm_document(
            resource=uri,
            authorization_servers=["https://mcp.example.com"],
        )
        assert doc["resource"] == uri

    def test_authorization_servers_matches_input(self) -> None:
        """PRM ``authorization_servers`` must be the passed list verbatim."""
        servers = ["https://auth.example.com"]
        doc = build_prm_document(
            resource="https://mcp.example.com/mcp",
            authorization_servers=servers,
        )
        assert doc["authorization_servers"] == servers

    def test_authorization_servers_is_non_empty_list(self) -> None:
        """PRM ``authorization_servers`` must be a non-empty list (RFC 9728 §3.2)."""
        doc = build_prm_document(
            resource="https://mcp.example.com/mcp",
            authorization_servers=["https://mcp.example.com"],
        )
        assert isinstance(doc["authorization_servers"], list)
        assert len(doc["authorization_servers"]) >= 1

    def test_scopes_supported_exact_four_locked_scopes(self) -> None:
        """PRM ``scopes_supported`` must be exactly the 4 locked agent-brain:* scopes.

        The scope list is locked by the design doc §"Scope-to-Tool Mapping".
        Order is significant — changes require a schema migration.
        """
        doc = build_prm_document(
            resource="https://mcp.example.com/mcp",
            authorization_servers=["https://mcp.example.com"],
        )
        assert doc["scopes_supported"] == [
            "agent-brain:read",
            "agent-brain:index",
            "agent-brain:admin",
            "agent-brain:subscribe",
        ]

    def test_scopes_supported_contains_read(self) -> None:
        """agent-brain:read must be present in scopes_supported."""
        doc = build_prm_document(
            resource="https://mcp.example.com/mcp",
            authorization_servers=["https://mcp.example.com"],
        )
        assert "agent-brain:read" in doc["scopes_supported"]  # type: ignore[operator]

    def test_scopes_supported_contains_index(self) -> None:
        """agent-brain:index must be present in scopes_supported."""
        doc = build_prm_document(
            resource="https://mcp.example.com/mcp",
            authorization_servers=["https://mcp.example.com"],
        )
        assert "agent-brain:index" in doc["scopes_supported"]  # type: ignore[operator]

    def test_scopes_supported_contains_admin(self) -> None:
        """agent-brain:admin must be present in scopes_supported."""
        doc = build_prm_document(
            resource="https://mcp.example.com/mcp",
            authorization_servers=["https://mcp.example.com"],
        )
        assert "agent-brain:admin" in doc["scopes_supported"]  # type: ignore[operator]

    def test_scopes_supported_contains_subscribe(self) -> None:
        """agent-brain:subscribe must be present in scopes_supported."""
        doc = build_prm_document(
            resource="https://mcp.example.com/mcp",
            authorization_servers=["https://mcp.example.com"],
        )
        assert "agent-brain:subscribe" in doc["scopes_supported"]  # type: ignore[operator]

    def test_multiple_authorization_servers(self) -> None:
        """PRM accepts a multi-entry authorization_servers list."""
        servers = ["https://auth1.example.com", "https://auth2.example.com"]
        doc = build_prm_document(
            resource="https://mcp.example.com/mcp",
            authorization_servers=servers,
        )
        assert doc["authorization_servers"] == servers

    def test_scopes_supported_is_a_list(self) -> None:
        """scopes_supported must be a list (JSON array), not a string."""
        doc = build_prm_document(
            resource="https://mcp.example.com/mcp",
            authorization_servers=["https://mcp.example.com"],
        )
        assert isinstance(doc["scopes_supported"], list)

    def test_result_is_json_serializable(self) -> None:
        """PRM document must be JSON-serializable (all values are str/list)."""
        import json

        doc = build_prm_document(
            resource="https://mcp.example.com/mcp",
            authorization_servers=["https://mcp.example.com"],
        )
        # Should not raise
        serialized = json.dumps(doc)
        parsed = json.loads(serialized)
        assert parsed["resource"] == "https://mcp.example.com/mcp"


# ---------------------------------------------------------------------------
# OASM document tests (RFC 8414)
# ---------------------------------------------------------------------------


class TestBuildOasmDocument:
    """Verify build_oasm_document() shape and field values."""

    _ISSUER = "https://mcp.example.com"
    _BASE_URL = "https://mcp.example.com"

    def _build(self) -> dict[str, object]:
        """Build a standard OASM document for reuse in tests."""
        return build_oasm_document(
            issuer=self._ISSUER,
            base_url=self._BASE_URL,
        )

    def test_has_required_rfc8414_fields(self) -> None:
        """OASM must include all required RFC 8414 §2 fields."""
        doc = self._build()
        required = {
            "issuer",
            "authorization_endpoint",
            "token_endpoint",
            "registration_endpoint",
            "jwks_uri",
            "code_challenge_methods_supported",
            "grant_types_supported",
            "response_types_supported",
        }
        assert required.issubset(set(doc.keys()))

    def test_issuer_matches_input(self) -> None:
        """OASM ``issuer`` must equal the passed issuer URI verbatim."""
        doc = self._build()
        assert doc["issuer"] == self._ISSUER

    def test_code_challenge_methods_supported_is_exactly_s256(self) -> None:
        """``code_challenge_methods_supported`` MUST be exactly ``["S256"]``.

        This is the critical field for MCP compliance. Compliant clients abort
        the OAuth dance if this field is absent or does not include "S256"
        (MCP Authorization 2025-11-25 spec; design doc ROADMAP SC#2).
        """
        doc = self._build()
        assert doc["code_challenge_methods_supported"] == ["S256"]

    def test_code_challenge_methods_supported_is_list(self) -> None:
        """code_challenge_methods_supported must be a list (JSON array)."""
        doc = self._build()
        assert isinstance(doc["code_challenge_methods_supported"], list)

    def test_code_challenge_methods_supported_not_empty(self) -> None:
        """code_challenge_methods_supported must be non-empty."""
        doc = self._build()
        assert len(doc["code_challenge_methods_supported"]) >= 1  # type: ignore[arg-type]

    def test_grant_types_supported(self) -> None:
        """OASM must advertise authorization_code and refresh_token grant types."""
        doc = self._build()
        assert doc["grant_types_supported"] == ["authorization_code", "refresh_token"]

    def test_response_types_supported(self) -> None:
        """OASM must advertise ``code`` response type (authorization code flow)."""
        doc = self._build()
        assert doc["response_types_supported"] == ["code"]

    def test_authorization_endpoint_derived_from_issuer(self) -> None:
        """authorization_endpoint must be a forward-ref derived from issuer."""
        doc = self._build()
        assert str(doc["authorization_endpoint"]).endswith("/authorize")
        assert str(doc["authorization_endpoint"]).startswith(self._ISSUER)

    def test_token_endpoint_derived_from_issuer(self) -> None:
        """token_endpoint must be a forward-ref derived from issuer."""
        doc = self._build()
        assert str(doc["token_endpoint"]).endswith("/token")
        assert str(doc["token_endpoint"]).startswith(self._ISSUER)

    def test_registration_endpoint_derived_from_issuer(self) -> None:
        """registration_endpoint must be a forward-ref derived from issuer."""
        doc = self._build()
        assert str(doc["registration_endpoint"]).endswith("/register")
        assert str(doc["registration_endpoint"]).startswith(self._ISSUER)

    def test_jwks_uri_derived_from_issuer(self) -> None:
        """jwks_uri must be a forward-ref derived from issuer."""
        doc = self._build()
        assert "jwks" in str(doc["jwks_uri"]).lower()
        assert str(doc["jwks_uri"]).startswith(self._ISSUER)

    def test_endpoints_use_different_issuer(self) -> None:
        """When a different issuer is passed, all endpoint URIs use it."""
        other_issuer = "https://auth.other.example.com"
        doc = build_oasm_document(
            issuer=other_issuer,
            base_url="https://mcp.example.com",
        )
        assert doc["issuer"] == other_issuer
        assert str(doc["authorization_endpoint"]).startswith(other_issuer)
        assert str(doc["token_endpoint"]).startswith(other_issuer)
        assert str(doc["registration_endpoint"]).startswith(other_issuer)
        assert str(doc["jwks_uri"]).startswith(other_issuer)

    def test_result_is_json_serializable(self) -> None:
        """OASM document must be JSON-serializable."""
        import json

        doc = self._build()
        serialized = json.dumps(doc)
        parsed = json.loads(serialized)
        assert parsed["code_challenge_methods_supported"] == ["S256"]
        assert parsed["issuer"] == self._ISSUER
