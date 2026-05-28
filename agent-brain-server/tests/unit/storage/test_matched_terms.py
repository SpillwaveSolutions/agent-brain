"""Tests for the matched_terms field on SearchResult (issue #159).

Covers:
- The Chroma backend's bm25s-based tokenizer + intersection.
- The Postgres backend's ts_headline parser.
- That `explain=False` (default) returns matched_terms=None — backward compat.
"""

from __future__ import annotations

from agent_brain_server.storage.chroma.backend import (
    _bm25_tokens,
    _intersect_tokens,
)
from agent_brain_server.storage.postgres.keyword_ops import _parse_headline_terms


class TestBm25TokenizerHelpers:
    """Verify the Chroma-side tokenizer mirrors the BM25 indexer."""

    def test_tokenize_lowercases_and_splits(self) -> None:
        tokens = _bm25_tokens("Authentication SETUP process")
        assert "authentication" in tokens
        assert "setup" in tokens
        assert "process" in tokens
        # No uppercase leaks through.
        assert "Authentication" not in tokens

    def test_tokenize_strips_english_stopwords(self) -> None:
        """Common English stopwords are dropped — they're noise as matches."""
        tokens = _bm25_tokens("the authentication is the setup")
        assert "authentication" in tokens
        assert "setup" in tokens
        # Stopwords stripped.
        assert "the" not in tokens
        assert "is" not in tokens

    def test_tokenize_handles_empty_input(self) -> None:
        assert _bm25_tokens("") == []
        assert _bm25_tokens("the and or") == []  # all stopwords -> empty

    def test_intersect_preserves_query_order(self) -> None:
        query_tokens = ["authentication", "oauth", "setup"]
        doc = "OAuth providers handle the authentication and setup flow."
        matched = _intersect_tokens(query_tokens, doc)
        # Order follows the query, not the document.
        assert matched == ["authentication", "oauth", "setup"]

    def test_intersect_deduplicates(self) -> None:
        query_tokens = ["auth", "auth", "setup"]
        doc = "auth setup auth"
        matched = _intersect_tokens(query_tokens, doc)
        assert matched == ["auth", "setup"]

    def test_intersect_excludes_misses(self) -> None:
        query_tokens = ["authentication", "rocketship"]
        doc = "authentication and authorization"
        matched = _intersect_tokens(query_tokens, doc)
        assert matched == ["authentication"]

    def test_intersect_empty_query_returns_empty(self) -> None:
        assert _intersect_tokens([], "anything") == []


class TestParseHeadlineTerms:
    """Verify the Postgres ts_headline parser."""

    def test_parse_extracts_wrapped_terms(self) -> None:
        """Standard case: ts_headline output with <<<...>>> sentinels."""
        headline = "The <<<authentication>>> flow uses <<<oauth>>> by default."
        assert _parse_headline_terms(headline) == ["authentication", "oauth"]

    def test_parse_lowercases_and_dedups(self) -> None:
        """Same term in multiple fragments collapses to one entry."""
        headline = "<<<Auth>>> sets up <<<auth>>> via <<<AUTH>>>"
        assert _parse_headline_terms(headline) == ["auth"]

    def test_parse_none_input(self) -> None:
        assert _parse_headline_terms(None) is None

    def test_parse_empty_input(self) -> None:
        assert _parse_headline_terms("") is None

    def test_parse_no_matches_returns_none(self) -> None:
        """A headline that didn't highlight anything maps to None."""
        assert _parse_headline_terms("Plain text with no markers.") is None

    def test_parse_strips_whitespace_inside_sentinels(self) -> None:
        headline = "<<< spaced >>> match"
        assert _parse_headline_terms(headline) == ["spaced"]


class TestSearchResultDefault:
    """Confirm backward compat: SearchResult defaults to matched_terms=None."""

    def test_default_construction(self) -> None:
        from agent_brain_server.storage.protocol import SearchResult

        res = SearchResult(text="hello", metadata={}, score=0.5, chunk_id="c1")
        assert res.matched_terms is None
