# Phase 13: Content Injection Pipeline - Research

**Researched:** 2026-03-05
**Domain:** Python dynamic module loading, metadata enrichment pipeline, CLI extension patterns
**Confidence:** HIGH

## Summary

Phase 13 adds a content injection hook to the existing indexing pipeline. Users provide either a Python script exporting `process_chunk(chunk: dict) -> dict` or a JSON file containing static metadata; both are merged into `ChunkMetadata.extra` before embedding generation. The implementation is almost entirely additive: a new `ContentInjector` service, a new `inject` CLI command that delegates to the existing `index` command logic, and a `--dry-run` path that validates script+sample chunks without touching the vector store.

The pipeline insertion point is already identified: `IndexingService._run_indexing_pipeline` in `agent-brain-server/agent_brain_server/services/indexing_service.py` at the boundary between Step 2 (chunk) and Step 3 (embed). `ChunkMetadata.extra` is a `dict[str, Any]` that is already flattened into the ChromaDB metadata dict via `to_dict()` — injection is a matter of merging a dict. The per-chunk error handling requirement (INJECT-05) matches the existing pattern of try/except with logger.warning already used throughout the chunking code.

Dynamic script loading is a solved Python problem via `importlib.util.spec_from_file_location` / `exec_module`. The `process_chunk` protocol is a simple callable validated with `callable()` + `hasattr()` on the loaded module. The `--dry-run` flag runs the injector against a small sample of chunks (5-10) captured after chunking and returns a report, without reaching the embedding or storage steps. The entire phase is one plan with ~8 tasks.

**Primary recommendation:** Implement `ContentInjector` as a standalone service class in `agent-brain-server/agent_brain_server/services/content_injector.py`, inject it into `IndexingService.__init__` as an optional parameter (following the FolderManager pattern), and add a new `inject` CLI command in `agent-brain-cli/agent_brain_cli/commands/inject.py` that mirrors `index_command` with additional `--script`, `--folder-metadata`, and `--dry-run` options.

---

## Standard Stack

### Core (no new dependencies required)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `importlib.util` | stdlib | Dynamic script loading (`spec_from_file_location`, `exec_module`) | Stdlib, avoids `exec()` security issues, proper module isolation |
| `json` | stdlib | Load `--folder-metadata` JSON file | Already used throughout project |
| `pathlib.Path` | stdlib | Path validation for `--script` and `--folder-metadata` | Already used throughout project |
| `logging` | stdlib | Per-chunk warning on injection failure (INJECT-05) | Already used throughout project |
| `typing.Protocol` | stdlib | Define `ChunkInjectorProtocol` for type checking | Already used in `StorageBackendProtocol` |

### Supporting (already in project)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `click` | existing | CLI `--script`, `--folder-metadata`, `--dry-run` options | New `inject` command |
| `rich.console` | existing | Dry-run report table output | Always for CLI output |
| `pydantic` | existing | Extend `IndexRequest` with `injector_script` + `folder_metadata` fields | Request model extension |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `importlib.util.spec_from_file_location` | `exec(open(...).read())` | `exec` pollutes namespace, no module isolation, no mypy compatibility |
| `importlib.util.spec_from_file_location` | `runpy.run_path` | `runpy` is acceptable alternative, slightly less explicit; `importlib` is the modern idiom |
| Inline injector in IndexingService | Separate `ContentInjector` class | Inline is harder to test, harder to mock, harder to extend |

**Installation:** No new packages needed.

---

## Architecture Patterns

### Recommended Project Structure

```
agent-brain-server/
├── agent_brain_server/
│   └── services/
│       ├── content_injector.py     # NEW: ContentInjector service class
│       ├── indexing_service.py     # MODIFIED: accept optional injector param
│       ├── folder_manager.py       # reference pattern
│       └── file_type_presets.py    # reference pattern
agent-brain-cli/
├── agent_brain_cli/
│   └── commands/
│       ├── inject.py               # NEW: inject CLI command
│       └── index.py                # reference pattern
```

### Pattern 1: ContentInjector Service Class

Follow the `FolderManager` pattern exactly: standalone class with `__init__`, initialized from `IndexingService.__init__` as an optional parameter.

```python
# agent_brain_server/services/content_injector.py
from __future__ import annotations

import importlib.util
import json
import logging
import types
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ContentInjector:
    """Enriches chunk dicts with custom metadata before embedding.

    Supports two modes:
    1. Python script exporting process_chunk(chunk: dict) -> dict
    2. Folder-level JSON metadata merged into all chunks

    Per-chunk exceptions are caught and logged — they never crash
    the indexing job (INJECT-05).
    """

    def __init__(
        self,
        script_path: Path | None = None,
        folder_metadata: dict[str, Any] | None = None,
    ) -> None:
        self._script_path = script_path
        self._folder_metadata = folder_metadata or {}
        self._process_chunk_fn: Any = None  # loaded lazily

        if script_path is not None:
            self._load_script(script_path)

    def _load_script(self, script_path: Path) -> None:
        """Load and validate the injector script.

        Raises:
            FileNotFoundError: If script_path does not exist.
            AttributeError: If module does not export process_chunk.
            TypeError: If process_chunk is not callable.
        """
        if not script_path.exists():
            raise FileNotFoundError(f"Injector script not found: {script_path}")

        spec = importlib.util.spec_from_file_location("_injector_script", script_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load script: {script_path}")

        module = types.ModuleType("_injector_script")
        spec.loader.exec_module(module)  # type: ignore[attr-defined]

        if not hasattr(module, "process_chunk"):
            raise AttributeError(
                f"Script {script_path} must export a 'process_chunk' callable"
            )

        fn = getattr(module, "process_chunk")
        if not callable(fn):
            raise TypeError(f"'process_chunk' in {script_path} must be callable")

        self._process_chunk_fn = fn
        logger.info(f"Loaded injector script: {script_path}")

    @classmethod
    def from_folder_metadata_file(cls, metadata_path: Path) -> "ContentInjector":
        """Create a ContentInjector from a JSON metadata file.

        Args:
            metadata_path: Path to JSON file with metadata dict.

        Returns:
            ContentInjector with folder_metadata populated.

        Raises:
            FileNotFoundError: If metadata_path does not exist.
            json.JSONDecodeError: If file is not valid JSON.
            TypeError: If JSON root is not an object (dict).
        """
        if not metadata_path.exists():
            raise FileNotFoundError(f"Metadata file not found: {metadata_path}")

        with open(metadata_path, encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise TypeError(
                f"Metadata file {metadata_path} must be a JSON object, "
                f"got {type(data).__name__}"
            )

        return cls(folder_metadata=data)

    def apply(self, chunk: dict[str, Any]) -> dict[str, Any]:
        """Apply injection to a single chunk dict.

        Merges folder_metadata first, then calls process_chunk if loaded.
        Per-chunk errors are caught and logged (INJECT-05).

        Args:
            chunk: Flat chunk dict as produced by ChunkMetadata.to_dict().

        Returns:
            Enriched chunk dict (may be same object with mutations or new dict).
        """
        # Start with folder-level static metadata (shallow merge)
        if self._folder_metadata:
            try:
                chunk = {**chunk, **self._folder_metadata}
            except Exception as e:
                logger.warning(f"Failed to merge folder metadata into chunk: {e}")

        # Apply script injector
        if self._process_chunk_fn is not None:
            try:
                result = self._process_chunk_fn(chunk)
                if isinstance(result, dict):
                    chunk = result
                else:
                    logger.warning(
                        f"process_chunk returned {type(result).__name__}, "
                        "expected dict — skipping enrichment for this chunk"
                    )
            except Exception as e:
                logger.warning(
                    f"Injector exception for chunk "
                    f"'{chunk.get('chunk_id', 'unknown')}': {e} — "
                    "skipping enrichment, continuing indexing"
                )

        return chunk
```

**Confidence:** HIGH — verified against `importlib` stdlib docs and existing `Protocol` usage in project.

### Pattern 2: Injection Hook in IndexingService

The hook goes **after** chunking and **before** `embed_chunks`. Chunks are stored as `TextChunk | CodeChunk` objects with a `metadata: ChunkMetadata` attribute. The injector receives the flat dict from `chunk.metadata.to_dict()`, enriches it, then writes it back to `chunk.metadata.extra`.

```python
# In IndexingService._run_indexing_pipeline, after chunks assembled:

# Step 2.5: Apply content injection (INJECT-03, INJECT-07)
if self.content_injector is not None:
    for chunk in chunks:
        original_dict = chunk.metadata.to_dict()
        enriched_dict = self.content_injector.apply(original_dict)
        # Extract injected keys back into extra
        # Keys already in fixed ChunkMetadata fields are ignored;
        # new/changed keys go to extra
        known_keys = {
            "chunk_id", "source", "file_name", "chunk_index", "total_chunks",
            "source_type", "created_at", "language", "heading_path",
            "section_title", "content_type", "symbol_name", "symbol_kind",
            "start_line", "end_line", "section_summary", "prev_section_summary",
            "docstring", "parameters", "return_type", "decorators", "imports",
        }
        for key, val in enriched_dict.items():
            if key not in known_keys:
                chunk.metadata.extra[key] = val
    logger.info(f"Applied content injection to {len(chunks)} chunks")
```

**Why this approach:** `ChunkMetadata.extra` is already the designed extension point (present in both `TextChunk` and `CodeChunk`). The `to_dict()` method already flattens `extra` via `data.update(self.extra)`. No schema changes needed to ChromaDB or BM25.

**Confidence:** HIGH — verified by reading `chunking.py` lines 56, 102-103.

### Pattern 3: IndexRequest Extension (INJECT-01, INJECT-04)

Extend `IndexRequest` with two optional fields (both `None` by default — backward compatible):

```python
# In agent_brain_server/models/index.py, inside IndexRequest:
injector_script: str | None = Field(
    default=None,
    description="Path to Python script exporting process_chunk(chunk: dict) -> dict",
)
folder_metadata_file: str | None = Field(
    default=None,
    description="Path to JSON file with static metadata to merge into all chunks",
)
```

**Note:** These are server-side paths — the CLI must resolve them to absolute paths before sending to the API. This matches how `folder_path` is handled.

**Confidence:** HIGH — follows existing `IndexRequest` field extension pattern (Phase 12 added `include_types`).

### Pattern 4: `inject` CLI Command

The `inject` command is a thin wrapper around `index` with three additional options. It uses the same `DocServeClient.index()` call, passing injector parameters in the request body.

```python
# agent_brain_cli/commands/inject.py
@click.command("inject")
@click.argument("folder_path", type=click.Path(exists=True, file_okay=False))
@click.option("--script", "injector_script", type=click.Path(exists=True),
              help="Python script exporting process_chunk(chunk: dict) -> dict")
@click.option("--folder-metadata", "folder_metadata",
              type=click.Path(exists=True),
              help="JSON file with static metadata to merge into all chunks")
@click.option("--dry-run", is_flag=True,
              help="Validate injector script against sample chunks without indexing")
# ... inherits all index_command options ...
```

**Dry-run path:** Client-side only (no server round-trip). Load and validate the script locally, load 1-3 sample text files from the folder, chunk them with `ContextAwareChunker`, run `ContentInjector.apply()` on each, display a Rich table showing original vs. enriched metadata.

**Confidence:** MEDIUM — dry-run as a pure client-side operation avoids adding a `dry_run` mode to the server API, keeping server complexity low. This matches the spirit of INJECT-06 ("tests injector script against sample chunks without indexing").

### Pattern 5: ContentInjector Registration in IndexingService.__init__

Follow the `FolderManager` injection pattern:

```python
# In IndexingService.__init__ signature:
def __init__(
    self,
    ...,
    folder_manager: FolderManager | None = None,
    content_injector: ContentInjector | None = None,  # ADD THIS
) -> None:
    ...
    self.content_injector = content_injector  # Store, use in pipeline
```

The `IndexingService` singleton factory `get_indexing_service()` does NOT create a `ContentInjector` — it remains None by default. The `ContentInjector` is created from request parameters at the job-dispatch layer (either in the API router for direct calls, or in `JobWorker._process_job` for queued jobs).

**Confidence:** HIGH — directly mirrors FolderManager pattern verified in indexing_service.py lines 62-111.

### Pattern 6: JobRecord Extension for Queued Injection

`JobWorker._process_job` creates the `IndexRequest` from `JobRecord` fields (lines 210-222). To support injection in queued jobs, `JobRecord` needs two additional optional fields:

```python
# In agent_brain_server/models/job.py:
injector_script: str | None = Field(default=None, ...)
folder_metadata_file: str | None = Field(default=None, ...)
```

Then in `JobWorker._process_job`:
```python
content_injector = None
if job.injector_script or job.folder_metadata_file:
    from agent_brain_server.services.content_injector import ContentInjector
    content_injector = ContentInjector.build_from_paths(
        script_path=Path(job.injector_script) if job.injector_script else None,
        metadata_path=Path(job.folder_metadata_file) if job.folder_metadata_file else None,
    )
# Temporarily attach to indexing_service for this job
original_injector = self._indexing_service.content_injector
self._indexing_service.content_injector = content_injector
try:
    await asyncio.wait_for(
        self._indexing_service._run_indexing_pipeline(...),
        ...
    )
finally:
    self._indexing_service.content_injector = original_injector
```

**Alternative:** Pass `content_injector` directly to `_run_indexing_pipeline` as a parameter — cleaner, avoids mutation of singleton state. Recommend this approach.

**Confidence:** HIGH — pattern is consistent with how `force` is threaded through the pipeline.

### Anti-Patterns to Avoid

- **exec() for script loading:** `exec(open(path).read())` pollutes the current namespace, has no module isolation, and is unsafe. Use `importlib.util.spec_from_file_location` always.
- **Catching BaseException in apply():** Only catch `Exception`. `KeyboardInterrupt` and `SystemExit` must propagate.
- **Nested dicts in injection metadata:** ChromaDB metadata requires flat scalar values (`str`, `int`, `float`, `bool`). If a user injects a nested dict or list, `chunk.metadata.to_dict()` will include it, but ChromaDB will reject it at upsert time. Validate and flatten injected metadata before the storage step.
- **Injecting non-serializable values:** Custom class instances, callables, etc. Validate that all injected values are JSON-serializable before writing to `extra`.
- **Breaking the test: no ContentInjector in get_indexing_service():** The singleton must remain injection-free. ContentInjector is per-request, not global.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Dynamic Python module loading | Custom `exec`/`compile` wrapper | `importlib.util.spec_from_file_location` + `exec_module` | Module isolation, proper `__file__` attribute, stdlib |
| JSON metadata loading | Custom parser | `json.load()` | Standard, already used project-wide |
| Protocol type checking | Custom ABC | `typing.Protocol` with `runtime_checkable` | Already the project pattern (StorageBackendProtocol) |
| Dry-run document loading | Custom file reader | Reuse `DocumentLoader` from indexing package | Already battle-tested in the project |

**Key insight:** Every component needed for Phase 13 already exists in the project. This phase is about wiring, not new infrastructure.

---

## Common Pitfalls

### Pitfall 1: ChromaDB Rejects Non-Scalar Metadata Values

**What goes wrong:** User's `process_chunk` injects `{"tags": ["a", "b"]}` or `{"config": {"key": "val"}}`. These pass `to_dict()` fine (it uses `data.update(self.extra)`), but ChromaDB's `upsert` raises a validation error at storage time.

**Why it happens:** ChromaDB metadata fields must be `str | int | float | bool`. Lists and nested dicts are not supported in ChromaDB 0.3.x/0.4.x metadata.

**How to avoid:** In `ContentInjector.apply()`, after the user's `process_chunk` returns, validate the new keys. Either: (a) silently flatten lists to comma-joined strings, or (b) log a warning and skip non-scalar values. Document this in injector protocol docs.

**Warning signs:** `chromadb.errors.InvalidArgumentError` at the `upsert_documents` step, not at injection time — hard to trace back to user script.

**Confidence:** HIGH — verified in existing `to_dict()` pattern and ChromaDB docs.

### Pitfall 2: Injector Script Side Effects on Import

**What goes wrong:** User's script has top-level code that runs `requests.get(...)` or writes to a file on import. `importlib.util.exec_module` executes all top-level code.

**Why it happens:** Python module execution runs all top-level statements.

**How to avoid:** Document that `process_chunk` must be the only exported symbol used. Cannot prevent (short of sandboxing, which is out of scope). Log that the script was loaded and mention it in the protocol docs (INJECT-08).

**Warning signs:** Slow script loading, network errors during indexing startup.

### Pitfall 3: Mutation of Chunk Dict Breaking Later Pipeline Steps

**What goes wrong:** User's `process_chunk` deletes required fields (`chunk_id`, `source`, etc.) from the dict. The pipeline then fails at the embedding or storage step.

**Why it happens:** The chunk dict passed to `process_chunk` is a copy from `to_dict()`, but if the user script deletes keys that are later read back and written to `chunk.metadata.extra`, there is no issue. The problem only arises if the caller directly stores the returned dict.

**How to avoid:** The injection pattern in "Pattern 2" above extracts only NEW or CHANGED keys from the enriched dict, ignoring deletions of known fields. This is the safe approach: `for key, val in enriched_dict.items(): if key not in known_keys: chunk.metadata.extra[key] = val`. Deletions of core fields are simply ignored.

**Warning signs:** `KeyError` at `upsert_documents` time on `chunk_id` or `source`.

### Pitfall 4: Dry-Run Requires Server to Be Running (Wrong Design)

**What goes wrong:** Implementing `--dry-run` as a server-side endpoint that requires the full indexing stack to be live.

**Why it happens:** Treating `--dry-run` as an API feature rather than a client-side validation tool.

**How to avoid:** Implement `--dry-run` entirely in the CLI process, importing `ContentInjector` from the server package if installed, or duplicating the minimal logic. This avoids a server dependency and matches the user mental model of "validate before indexing."

**Note:** The CLI (`agent-brain-cli`) does NOT import from `agent-brain-rag` (server package) in the current design (Phase 12 hardcoded FILE_TYPE_PRESETS to avoid cross-package deps). Dry-run must therefore duplicate the minimal ContentInjector loading logic in the CLI package, or the dry-run can be server-mediated via a dedicated `POST /index/dry-run` endpoint. Given the Phase 12 precedent, recommend the **server-mediated** approach: add a `dry_run: bool` query param to `POST /index/` that runs injection validation and returns a report without enqueueing.

**Confidence:** MEDIUM — design decision; both approaches are valid.

### Pitfall 5: ContentInjector State Leaking Between Jobs

**What goes wrong:** If `ContentInjector` is attached to the `IndexingService` singleton and a second job starts before the first completes (though worker processes one job at a time currently), the injector from job 1 could be used for job 2.

**Why it happens:** Singleton service state mutation.

**How to avoid:** Pass `content_injector` as a parameter to `_run_indexing_pipeline(request, job_id, progress_callback, content_injector=None)` rather than mutating `self.content_injector`. This is the cleanest approach.

**Confidence:** HIGH — current `JobWorker` is single-threaded (one job at a time), but the per-call parameter pattern is safer and easier to test.

---

## Code Examples

Verified patterns from codebase and stdlib:

### Dynamic Script Loading (stdlib importlib)

```python
# Source: Python 3.10+ stdlib importlib.util docs + codebase pattern
import importlib.util
import types
from pathlib import Path

def load_injector_module(script_path: Path) -> types.ModuleType:
    """Load a Python script as a module."""
    spec = importlib.util.spec_from_file_location("_injector", script_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load: {script_path}")
    module = types.ModuleType("_injector")
    module.__file__ = str(script_path)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module
```

### Example User Injector Script (for documentation, INJECT-08)

```python
# enrich.py — example injector script
# Exports: process_chunk(chunk: dict) -> dict

def process_chunk(chunk: dict) -> dict:
    """Add custom metadata to each chunk.

    Args:
        chunk: Flat metadata dict from ChunkMetadata.to_dict().
                Keys include: chunk_id, source, file_name, chunk_index,
                total_chunks, source_type, language, etc.

    Returns:
        Enriched dict. New keys are merged into ChunkMetadata.extra.
        Existing keys can be overridden. Values must be str/int/float/bool.
    """
    # Example: tag all chunks with project name
    chunk["project"] = "my-project"
    chunk["team"] = "platform"

    # Example: conditional enrichment
    if chunk.get("source_type") == "code":
        chunk["code_reviewed"] = False

    return chunk
```

### Folder Metadata JSON (for documentation, INJECT-08)

```json
{
    "project": "agent-brain",
    "team": "platform",
    "environment": "production",
    "data_classification": "internal"
}
```

### Per-Chunk Error Handling (INJECT-05)

```python
# Pattern from existing codebase: logger.error + continue
# Source: indexing_service.py lines 417-428
try:
    result = self._process_chunk_fn(chunk)
except Exception as e:
    logger.warning(
        f"Injector exception for chunk '{chunk.get('chunk_id', 'unknown')}': "
        f"{e} — skipping enrichment, continuing indexing"
    )
    # result stays as original chunk — no enrichment applied
```

### IndexingService.__init__ Optional Injector (Pattern follows FolderManager)

```python
# Source: indexing_service.py lines 62-111 — FolderManager injection pattern
def __init__(
    self,
    ...,
    folder_manager: FolderManager | None = None,
    content_injector: ContentInjector | None = None,
) -> None:
    ...
    self.folder_manager = folder_manager
    self.content_injector = content_injector
```

---

## Pipeline Integration Map

```
IndexingService._run_indexing_pipeline():
  Step 1: Load documents           ← unchanged
  Step 2: Chunk documents          ← unchanged
  [NEW] Step 2.5: Apply injection  ← ContentInjector.apply() per chunk
  Step 3: Generate embeddings      ← unchanged (enriched extra is in ChunkMetadata.extra)
  Step 4: Store in vector database ← ChunkMetadata.to_dict() flattens extra — no changes needed
  Step 5: Build BM25 index         ← unchanged
  Step 6: Build graph index        ← unchanged
```

The injection step calls `ContentInjector.apply(chunk.metadata.to_dict())`, extracts new keys, and writes them to `chunk.metadata.extra`. The `to_dict()` call at Step 4 then naturally includes those keys.

**No changes needed to storage layer, BM25 index, or graph index.**

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `exec(script_content)` | `importlib.util.spec_from_file_location` | Python 3.4+ | Better isolation, proper `__file__` |
| Flat metadata only | `ChunkMetadata.extra` dict | Phase 12 (existing) | Extension point already in place |
| importlib.machinery | importlib.util | Python 3.1+ | `importlib.util` is the recommended API |

**Note:** `runpy.run_path()` is an acceptable alternative to `importlib.util` for this use case. Both are stdlib, both execute the script in a fresh namespace. `importlib.util` gives more control over the module object; `runpy.run_path` returns a dict of globals. Either works. Recommend `importlib.util` for consistency with Python module system semantics.

---

## Open Questions

1. **Dry-run implementation location: CLI-only vs. server-mediated**
   - What we know: Phase 12 hardcoded FILE_TYPE_PRESETS in CLI to avoid cross-package deps
   - What's unclear: Should `--dry-run` be a pure CLI operation (requires duplicating ContentInjector logic) or a `?dry_run=true` query param on `POST /index/`?
   - Recommendation: Server-mediated (`?dry_run=true`) is cleaner and avoids code duplication. The server can load the script, apply to 5 sample chunks from the folder, and return a report without enqueueing a job. This requires the script path to be accessible from the server process (same machine — valid for local dev).

2. **API design: Extend `index` endpoint vs. new `inject` endpoint**
   - What we know: INJECT-01 says `agent-brain inject --script enrich.py /path` — implies a new `inject` CLI command
   - What's unclear: Should injection be a separate API endpoint or additional params on `POST /index/`?
   - Recommendation: Add `injector_script` and `folder_metadata_file` as optional fields to `IndexRequest` and the existing `POST /index/` endpoint. The `inject` CLI command is a new command that calls this same endpoint with those fields set. No new API endpoint needed.

3. **ChromaDB scalar validation: enforce at injection time or storage time**
   - What we know: ChromaDB rejects non-scalar metadata values
   - What's unclear: Whether to validate at `ContentInjector.apply()` or let storage layer surface the error
   - Recommendation: Validate at injection time with a warning + skip for non-scalar values. Fail fast with a clear error rather than a confusing ChromaDB exception later.

---

## Sources

### Primary (HIGH confidence)

- Codebase: `agent-brain-server/agent_brain_server/services/indexing_service.py` — pipeline structure, FolderManager injection pattern
- Codebase: `agent-brain-server/agent_brain_server/indexing/chunking.py` — ChunkMetadata.extra, to_dict() pattern
- Codebase: `agent-brain-server/agent_brain_server/models/index.py` — IndexRequest extension pattern
- Codebase: `agent-brain-server/agent_brain_server/services/folder_manager.py` — optional service injection pattern
- Codebase: `agent-brain-server/agent_brain_server/job_queue/job_worker.py` — JobRecord-to-IndexRequest mapping
- Python 3.10 stdlib: `importlib.util.spec_from_file_location` / `exec_module` — dynamic module loading
- Codebase: `agent-brain-server/agent_brain_server/storage/protocol.py` — Protocol usage pattern

### Secondary (MEDIUM confidence)

- Codebase: `.planning/research/PITFALLS.md` — ChromaDB delete empty list bug, already-known pitfalls

### Tertiary (LOW confidence)

- None: all claims verified against codebase or stdlib.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all stdlib, no new dependencies
- Architecture: HIGH — verified injection point, metadata extension point, and service injection pattern directly in codebase
- Pitfalls: HIGH — ChromaDB scalar constraint is documented behavior; other pitfalls verified by reading the code
- Dry-run design: MEDIUM — design decision with two valid approaches; recommendation based on Phase 12 precedent

**Research date:** 2026-03-05
**Valid until:** 2026-04-05 (stable domain, no fast-moving dependencies)
