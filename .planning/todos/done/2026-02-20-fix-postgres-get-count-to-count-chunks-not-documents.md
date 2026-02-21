---
created: 2026-02-20T19:24:12.153Z
title: Fix postgres get_count to count chunks not documents
area: api
severity: low
files:
  - agent-brain-server/agent_brain_server/storage/postgres/backend.py:340-371
---

## Problem

`PostgresBackend.get_count()` counts rows in the `documents` table, but this table holds metadata rows (1 row per source file), not chunks. The status endpoint reports "Total Documents: 0" while "Total Chunks: 14328".

```python
# storage/postgres/backend.py:340-371
async def get_count(self, where=None) -> int:
    sql = f"SELECT COUNT(*) FROM documents {filter_clause}"
```

The verification code in `job_worker.py` calls `get_count()` expecting a chunk count, but gets a document-level count instead. This creates an inconsistency between what the status shows and what verification checks.

The status endpoint presumably gets its chunk count from a different source (BM25 or a separate query), creating confusion.

## Solution

Investigate what the `documents` table actually stores vs chunks:
- If documents table = source files and chunks are stored as individual rows, `get_count()` should count the right thing
- If chunks are embedded within document rows (JSONB array), the count needs to extract chunk counts
- Align `get_count()` with what ChromaBackend returns for the same concept (chunk count, not source file count)

The fix should make `get_count()` return the same semantic value (number of searchable chunks) regardless of backend, since the verification and status code depends on this.
