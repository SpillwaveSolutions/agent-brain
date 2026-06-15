"""Tests for RS256 keypair generation and JWKS serialization (Phase 67 Plan 02 Task 1).

Tests verify:
  - RS256 keypair generation produces a 2048-bit RSA private key
  - build_jwks returns a public-only JWKS document (no private key material)
  - Round-trip: token signed with private key verifies against PyJWK built from JWKS
  - get_or_create_signing_key returns a stable SigningKey for the process lifetime
  - resolve_client_id_allowlist parses AGENT_BRAIN_OAUTH_CLIENT_ID_ALLOWLIST
  - resolve_signing_key_path returns AGENT_BRAIN_OAUTH_SIGNING_KEY or None

Design doc: docs/plans/2026-06-14-mcp-v4-oauth-design.md
  §"Deployment Shape A: Co-Located AS + RS" (in-memory RS256 signing key)
  §"SDK Gap: No Built-In JWKS Endpoint"
"""

from __future__ import annotations

import json

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey

from agent_brain_mcp.oauth.keys import (
    SigningKey,
    build_jwks,
    compute_kid,
    generate_rs256_keypair,
    get_or_create_signing_key,
)


class TestGenerateRs256Keypair:
    """Tests for generate_rs256_keypair()."""

    def test_returns_rsa_private_key(self) -> None:
        """generate_rs256_keypair() returns an RSAPrivateKey instance."""
        private_key = generate_rs256_keypair()
        assert isinstance(private_key, RSAPrivateKey)

    def test_key_size_is_2048_bits(self) -> None:
        """The generated key is 2048 bits."""
        private_key = generate_rs256_keypair()
        assert private_key.key_size == 2048

    def test_public_exponent_is_65537(self) -> None:
        """The public exponent is 65537 (F4)."""
        private_key = generate_rs256_keypair()
        pub = private_key.public_key()
        assert isinstance(pub, RSAPublicKey)
        assert pub.public_numbers().e == 65537

    def test_two_calls_yield_distinct_keys(self) -> None:
        """Each call produces a different keypair (no reuse)."""
        k1 = generate_rs256_keypair()
        k2 = generate_rs256_keypair()
        # Different keys have different public exponent values' e is same (65537)
        # but moduli will differ
        n1 = k1.public_key().public_numbers().n
        n2 = k2.public_key().public_numbers().n
        assert n1 != n2


class TestBuildJwks:
    """Tests for build_jwks()."""

    def setup_method(self) -> None:
        """Create a fresh keypair for each test."""
        self.private_key = generate_rs256_keypair()
        self.public_key = self.private_key.public_key()
        self.kid = compute_kid(self.public_key)

    def test_returns_dict_with_keys_list(self) -> None:
        """build_jwks returns a dict with a 'keys' list."""
        doc = build_jwks(self.public_key, self.kid)
        assert isinstance(doc, dict)
        assert "keys" in doc
        assert isinstance(doc["keys"], list)
        assert len(doc["keys"]) == 1

    def test_jwk_entry_has_required_fields(self) -> None:
        """Each JWK entry has kty, use, alg, kid, n, e."""
        doc = build_jwks(self.public_key, self.kid)
        entry = doc["keys"][0]
        for field in ("kty", "use", "alg", "kid", "n", "e"):
            assert field in entry, f"Missing field: {field}"

    def test_kty_is_rsa(self) -> None:
        """kty is 'RSA'."""
        doc = build_jwks(self.public_key, self.kid)
        assert doc["keys"][0]["kty"] == "RSA"

    def test_use_is_sig(self) -> None:
        """use is 'sig'."""
        doc = build_jwks(self.public_key, self.kid)
        assert doc["keys"][0]["use"] == "sig"

    def test_alg_is_rs256(self) -> None:
        """alg is 'RS256'."""
        doc = build_jwks(self.public_key, self.kid)
        assert doc["keys"][0]["alg"] == "RS256"

    def test_kid_matches_supplied_kid(self) -> None:
        """kid in JWKS matches the supplied kid."""
        doc = build_jwks(self.public_key, self.kid)
        assert doc["keys"][0]["kid"] == self.kid

    def test_no_private_key_material(self) -> None:
        """JWKS must NOT include private key fields (d, p, q, dp, dq, qi)."""
        doc = build_jwks(self.public_key, self.kid)
        entry = doc["keys"][0]
        for private_field in ("d", "p", "q", "dp", "dq", "qi"):
            assert private_field not in entry, f"Private field exposed: {private_field}"

    def test_n_and_e_are_base64url_strings(self) -> None:
        """n and e are non-empty strings (base64url encoded)."""
        doc = build_jwks(self.public_key, self.kid)
        entry = doc["keys"][0]
        assert isinstance(entry["n"], str) and len(entry["n"]) > 0
        assert isinstance(entry["e"], str) and len(entry["e"]) > 0

    def test_round_trip_verify(self) -> None:
        """Token signed with private key verifies against PyJWK built from JWKS."""
        doc = build_jwks(self.public_key, self.kid)
        jwk_entry = doc["keys"][0]

        # Sign a token with the private key
        payload = {"sub": "test-client", "iss": "https://example.com"}
        token = jwt.encode(
            payload,
            self.private_key,
            algorithm="RS256",
            headers={"kid": self.kid},
        )

        # Rebuild the public key from the JWKS entry via RSAAlgorithm
        from jwt.algorithms import RSAAlgorithm

        jwk_json = json.dumps(jwk_entry)
        pub_key_from_jwks = RSAAlgorithm.from_jwk(jwk_json)

        # Verify the token
        decoded = jwt.decode(
            token,
            pub_key_from_jwks,
            algorithms=["RS256"],
            options={"verify_exp": False},
        )
        assert decoded["sub"] == "test-client"
        assert decoded["iss"] == "https://example.com"

    def test_jwks_is_json_serializable(self) -> None:
        """The JWKS document is JSON-serializable."""
        doc = build_jwks(self.public_key, self.kid)
        serialized = json.dumps(doc)
        parsed = json.loads(serialized)
        assert parsed["keys"][0]["kty"] == "RSA"


class TestGetOrCreateSigningKey:
    """Tests for get_or_create_signing_key() stability and caching."""

    def test_returns_signing_key_instance(self) -> None:
        """get_or_create_signing_key() returns a SigningKey."""
        sk = get_or_create_signing_key()
        assert isinstance(sk, SigningKey)

    def test_has_required_attributes(self) -> None:
        """SigningKey has private_key, public_key, kid, and jwks_dict."""
        sk = get_or_create_signing_key()
        assert isinstance(sk.private_key, RSAPrivateKey)
        assert isinstance(sk.public_key, RSAPublicKey)
        assert isinstance(sk.kid, str) and len(sk.kid) > 0
        assert isinstance(sk.jwks_dict, dict) and "keys" in sk.jwks_dict

    def test_stable_within_process(self) -> None:
        """Successive calls return the same SigningKey (same kid)."""
        sk1 = get_or_create_signing_key()
        sk2 = get_or_create_signing_key()
        assert sk1.kid == sk2.kid
        # Same private key object (cached)
        n1 = sk1.private_key.public_key().public_numbers().n
        n2 = sk2.private_key.public_key().public_numbers().n
        assert n1 == n2

    def test_jwks_dict_has_no_private_material(self) -> None:
        """The cached jwks_dict has no private key fields."""
        sk = get_or_create_signing_key()
        entry = sk.jwks_dict["keys"][0]
        for private_field in ("d", "p", "q", "dp", "dq", "qi"):
            assert (
                private_field not in entry
            ), f"Private field in jwks_dict: {private_field}"


class TestResolveClientIdAllowlist:
    """Tests for resolve_client_id_allowlist() in config.py."""

    def test_unset_returns_empty_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Unset AGENT_BRAIN_OAUTH_CLIENT_ID_ALLOWLIST -> empty list."""
        monkeypatch.delenv("AGENT_BRAIN_OAUTH_CLIENT_ID_ALLOWLIST", raising=False)
        from agent_brain_mcp.config import resolve_client_id_allowlist

        result = resolve_client_id_allowlist()
        assert result == []

    def test_single_domain(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A single domain returns a one-element list."""
        monkeypatch.setenv("AGENT_BRAIN_OAUTH_CLIENT_ID_ALLOWLIST", "example.com")
        from agent_brain_mcp.config import resolve_client_id_allowlist

        result = resolve_client_id_allowlist()
        assert result == ["example.com"]

    def test_comma_separated_domains(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Comma-separated domains are split and stripped."""
        monkeypatch.setenv(
            "AGENT_BRAIN_OAUTH_CLIENT_ID_ALLOWLIST",
            "example.com, another.org , third.io",
        )
        from agent_brain_mcp.config import resolve_client_id_allowlist

        result = resolve_client_id_allowlist()
        assert result == ["example.com", "another.org", "third.io"]

    def test_empty_entries_dropped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Empty entries (double-commas, trailing commas) are dropped."""
        monkeypatch.setenv(
            "AGENT_BRAIN_OAUTH_CLIENT_ID_ALLOWLIST", "example.com,,  ,another.org,"
        )
        from agent_brain_mcp.config import resolve_client_id_allowlist

        result = resolve_client_id_allowlist()
        assert result == ["example.com", "another.org"]

    def test_empty_string_returns_empty_list(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Empty string env var -> empty list."""
        monkeypatch.setenv("AGENT_BRAIN_OAUTH_CLIENT_ID_ALLOWLIST", "")
        from agent_brain_mcp.config import resolve_client_id_allowlist

        result = resolve_client_id_allowlist()
        assert result == []


class TestResolveSigningKeyPath:
    """Tests for resolve_signing_key_path() in config.py."""

    def test_unset_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Unset AGENT_BRAIN_OAUTH_SIGNING_KEY -> None."""
        monkeypatch.delenv("AGENT_BRAIN_OAUTH_SIGNING_KEY", raising=False)
        from agent_brain_mcp.config import resolve_signing_key_path

        result = resolve_signing_key_path()
        assert result is None

    def test_empty_string_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Empty AGENT_BRAIN_OAUTH_SIGNING_KEY -> None."""
        monkeypatch.setenv("AGENT_BRAIN_OAUTH_SIGNING_KEY", "")
        from agent_brain_mcp.config import resolve_signing_key_path

        result = resolve_signing_key_path()
        assert result is None

    def test_valid_path_returned(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A non-empty value is returned as-is."""
        monkeypatch.setenv("AGENT_BRAIN_OAUTH_SIGNING_KEY", "/etc/mcp/signing.pem")
        from agent_brain_mcp.config import resolve_signing_key_path

        result = resolve_signing_key_path()
        assert result == "/etc/mcp/signing.pem"
