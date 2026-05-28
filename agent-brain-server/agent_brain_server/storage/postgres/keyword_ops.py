"""tsvector keyword search and upsert operations.

This module provides the KeywordOps class for performing full-text keyword
search using PostgreSQL tsvector with weighted relevance (title=A, summary=B,
content=C) and configurable language support.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from sqlalchemy import text

from agent_brain_server.storage.postgres.connection import PostgresConnectionManager
from agent_brain_server.storage.protocol import SearchResult, StorageError

logger = logging.getLogger(__name__)


# Issue #159: parse the wrapped fragments from a ts_headline output back
# into a deduplicated, lowercase list of matched terms.
_HEADLINE_TERM_RE = re.compile(r"<<<(.+?)>>>")


def _parse_headline_terms(headline: str | None) -> list[str] | None:
    """Extract the highlighted terms from a ts_headline string."""
    if not headline:
        return None
    seen: set[str] = set()
    ordered: list[str] = []
    for raw in _HEADLINE_TERM_RE.findall(headline):
        term = raw.strip().lower()
        if term and term not in seen:
            seen.add(term)
            ordered.append(term)
    return ordered or None


class KeywordOps:
    """tsvector keyword search and upsert operations.

    Uses PostgreSQL full-text search with weighted tsvector columns
    (title=A, summary=B, content=C) for relevance boosting. Query
    parsing uses ``websearch_to_tsquery()`` for user-friendly syntax.

    Scores are normalized to 0-1 via per-query max normalization,
    matching the ChromaBackend BM25 approach.

    Attributes:
        connection_manager: Initialized PostgresConnectionManager.
        language: PostgreSQL text search language configuration.
    """

    def __init__(
        self,
        connection_manager: PostgresConnectionManager,
        language: str = "english",
    ) -> None:
        """Initialize keyword operations.

        Args:
            connection_manager: An initialized PostgresConnectionManager.
            language: PostgreSQL tsvector language (default: ``english``).
        """
        self.connection_manager = connection_manager
        self.language = language

    async def upsert_with_tsvector(
        self,
        chunk_id: str,
        document_text: str,
        metadata: dict[str, Any],
    ) -> None:
        """Upsert a document with weighted tsvector for full-text search.

        Builds a combined tsvector with weights:
        - A: title (from metadata filename or title)
        - B: summary (from metadata summary)
        - C: document text (body content)

        Uses INSERT ... ON CONFLICT DO UPDATE for idempotent upserts.

        Args:
            chunk_id: Unique chunk identifier.
            document_text: Full text content of the document chunk.
            metadata: Document metadata dictionary. Keys used for
                tsvector weighting: ``filename``, ``title``, ``summary``.

        Raises:
            StorageError: If the upsert operation fails.
        """
        engine = self.connection_manager.engine
        try:
            title = metadata.get("filename") or metadata.get("title") or ""
            summary = metadata.get("summary") or ""
            metadata_json = json.dumps(metadata)

            sql = """
                INSERT INTO documents
                    (chunk_id, document_text, metadata, tsv)
                VALUES (
                    :chunk_id, :document_text, CAST(:metadata AS jsonb),
                    setweight(to_tsvector(
                        :language, COALESCE(:title, '')
                    ), 'A') ||
                    setweight(to_tsvector(
                        :language, COALESCE(:summary, '')
                    ), 'B') ||
                    setweight(to_tsvector(
                        :language, :document_text
                    ), 'C')
                )
                ON CONFLICT (chunk_id) DO UPDATE SET
                    document_text = EXCLUDED.document_text,
                    metadata = EXCLUDED.metadata,
                    tsv = EXCLUDED.tsv,
                    updated_at = NOW()
            """

            async with engine.begin() as conn:
                await conn.execute(
                    text(sql),
                    {
                        "chunk_id": chunk_id,
                        "document_text": document_text,
                        "metadata": metadata_json,
                        "language": self.language,
                        "title": title,
                        "summary": summary,
                    },
                )
        except Exception as e:
            raise StorageError(
                f"Failed to upsert document with tsvector for "
                f"chunk {chunk_id}: {e}",
                backend="postgres",
            ) from e

    async def keyword_search(
        self,
        query: str,
        top_k: int,
        source_types: list[str] | None = None,
        languages: list[str] | None = None,
        explain: bool = False,
    ) -> list[SearchResult]:
        """Perform full-text keyword search using tsvector.

        Uses ``websearch_to_tsquery()`` for user-friendly query syntax
        (supports AND, OR, quoted phrases, negation with ``-``).

        Scores are normalized to 0-1 via per-query max normalization
        (dividing all scores by the highest score in the result set).

        Args:
            query: Search query string.
            top_k: Maximum number of results to return.
            source_types: Optional filter by ``source_type`` metadata field.
            languages: Optional filter by ``language`` metadata field.
            explain: When True (issue #159), include ``ts_headline()`` output
                and parse it to populate ``SearchResult.matched_terms``.

        Returns:
            List of SearchResult sorted by score descending, with
            scores normalized to 0-1 range.

        Raises:
            StorageError: If the search operation fails.
        """
        engine = self.connection_manager.engine
        try:
            params: dict[str, Any] = {
                "language": self.language,
                "query": query,
                "top_k": top_k,
            }

            # Build optional filter clauses
            filter_clauses: list[str] = []

            if source_types:
                filter_clauses.append(
                    "AND metadata->>'source_type' = ANY(:source_types)"
                )
                params["source_types"] = source_types

            if languages:
                filter_clauses.append("AND metadata->>'language' = ANY(:languages)")
                params["languages"] = languages

            filter_sql = "\n".join(filter_clauses)

            # Issue #159: when explain=True, also pull a ts_headline using
            # a sentinel "<<<term>>>" wrapper so we can parse the matched
            # terms back out without HTML escaping concerns.
            headline_select = (
                ", ts_headline(:language, document_text, "
                "websearch_to_tsquery(:language, :query), "
                "'StartSel=<<<, StopSel=>>>, MaxFragments=10, MaxWords=20, "
                "MinWords=5') AS headline"
                if explain
                else ""
            )

            sql = f"""
                SELECT chunk_id, document_text, metadata,
                       ts_rank(tsv, websearch_to_tsquery(:language, :query))
                           AS score{headline_select}
                FROM documents
                WHERE tsv @@ websearch_to_tsquery(:language, :query)
                {filter_sql}
                ORDER BY score DESC
                LIMIT :top_k
            """

            async with engine.connect() as conn:
                result = await conn.execute(text(sql), params)
                rows = result.fetchall()

            if not rows:
                return []

            # Per-query max normalization (matching ChromaBackend BM25)
            max_score = max(float(row[3]) for row in rows)
            if max_score <= 0:
                max_score = 1.0

            results: list[SearchResult] = []
            for row in rows:
                raw_score = float(row[3])
                normalized_score = raw_score / max_score

                metadata_val = row[2]
                if isinstance(metadata_val, str):
                    metadata_val = json.loads(metadata_val)

                matched_terms = (
                    _parse_headline_terms(row[4]) if explain and len(row) > 4 else None
                )

                results.append(
                    SearchResult(
                        text=row[1],
                        metadata=metadata_val,
                        score=normalized_score,
                        chunk_id=row[0],
                        matched_terms=matched_terms,
                    )
                )

            return results

        except StorageError:
            raise
        except Exception as e:
            raise StorageError(
                f"Keyword search failed: {e}",
                backend="postgres",
            ) from e
