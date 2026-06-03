"""SUB-04 acceptance: ``notifications/resources/updated`` payload shape conforms.

This is the unit-level test that proves Phase 52's notification payload
parses cleanly against the MCP SDK's ``ResourceUpdatedNotification`` /
``ResourceUpdatedNotificationParams`` Pydantic models from
``mcp.types`` — i.e., the spec-conformant shape mandated by SUB-04 +
Phase 52 CONTEXT decision C.

Decision C lock-ins re-verified here:

* Minimal MCP-spec-compliant payload: ``{"uri": "<resource_uri>"}``.
* Optional ``_meta.revision`` carries a SHA-256 hex digest (64-char hex)
  of the canonical payload — lets clients short-circuit ``resources/read``
  when they already have a cached revision. ``_meta`` is the spec's
  forward-compat envelope for server-defined fields.
* Spec target: 2025-03-26 MCP revision (matches Phase 50 design doc
  citation; SDK pin ``mcp = "^1.12.0"`` in ``agent-brain-mcp/pyproject.toml``).

The e2e SDK tests in ``tests/e2e/test_e2e_subscriptions.py`` exercise
the FULL wire round-trip; this file is the schema-level pin that
catches drift in the SDK's notification model independently of the
end-to-end harness.

Note on revision computation: Plan 02's on-change closure currently
calls ``ServerSession.send_resource_updated(uri)`` which builds the
notification with **just** the URI — no ``_meta.revision`` field is
populated by Phase 52's wire handler today. CONTEXT decision C
documents revision as OPTIONAL (the spec wording "when known"); the
test pins both shapes — minimal (URI-only) and revision-bearing — so
any future enhancement that adds revision metadata stays
spec-conformant.
"""

from __future__ import annotations

import hashlib
import json

import pytest
from mcp.types import (
    ResourceUpdatedNotification,
    ResourceUpdatedNotificationParams,
)
from pydantic import AnyUrl

from agent_brain_mcp.subscriptions import DEFAULT_DROP_KEYS, canonical_hash


def _hex_sha256(payload: dict[str, object]) -> str:
    """Mirror the canonical-hash path Plan 01 ships for cross-check."""
    return canonical_hash(payload, DEFAULT_DROP_KEYS)


class TestMinimalShape:
    """URI-only shape (Phase 52 default) parses + round-trips."""

    def test_minimal_payload_parses_against_sdk_model(self) -> None:
        """The minimum legal ``ResourceUpdatedNotificationParams`` is
        a single ``uri`` field. Plan 02's on-change closure produces
        this shape via ``ServerSession.send_resource_updated(uri)``.
        """
        params = ResourceUpdatedNotificationParams(uri=AnyUrl("corpus://status"))
        assert str(params.uri) == "corpus://status"

    def test_minimal_notification_wraps_params(self) -> None:
        """Full ``ResourceUpdatedNotification`` envelope parses with
        method ``notifications/resources/updated`` and the params
        defined above. Wire shape must NOT drift."""
        notif = ResourceUpdatedNotification(
            params=ResourceUpdatedNotificationParams(uri=AnyUrl("job://abc"))
        )
        assert notif.method == "notifications/resources/updated"
        assert str(notif.params.uri) == "job://abc"

    def test_round_trip_json_minimal(self) -> None:
        """Serialize → parse → assert equality of the URI. This is
        what the MCP SDK does on the wire when ``send_resource_updated``
        runs end-to-end."""
        original = ResourceUpdatedNotification(
            params=ResourceUpdatedNotificationParams(uri=AnyUrl("corpus://folders"))
        )
        raw = original.model_dump_json()
        parsed = ResourceUpdatedNotification.model_validate_json(raw)
        assert parsed.method == original.method
        assert str(parsed.params.uri) == str(original.params.uri)


class TestRevisionEnvelope:
    """Revision-bearing shape (CONTEXT decision C optional enhancement)
    also parses + round-trips. Pins the future-compat contract for
    any code path that DOES populate ``_meta.revision``."""

    def test_revision_is_64_char_hex_sha256(self) -> None:
        """``canonical_hash`` returns a SHA-256 hex digest. The
        spec-compliant revision string is therefore 64 hex chars.
        Pinned so any future revision-shape change (e.g., a switch
        to BLAKE2 or truncated hash) trips this test and the SUB-04
        contract gets re-reviewed."""
        payload = {
            "status": "indexing",
            "total_chunks": 42,
            # Volatile key — gets stripped by DEFAULT_DROP_KEYS.
            "timestamp": "2026-06-03T15:00:00Z",
        }
        revision = _hex_sha256(payload)
        assert len(revision) == 64
        # All characters are lowercase hex.
        assert all(c in "0123456789abcdef" for c in revision)

    def test_canonical_hash_matches_stripped_payload_sha256(self) -> None:
        """Independent verification: the canonical hash equals
        sha256(json.dumps(stripped_payload, sort_keys=True,
        separators=(',', ':'))). Pins the digest computation against
        accidental drift in :func:`canonical_hash`."""
        payload = {"a": 1, "b": [2, 3], "timestamp": "drop-me"}
        expected = hashlib.sha256(
            json.dumps(
                {"a": 1, "b": [2, 3]}, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()
        assert _hex_sha256(payload) == expected

    def test_params_accepts_meta_revision(self) -> None:
        """``ResourceUpdatedNotificationParams`` is configured with
        ``extra='allow'`` in the SDK, so ``_meta`` is admitted as a
        forward-compat field. This is the path a future Phase 52
        enhancement would take if it decided to populate revision."""
        revision = _hex_sha256({"k": "v"})
        params = ResourceUpdatedNotificationParams.model_validate(
            {
                "uri": "corpus://status",
                "_meta": {"revision": revision},
            }
        )
        assert str(params.uri) == "corpus://status"
        # Pydantic stores extras on the model. ``_meta`` round-trips
        # through model_dump and is recovered by validate.
        dumped = params.model_dump(by_alias=True, exclude_none=True)
        assert dumped["_meta"]["revision"] == revision

    def test_revision_round_trip_preserves_64_char_hex(self) -> None:
        """End-to-end: build params with revision, serialize, parse,
        assert revision is still a 64-char hex string."""
        revision = _hex_sha256({"status": "completed", "job_id": "abc"})
        notif = ResourceUpdatedNotification(
            params=ResourceUpdatedNotificationParams.model_validate(
                {
                    "uri": "job://abc",
                    "_meta": {"revision": revision},
                }
            )
        )
        raw = notif.model_dump_json(by_alias=True, exclude_none=True)
        # ``_meta`` MUST survive serialization (extra fields on
        # NotificationParams are spec-required for forward compat).
        decoded = json.loads(raw)
        assert decoded["params"]["_meta"]["revision"] == revision
        assert len(decoded["params"]["_meta"]["revision"]) == 64

        # And parses back cleanly with no validation errors.
        parsed = ResourceUpdatedNotification.model_validate_json(raw)
        assert str(parsed.params.uri) == "job://abc"


class TestMethodLiteral:
    """The notification method string is fixed by the MCP spec.
    Any divergence is a spec violation that would break every client.
    """

    def test_method_literal_is_pinned(self) -> None:
        """``method`` must be exactly ``"notifications/resources/updated"``."""
        notif = ResourceUpdatedNotification(
            params=ResourceUpdatedNotificationParams(uri=AnyUrl("corpus://status"))
        )
        assert notif.method == "notifications/resources/updated"

    def test_method_cannot_be_overridden_to_arbitrary_string(self) -> None:
        """The method field is a ``Literal`` — pydantic refuses any
        other string. Pins that the SDK still treats the method as
        a constant (not a free-form string)."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ResourceUpdatedNotification.model_validate(
                {
                    "method": "notifications/something/else",
                    "params": {"uri": "corpus://status"},
                }
            )
