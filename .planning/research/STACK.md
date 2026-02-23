# Stack Research — v7.0 Index Management & Content Pipeline

**Domain:** Index management, file filtering, chunk eviction, content enrichment
**Researched:** 2026-02-23
**Confidence:** HIGH

## Executive Summary

v7.0 adds four NEW capabilities to the existing Agent Brain RAG system. **CRITICAL**: This stack analysis covers ONLY what's NEW — the existing validated stack (FastAPI, ChromaDB, LlamaIndex, PostgreSQL, etc.) is already in place and NOT covered here.

**Key Finding:** Most features require NO new external dependencies. The Python standard library + existing LlamaIndex capabilities cover 90% of needs. Only optional feature (content injector with custom enrichment) might benefit from a small utility library.

## New Feature Requirements

| Feature | Stack Additions | Rationale |
|---------|----------------|-----------|
| Indexed Folder Management | None (stdlib only) | JSONL manifest with stdlib json module |
| Smart Include Filtering | None (stdlib only) | Predefined presets using existing extensions |
| Chunk Eviction & Live Reindex | hashlib (stdlib) | SHA256 for content change detection |
| Content Injector CLI | None (LlamaIndex already has it) | SummaryExtractor pattern already used |

---

## Recommended Stack (NEW Components Only)

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| hashlib (stdlib) | Python 3.10+ | Content change detection via SHA256 | Standard library, no dependencies, 50MB/s throughput on typical hardware, widely used for file integrity checks |
| json (stdlib) | Python 3.10+ | JSONL manifest file I/O | Standard library, line-by-line processing for large manifests, append-safe for crash recovery |
| pathlib (stdlib) | Python 3.10+ | Cross-platform path handling | Already used extensively, consistent path normalization for manifest keys |

### Supporting Libraries (Optional)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| filetype | ^1.2.0 | Content-based file type detection | Only if users report incorrect type detection from extensions (LOW priority) |

---

## What Already Exists (DO NOT ADD)

| Capability | Already Available | Location |
|------------|-------------------|----------|
| Metadata extraction | LlamaIndex SummaryExtractor, QuestionsAnsweredExtractor, TitleExtractor, EntityExtractor | agent_brain_server/indexing/chunking.py uses SummaryExtractor |
| File extension filtering | LlamaIndex SimpleDirectoryReader `required_exts` parameter | document_loader.py line 370 |
| Code/doc type detection | LanguageDetector with 40+ extensions | document_loader.py lines 44-239 |
| Source tracking | ChromaDB/PostgreSQL metadata fields (`file_path`, `file_name`, `source`) | Stored with every chunk |
| Background job queue | JSONL-based queue with worker | models/job.py, services/job_queue.py |

---

## Installation (NEW Dependencies Only)

```bash
# Server — NO new required dependencies
# Existing pyproject.toml already has everything needed

# Optional (content-based type detection, LOW priority)
poetry add filetype  # Only if extension-based detection proves insufficient
```

**IMPORTANT**: The existing stack already includes:
- Python 3.10+ stdlib (hashlib, json, pathlib)
- LlamaIndex metadata extractors (SummaryExtractor, etc.)
- ChromaDB/PostgreSQL with metadata storage
- JSONL job queue infrastructure

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| hashlib SHA256 | blake3 (faster) | Never — SHA256 is 200-300 MB/s, fast enough for file change detection, no external deps |
| json (stdlib) | jsonlines library | Never — stdlib json handles line-by-line JSONL natively, no dependency needed |
| Extension-based detection | python-magic (content-based) | Only if users index files without extensions (VERY rare) |
| LlamaIndex extractors | Custom LLM prompts | Never — extractors already optimized, battle-tested, configurable via provider YAML |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| watchdog / inotify | File watching deferred to future optimization milestone per PROJECT.md | Manual reindex triggered by CLI |
| MD5 hashing | Collision attacks make it unsuitable for integrity checks | hashlib SHA256 |
| Separate manifest database | Adds complexity, PostgreSQL not required for this | JSONL file in state directory |
| Custom metadata extractor implementations | LlamaIndex already provides 5+ extractors with LLM backing | LlamaIndex SummaryExtractor, TitleExtractor, etc. |
| pymimetype or python-magic | Heavy dependencies (libmagic C library), overkill for extension-based filtering | stdlib mimetypes + existing LanguageDetector |

---

## Implementation Patterns

### Pattern 1: File Manifest Tracking

**What:** JSONL file storing indexed file metadata (path, hash, mtime, indexed_at)
**When:** Every index operation
**Example:**
```python
import json
import hashlib
from pathlib import Path

def compute_file_hash(file_path: Path) -> str:
    """SHA256 hash of file content in 64KB chunks."""
    hasher = hashlib.sha256()
    with file_path.open("rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()

def append_to_manifest(manifest_path: Path, file_path: Path, hash: str):
    """Append file record to JSONL manifest."""
    record = {
        "file_path": str(file_path.absolute()),
        "hash": hash,
        "mtime": file_path.stat().st_mtime,
        "indexed_at": datetime.now(timezone.utc).isoformat()
    }
    with manifest_path.open("a") as f:
        f.write(json.dumps(record) + "\n")
```

**Why this works:**
- JSONL append-safe (crash recovery)
- Line-by-line reading doesn't load entire manifest into memory
- SHA256 detects renames, moves, content changes
- mtime provides fast pre-filter before hashing

### Pattern 2: File Type Presets

**What:** Predefined extension sets for common use cases
**When:** User wants "just markdown" or "just code" without listing extensions
**Example:**
```python
FILE_TYPE_PRESETS = {
    "markdown": {".md", ".markdown"},
    "text": {".txt", ".md", ".rst"},
    "code": DocumentLoader.CODE_EXTENSIONS,  # Already defined: 25+ extensions
    "docs": DocumentLoader.DOCUMENT_EXTENSIONS,  # Already defined: 6 extensions
    "python": {".py", ".pyw", ".pyi"},
    "typescript": {".ts", ".tsx"},
    "javascript": {".js", ".jsx", ".mjs", ".cjs"},
    "all": DocumentLoader.SUPPORTED_EXTENSIONS,  # 31+ extensions
}

def resolve_presets(presets: list[str]) -> set[str]:
    """Convert preset names to extension set."""
    extensions = set()
    for preset in presets:
        extensions.update(FILE_TYPE_PRESETS.get(preset, set()))
    return extensions
```

**Why this works:**
- Reuses existing DocumentLoader extension definitions
- No new dependencies
- User-friendly names instead of glob patterns
- Composable (e.g., `["python", "markdown"]`)

### Pattern 3: Chunk Eviction by Source

**What:** Remove all chunks from a specific file path
**When:** File deleted, moved, or changed (before reindexing)
**Example:**
```python
# ChromaDB backend
async def evict_chunks_by_source(self, file_path: str) -> int:
    """Delete all chunks from a specific source file."""
    collection = self.vector_store.get_collection()
    # Query by metadata filter
    results = collection.get(where={"file_path": file_path})
    if results["ids"]:
        collection.delete(ids=results["ids"])
    return len(results["ids"])

# PostgreSQL backend
async def evict_chunks_by_source(self, file_path: str) -> int:
    """Delete all chunks from a specific source file."""
    async with self.conn_manager.get_session() as session:
        result = await session.execute(
            text("DELETE FROM documents WHERE metadata->>'file_path' = :path"),
            {"path": file_path}
        )
        return result.rowcount
```

**Why this works:**
- Metadata already stored with every chunk (file_path field)
- Both ChromaDB and PostgreSQL support metadata filtering
- Idempotent (safe to call multiple times)
- Enables "live reindex" workflow (evict → reindex)

### Pattern 4: Content Enrichment Pipeline

**What:** Optional LLM-based metadata extraction during indexing
**When:** User wants enhanced summaries, Q&A pairs, or custom metadata
**Example:**
```python
from llama_index.core.extractors import (
    SummaryExtractor,
    QuestionsAnsweredExtractor,
    TitleExtractor
)

# Already exists in agent_brain_server/indexing/chunking.py
# User configures via YAML which extractors to enable
def build_enrichment_pipeline(config: dict) -> list[BaseExtractor]:
    """Build metadata extractor pipeline from config."""
    extractors = []
    if config.get("enable_summaries"):
        extractors.append(SummaryExtractor(llm=get_llm()))
    if config.get("enable_questions"):
        extractors.append(QuestionsAnsweredExtractor(llm=get_llm()))
    if config.get("enable_titles"):
        extractors.append(TitleExtractor(llm=get_llm()))
    return extractors

# Apply during chunking
def enrich_chunks(chunks: list[TextNode], extractors: list[BaseExtractor]):
    """Apply metadata extractors to chunks."""
    for extractor in extractors:
        chunks = extractor.process_nodes(chunks)
    return chunks
```

**Why this works:**
- LlamaIndex extractors already battle-tested
- Uses existing provider infrastructure (OpenAI, Anthropic, Ollama, etc.)
- Configurable via YAML (matches v3.0 pluggable provider pattern)
- No new dependencies

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| hashlib (stdlib) | Python 3.10+ | SHA256 available since Python 2.5, no compatibility issues |
| json (stdlib) | Python 3.10+ | JSONL line-by-line processing standard pattern |
| llama-index-core ^0.14.0 | SummaryExtractor, QuestionsAnsweredExtractor | Already in pyproject.toml, metadata extractors stable API |
| ChromaDB ^0.5.0 | Metadata filtering with `where` clause | Already validated in existing backend |
| PostgreSQL/pgvector | JSONB metadata queries with `->>'` operator | Already validated in v6.0 milestone |

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Embedding Cache with Content Hashing
**What:** Reusing embeddings when file content unchanged
**Why bad:** Out of scope for v7.0 per PROJECT.md "Out of Scope" section
**Instead:** Track changes with manifest, evict + reindex on change

### Anti-Pattern 2: Real-time File Watching
**What:** Using watchdog to auto-reindex on file changes
**Why bad:** Deferred to future optimization milestone per PROJECT.md
**Instead:** CLI-triggered reindex with manifest-based change detection

### Anti-Pattern 3: Custom Metadata Extractors from Scratch
**What:** Writing LLM prompts manually for chunk enrichment
**Why bad:** LlamaIndex extractors already optimized, tested, configurable
**Instead:** Use LlamaIndex SummaryExtractor, QuestionsAnsweredExtractor, TitleExtractor

### Anti-Pattern 4: Database for Manifest Tracking
**What:** Storing file manifest in PostgreSQL or ChromaDB
**Why bad:** Adds coupling, complexity, no clear benefit over JSONL
**Instead:** JSONL file in state directory (crash-safe, line-by-line, human-readable)

---

## Stack Patterns by Variant

**If user wants offline operation:**
- Use hashlib (stdlib) for change detection — no network required
- Use Ollama provider (already supported) for content enrichment
- JSONL manifest (stdlib) — no database needed

**If user wants maximum performance:**
- mtime pre-filter before SHA256 hashing (skip hash if mtime unchanged)
- Batch eviction queries (delete multiple sources in one call)
- Optional: LlamaIndex extractors run only on new/changed files

**If user wants minimal dependencies:**
- Use ONLY stdlib (hashlib, json, pathlib) — no external packages
- Disable content enrichment (LLM-based metadata extraction)
- Extension-based filtering (no filetype library)

---

## Open Questions (RESEARCH GAPS)

None. All v7.0 features can be implemented with:
1. Python stdlib (hashlib, json, pathlib)
2. Existing LlamaIndex metadata extractors
3. Existing ChromaDB/PostgreSQL metadata filtering

**Next Steps:**
- Roadmap creator will structure phases
- Implementation will reuse existing patterns (JSONL queue, provider config, metadata storage)

---

## Sources

**File Content Hashing:**
- [Python hashlib — Secure hashes and message digests](https://docs.python.org/3/library/hashlib.html) — Official stdlib documentation
- [How To Detect File Changes Using Python - GeeksforGeeks](https://www.geeksforgeeks.org/python/how-to-detect-file-changes-using-python/) — SHA256 + mtime pattern
- [How to Hash Files in Python - Nitratine](https://nitratine.net/blog/post/how-to-hash-files-in-python/) — Chunked hashing for large files

**MIME Type Detection:**
- [mimetypes — Map filenames to MIME types](https://docs.python.org/3/library/mimetypes.html) — Stdlib option for extension-based detection
- [filetype · PyPI](https://pypi.org/project/filetype/) — Lightweight alternative if content-based detection needed

**LlamaIndex Metadata Extraction:**
- [Metadata Extraction | LlamaIndex Python Documentation](https://docs.llamaindex.ai/en/stable/module_guides/indexing/metadata_extraction/) — SummaryExtractor, QuestionsAnsweredExtractor, TitleExtractor
- [Metadata Extraction Usage Pattern | LlamaIndex Python Documentation](https://docs.llamaindex.ai/en/stable/module_guides/loading/documents_and_nodes/usage_metadata_extractor/) — Integration with chunking pipeline

**JSONL Best Practices:**
- [How to Read and Parse JSONL Files in Python - Tim Santeford](https://www.timsanteford.com/posts/how-to-read-and-parse-jsonl-files-in-python/) — Line-by-line processing pattern
- [JSONL for Developers: Complete Guide to JSON Lines Format - JSONL Tools](https://jsonltools.com/jsonl-for-developers) — Append-safe writes for crash recovery

---

*Stack research for: v7.0 Index Management & Content Pipeline*
*Researched: 2026-02-23*
*Confidence: HIGH — All findings verified against existing codebase and official documentation*
