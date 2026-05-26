"""Chunk-ID uniqueness regression tests.

Regression coverage for issue #141: multi-part documents (e.g. PDF pages)
share the same `LoadedDocument.source`, so chunk IDs derived solely from
`(source, idx)` collide and storage silently overwrites them.

These tests pin the contract that:

  1. Two `LoadedDocument` instances sharing `source` but distinguished by a
     `page_label` metadata field MUST produce disjoint chunk IDs.
  2. A `LoadedDocument` without page metadata MUST keep its existing
     `(source, idx)` ID derivation (backwards compatibility — re-indexing
     existing corpora must not churn).
  3. Chunking the same document twice MUST yield identical chunk IDs
     (stability across re-indexing — the upsert contract).
"""

import hashlib

import pytest

from agent_brain_server.indexing.chunking import CodeChunker, ContextAwareChunker
from agent_brain_server.indexing.document_loader import LoadedDocument


def _make_pdf_page(source: str, page_label: str, text: str) -> LoadedDocument:
    """Build a LoadedDocument representing one page of a multi-page PDF."""
    return LoadedDocument(
        text=text,
        source=source,
        file_name="manual.pdf",
        file_path=source,
        file_size=len(text),
        metadata={
            "doc_id": f"uuid-{page_label}",
            "source": source,
            "source_type": "doc",
            "page_label": page_label,
        },
    )


@pytest.mark.asyncio
async def test_same_source_different_page_label_produces_disjoint_chunk_ids():
    """Two PDF pages sharing source but with different page_label must not collide."""
    text_a = "Alpha page content. " * 100
    text_b = "Bravo page content. " * 100
    page_one = _make_pdf_page("/tmp/manual.pdf", "1", text_a)
    page_two = _make_pdf_page("/tmp/manual.pdf", "2", text_b)

    chunker = ContextAwareChunker(chunk_size=128, chunk_overlap=16)
    chunks_one = await chunker.chunk_single_document(page_one)
    chunks_two = await chunker.chunk_single_document(page_two)

    assert chunks_one, "page 1 produced no chunks"
    assert chunks_two, "page 2 produced no chunks"

    ids_one = {c.chunk_id for c in chunks_one}
    ids_two = {c.chunk_id for c in chunks_two}
    overlap = ids_one & ids_two
    assert not overlap, (
        f"chunk_id collision between PDF pages 1 and 2: {sorted(overlap)}. "
        "Multi-page PDFs would silently overwrite each other in the vector "
        "store (issue #141)."
    )


@pytest.mark.asyncio
async def test_no_page_metadata_preserves_existing_chunk_ids():
    """Documents without page_label keep the legacy (source, idx) IDs.

    Stability matters here: changing the seed for non-PDF sources would
    invalidate every chunk ID in already-indexed corpora and force a full
    rebuild. We only disambiguate when page_label is present.
    """
    text = "Plain markdown body. " * 100
    doc = LoadedDocument(
        text=text,
        source="/tmp/README.md",
        file_name="README.md",
        file_path="/tmp/README.md",
        file_size=len(text),
        metadata={"doc_id": "uuid-readme", "source": "/tmp/README.md"},
    )

    chunker = ContextAwareChunker(chunk_size=128, chunk_overlap=16)
    chunks = await chunker.chunk_single_document(doc)

    assert chunks, "README produced no chunks"

    for chunk in chunks:
        expected_seed = f"/tmp/README.md_{chunk.chunk_index}"
        expected_id = f"chunk_{hashlib.md5(expected_seed.encode()).hexdigest()[:16]}"
        assert chunk.chunk_id == expected_id, (
            f"Backwards-compat broken for non-PDF source: chunk {chunk.chunk_index} "
            f"got {chunk.chunk_id}, expected {expected_id}"
        )


@pytest.mark.asyncio
async def test_chunk_ids_are_stable_across_reindexing():
    """Re-chunking the same document yields identical chunk IDs.

    The vector store relies on stable IDs to upsert (overwrite) chunks for
    unchanged files. If IDs were randomized per run, every re-index would
    insert duplicates instead of refreshing existing entries.
    """
    text = "Stable content for re-index. " * 100
    page = _make_pdf_page("/tmp/manual.pdf", "1", text)

    chunker = ContextAwareChunker(chunk_size=128, chunk_overlap=16)
    first = await chunker.chunk_single_document(page)
    second = await chunker.chunk_single_document(page)

    assert [c.chunk_id for c in first] == [c.chunk_id for c in second]


@pytest.mark.asyncio
async def test_code_chunker_same_source_different_page_label_disjoint():
    """CodeChunker shares the same id_seed pattern as the doc chunker.

    Less likely in practice (code files don't paginate), but the formula is
    identical so the fix must apply to both paths.
    """
    code_a = "def alpha():\n    return 1\n" * 30
    code_b = "def bravo():\n    return 2\n" * 30
    doc_a = LoadedDocument(
        text=code_a,
        source="/tmp/notebook.py",
        file_name="notebook.py",
        file_path="/tmp/notebook.py",
        file_size=len(code_a),
        metadata={
            "source_type": "code",
            "language": "python",
            "page_label": "cell-1",
        },
    )
    doc_b = LoadedDocument(
        text=code_b,
        source="/tmp/notebook.py",
        file_name="notebook.py",
        file_path="/tmp/notebook.py",
        file_size=len(code_b),
        metadata={
            "source_type": "code",
            "language": "python",
            "page_label": "cell-2",
        },
    )

    chunker = CodeChunker(language="python", chunk_lines=2, max_chars=80)
    chunks_a = await chunker.chunk_code_document(doc_a)
    chunks_b = await chunker.chunk_code_document(doc_b)

    assert chunks_a and chunks_b
    overlap = {c.chunk_id for c in chunks_a} & {c.chunk_id for c in chunks_b}
    assert (
        not overlap
    ), f"CodeChunker chunk_id collision across page_labels: {sorted(overlap)}"
