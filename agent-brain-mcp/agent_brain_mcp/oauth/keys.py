"""RS256 keypair generation and JWKS document serialization (Phase 67 Plan 02 Task 1).

Provides boot-time in-memory RS256 keypair generation for the co-located
Authorization Server. The public key is serialized as a JWKS document that
Plan 04 serves at GET /.well-known/jwks.json (auth-exempt route).

Key lifecycle
-------------
The signing key is generated once at process startup and held in memory.
All issued JWTs are signed with this key; the JWKS document stays stable for
the lifetime of the process. A process restart generates a new keypair —
this is an accepted trade-off matching the in-memory token store (sessions
already die on restart, so an ephemeral signing key adds no additional loss).

Optional PEM path
-----------------
If AGENT_BRAIN_OAUTH_SIGNING_KEY is set to a readable PEM file path,
``get_or_create_signing_key()`` loads that key instead of generating one.
This allows a stable JWKS across restarts (useful for multi-instance
deployments where all instances share the same signing key). The option is
low-cost and keeps Phase 70 split-AS/RS topology upgradeable without
regenerating JWKS trust anchors.

JWKS security
-------------
``build_jwks()`` produces a PUBLIC-ONLY document. Private key material
(d, p, q, dp, dq, qi) is NEVER included. The JWKS is the verifier's trust
anchor — exposing private material would let any holder forge tokens.

Design doc: docs/plans/2026-06-14-mcp-v4-oauth-design.md
  §"Deployment Shape A: Co-Located AS + RS" (in-memory RS256 signing key)
  §"SDK Gap: No Built-In JWKS Endpoint"
  §"Signing-key lifecycle" in 67-CONTEXT.md
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.rsa import (
    RSAPrivateKey,
    RSAPublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
    load_pem_private_key,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Keypair generation
# ---------------------------------------------------------------------------


def generate_rs256_keypair() -> RSAPrivateKey:
    """Generate a new 2048-bit RS256 RSA private key.

    Uses the ``cryptography`` library directly — consistent with the Phase 67
    dependency stack (``PyJWT[crypto]`` brings ``cryptography`` as a dep).

    Returns:
        A fresh RSA private key (2048-bit, public exponent 65537).
    """
    from cryptography.hazmat.primitives.asymmetric import rsa

    return rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )


# ---------------------------------------------------------------------------
# KID computation
# ---------------------------------------------------------------------------


def compute_kid(public_key: RSAPublicKey) -> str:
    """Compute a stable Key ID (KID) from the RSA public key.

    The KID is a base64url-encoded SHA-256 hash of the DER-encoded
    SubjectPublicKeyInfo structure. This is stable for a given key and
    unique across distinct keys.

    Args:
        public_key: The RSA public key to fingerprint.

    Returns:
        A base64url-encoded string (no padding) suitable for use as the
        ``kid`` claim in JWKs and JWT headers.
    """
    der = public_key.public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
    digest = hashlib.sha256(der).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


# ---------------------------------------------------------------------------
# JWKS document builder
# ---------------------------------------------------------------------------


def _int_to_base64url(n: int) -> str:
    """Convert an integer to a base64url-encoded string (no padding).

    Used to encode RSA modulus (n) and exponent (e) in JWK format.

    Args:
        n: The integer to encode.

    Returns:
        A base64url string with no ``=`` padding, as required by RFC 7517.
    """
    # Minimum byte length needed (ceil of bit_length / 8)
    byte_len = (n.bit_length() + 7) // 8
    raw = n.to_bytes(byte_len, byteorder="big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def build_jwks(public_key: RSAPublicKey, kid: str) -> dict[str, object]:
    """Serialize an RSA public key as a public-only JWKS document.

    The returned document is suitable for serving at
    ``GET /.well-known/jwks.json`` (Plan 04 adds this route). It contains
    exactly one JWK entry with the public key parameters.

    SECURITY: Private key material (d, p, q, dp, dq, qi) is NEVER included.
    The output is a JSON-serializable dict (all leaf values are str or list).

    Args:
        public_key: The RSA public key to serialize.
        kid: The Key ID to embed in the JWK entry. Must match the ``kid``
            header on JWTs signed with the corresponding private key.

    Returns:
        A dict with a single ``keys`` list containing one JWK entry:
        ``{"keys": [{"kty": "RSA", "use": "sig", "alg": "RS256",
                     "kid": <kid>, "n": <base64url>, "e": <base64url>}]}``.
    """
    pub_numbers = public_key.public_numbers()
    n_b64 = _int_to_base64url(pub_numbers.n)
    e_b64 = _int_to_base64url(pub_numbers.e)

    return {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "kid": kid,
                "n": n_b64,
                "e": e_b64,
            }
        ]
    }


# ---------------------------------------------------------------------------
# SigningKey holder + singleton cache
# ---------------------------------------------------------------------------


@dataclass
class SigningKey:
    """Bundle holding the RS256 keypair and derived JWKS document.

    Created once at boot by ``get_or_create_signing_key()``. All JWT minting
    and JWKS-serving code MUST use this bundle — do not construct ad-hoc
    keypairs elsewhere.

    Attributes:
        private_key: The RSA private key used to sign JWTs.
        public_key: The corresponding RSA public key.
        kid: The stable Key ID (base64url SHA-256 of DER public key).
        jwks_dict: The public-only JWKS document (JSON-serializable dict).
            Serve this at GET /.well-known/jwks.json (Plan 04).
    """

    private_key: RSAPrivateKey
    public_key: RSAPublicKey
    kid: str
    jwks_dict: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Populate jwks_dict if not supplied by the constructor."""
        if not self.jwks_dict:
            self.jwks_dict = build_jwks(self.public_key, self.kid)


# Module-level singleton — populated once, stable for the process lifetime.
_signing_key_singleton: SigningKey | None = None


def get_or_create_signing_key(
    pem_path: str | None = None,
) -> SigningKey:
    """Return the process-lifetime SigningKey, creating it on first call.

    On the first call this function either:

    1. Loads the PEM private key from ``pem_path`` (or
       ``AGENT_BRAIN_OAUTH_SIGNING_KEY`` env var) if the path is set
       and the file is readable.
    2. Otherwise generates a fresh ephemeral 2048-bit RSA keypair.

    Subsequent calls return the cached singleton regardless of ``pem_path``.
    The JWKS document derived from the public key is therefore stable for
    the lifetime of the process.

    Args:
        pem_path: Optional override for the PEM file path. If None (the
            default), the function reads ``AGENT_BRAIN_OAUTH_SIGNING_KEY``
            from the environment. The env-var path is typically supplied by
            ``resolve_signing_key_path()`` in ``config.py``.

    Returns:
        The cached ``SigningKey`` for this process.
    """
    global _signing_key_singleton  # noqa: PLW0603

    if _signing_key_singleton is not None:
        return _signing_key_singleton

    private_key: RSAPrivateKey

    # Resolve PEM path: explicit arg > env var
    import os

    resolved_path = pem_path or os.environ.get("AGENT_BRAIN_OAUTH_SIGNING_KEY") or None
    if resolved_path:
        resolved_path = resolved_path.strip() or None

    if resolved_path:
        pem_file = Path(resolved_path)
        if pem_file.is_file():
            try:
                raw_pem = pem_file.read_bytes()
                loaded_key = load_pem_private_key(raw_pem, password=None)
                if not isinstance(loaded_key, RSAPrivateKey):
                    raise TypeError(
                        f"PEM key at {resolved_path!r} is not an RSA private key; "
                        "generating an ephemeral key instead."
                    )
                private_key = loaded_key
                logger.info(
                    "Loaded RS256 signing key from %s (KID: stable across restarts)",
                    resolved_path,
                )
            except Exception as exc:
                logger.warning(
                    "Could not load PEM signing key from %r: %s — "
                    "generating an ephemeral keypair instead.",
                    resolved_path,
                    exc,
                )
                private_key = generate_rs256_keypair()
        else:
            logger.warning(
                "AGENT_BRAIN_OAUTH_SIGNING_KEY is set to %r but the file does "
                "not exist — generating an ephemeral keypair instead.",
                resolved_path,
            )
            private_key = generate_rs256_keypair()
    else:
        private_key = generate_rs256_keypair()
        logger.debug(
            "Generated ephemeral RS256 signing key (in-memory; restarts invalidate tokens)."
        )

    public_key = private_key.public_key()
    kid = compute_kid(public_key)
    jwks_dict = build_jwks(public_key, kid)
    _signing_key_singleton = SigningKey(
        private_key=private_key,
        public_key=public_key,
        kid=kid,
        jwks_dict=jwks_dict,
    )
    return _signing_key_singleton
