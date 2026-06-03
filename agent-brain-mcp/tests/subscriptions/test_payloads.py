"""Unit tests for :mod:`agent_brain_mcp.subscriptions.payloads`.

Covers Phase 52 CONTEXT decision B (diff-suppression hash strips
volatile keys at every nesting depth) and CONTEXT specifics #3 (the
explicit key allowlist must include ``timestamp``, ``updated_at``,
``elapsed_ms``, ``polled_at``).
"""

from __future__ import annotations

import pytest

from agent_brain_mcp.subscriptions import DEFAULT_DROP_KEYS, canonical_hash


class TestDefaultDropKeys:
    """:data:`DEFAULT_DROP_KEYS` must cover the keys CONTEXT calls out."""

    def test_is_frozenset(self) -> None:
        """Frozenset so callers can't accidentally mutate the default."""
        assert isinstance(DEFAULT_DROP_KEYS, frozenset)

    @pytest.mark.parametrize(
        "key",
        ["timestamp", "updated_at", "elapsed_ms", "polled_at", "now"],
    )
    def test_contains_required_key(self, key: str) -> None:
        """The CONTEXT-mandated volatile keys are all present."""
        assert key in DEFAULT_DROP_KEYS


class TestCanonicalHashBasics:
    """Output shape and determinism."""

    def test_returns_64_char_hex(self) -> None:
        """SHA-256 hex = 64 lowercase hex chars."""
        h = canonical_hash({"a": 1})
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_deterministic(self) -> None:
        """Same input → same hash across calls."""
        payload = {"value": 42, "name": "foo", "items": [1, 2, 3]}
        assert canonical_hash(payload) == canonical_hash(payload)

    def test_key_order_does_not_matter(self) -> None:
        """``sort_keys=True`` makes insertion order irrelevant."""
        a = {"x": 1, "y": 2, "z": 3}
        b = {"z": 3, "y": 2, "x": 1}
        assert canonical_hash(a) == canonical_hash(b)

    def test_different_scalar_yields_different_hash(self) -> None:
        """Genuine change in a non-volatile scalar flips the digest."""
        assert canonical_hash({"value": 42}) != canonical_hash({"value": 43})


class TestRecursiveDrop:
    """``canonical_hash`` must strip ``drop`` keys at EVERY nesting depth.

    Plan 03's ``corpus://status`` policy depends on this: uvicorn embeds
    timestamps deep in the health payload, and a one-level-deep strip
    would leak the volatile field into the hash.
    """

    def test_top_level_timestamp_dropped(self) -> None:
        """A top-level ``timestamp`` mutation must not change the hash."""
        a = {"value": 42, "timestamp": "2026-06-02T00:00:00Z"}
        b = {"value": 42, "timestamp": "2026-06-03T00:00:00Z"}
        assert canonical_hash(a) == canonical_hash(b)

    def test_nested_timestamp_dropped(self) -> None:
        """Nested ``timestamp`` mutation also yields the same hash."""
        a = {"a": {"b": {"timestamp": "2026-01-01", "value": 42}}}
        b = {"a": {"b": {"timestamp": "2099-12-31", "value": 42}}}
        assert canonical_hash(a) == canonical_hash(b)

    def test_deeply_nested_timestamp_dropped(self) -> None:
        """Drop applies at every depth, however deep."""
        a = {
            "lvl1": {
                "lvl2": {
                    "lvl3": {
                        "lvl4": {
                            "value": "stable",
                            "updated_at": "morning",
                        }
                    }
                }
            }
        }
        b = {
            "lvl1": {
                "lvl2": {
                    "lvl3": {
                        "lvl4": {
                            "value": "stable",
                            "updated_at": "evening",
                        }
                    }
                }
            }
        }
        assert canonical_hash(a) == canonical_hash(b)

    def test_timestamp_inside_list_of_dicts_dropped(self) -> None:
        """List elements that are dicts have ``drop`` keys stripped too."""
        a = {
            "jobs": [
                {"id": "1", "status": "running", "timestamp": "T1"},
                {"id": "2", "status": "queued", "timestamp": "T1"},
            ]
        }
        b = {
            "jobs": [
                {"id": "1", "status": "running", "timestamp": "T999"},
                {"id": "2", "status": "queued", "timestamp": "T999"},
            ]
        }
        assert canonical_hash(a) == canonical_hash(b)

    def test_non_volatile_field_at_depth_3_changes_hash(self) -> None:
        """Genuine change at any depth must change the hash."""
        a = {"a": {"b": {"c": "before"}}}
        b = {"a": {"b": {"c": "after"}}}
        assert canonical_hash(a) != canonical_hash(b)

    def test_custom_drop_set_overrides_default(self) -> None:
        """Caller-supplied ``drop`` replaces the default; ``timestamp``
        is NOT stripped unless explicitly included."""
        a = {"value": 42, "timestamp": "T1"}
        b = {"value": 42, "timestamp": "T2"}
        # With an empty drop set, the timestamp mutation IS visible.
        assert canonical_hash(a, drop=set()) != canonical_hash(b, drop=set())


class TestEdgeCases:
    """Robustness against non-trivial payloads."""

    def test_empty_dict(self) -> None:
        """Empty dict hashes to a stable value (``{}``)."""
        h1 = canonical_hash({})
        h2 = canonical_hash({})
        assert h1 == h2

    def test_list_top_level_not_supported_via_dict_wrapper(self) -> None:
        """``canonical_hash`` types ``payload: dict[str, Any]``. List
        payloads must be wrapped by the caller — verifies the contract."""
        payload: dict = {"items": [1, 2, 3]}
        # Just ensures lists inside dicts hash and that order is preserved.
        h1 = canonical_hash(payload)
        h2 = canonical_hash({"items": [1, 2, 3]})
        assert h1 == h2
        # Different list order is a genuine change (lists ARE ordered).
        assert canonical_hash({"items": [3, 2, 1]}) != h1

    def test_none_value_preserved(self) -> None:
        """``None`` values inside the payload are JSON-serialized as
        ``null`` and contribute to the hash."""
        h1 = canonical_hash({"k": None})
        h2 = canonical_hash({"k": None})
        assert h1 == h2
        # Different from missing key.
        assert canonical_hash({"k": None}) != canonical_hash({})

    def test_non_serializable_raises(self) -> None:
        """Non-JSON-serializable values surface as ``TypeError``."""

        class Opaque:
            pass

        with pytest.raises(TypeError):
            canonical_hash({"obj": Opaque()})

    def test_tuple_treated_like_list(self) -> None:
        """JSON has no tuple type; our ``_strip`` flattens tuple →
        list before hashing for stability."""
        a = {"items": (1, 2, 3)}
        b = {"items": [1, 2, 3]}
        assert canonical_hash(a) == canonical_hash(b)
