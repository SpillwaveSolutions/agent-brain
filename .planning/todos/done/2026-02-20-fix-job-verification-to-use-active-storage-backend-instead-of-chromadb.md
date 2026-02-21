---
created: 2026-02-20T19:24:12.153Z
title: Fix job verification to use active storage backend instead of ChromaDB
area: api
severity: critical
files:
  - agent-brain-server/agent_brain_server/services/job_worker.py:250-256
  - agent-brain-server/agent_brain_server/services/job_worker.py:386-433
  - agent-brain-server/agent_brain_server/services/indexing_service.py:89-93
---

## Problem

All indexing jobs report "FAILED" despite successful indexing when using the PostgreSQL backend.

**Root cause:** In `job_worker.py:250-256`, the verification uses `self._indexing_service.vector_store` which is a `VectorStoreManager` (ChromaDB). When using PostgreSQL backend, `PostgresBackend` does NOT have a `.vector_store` attribute, so `indexing_service.py:90-93` falls through to the else branch:

```python
# indexing_service.py:89-93
if hasattr(self.storage_backend, "vector_store"):
    self.vector_store = self.storage_backend.vector_store  # ChromaBackend has this
else:
    self.vector_store = vector_store or get_vector_store()  # FALLBACK: creates EMPTY ChromaDB!
```

So `self.vector_store` becomes a brand new, empty ChromaDB — completely disconnected from the PostgreSQL backend that actually stores the data.

Then in `job_worker.py:250-254`:
```python
count_before = 0
vector_store = self._indexing_service.vector_store  # Empty ChromaDB!
if vector_store.is_initialized:
    count_before = await vector_store.get_count()  # Always 0
```

And verification at line 386-433:
```python
count_after = await vector_store.get_count()  # Still 0
delta = count_after - count_before  # 0 - 0 = 0
# Falls into else branch:
logger.warning("Verification failed for job: no chunks in vector store")
return False
```

Also: The docstring on JobWorker (line 30) says "Verifies ChromaDB has chunks" — should be generalized.

## Solution

Replace `vector_store.get_count()` with `storage_backend.get_count()` in job_worker.py:

```python
# In job_worker.py, replace lines 250-256 and 400-401 with:
storage = self._indexing_service.storage_backend
if storage and hasattr(storage, 'is_initialized') and storage.is_initialized:
    count_before = await storage.get_count()
# ...
count_after = await storage.get_count()
```

Or add a `get_count()` convenience method to IndexingService that delegates to the active storage backend.

Update the JobWorker docstring to say "Verifies storage backend has chunks" instead of "Verifies ChromaDB has chunks."
