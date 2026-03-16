# Phase 25 Research: Setup Wizard Coverage Gaps

**Phase:** 25-setup-wizard-coverage-gaps-graphrag-opt-in-bm25-postgresql-awareness-search-mode-education
**Researched:** 2026-03-15
**Scope:** Analysis of coverage gaps in setup wizard + skill documentation

---

## Key Findings

### 1. GraphRAG + PostgreSQL Compatibility (CRITICAL FINDING)

**Status: GraphRAG is INCOMPATIBLE with PostgreSQL backend.**

Source: `agent-brain-server/agent_brain_server/services/query_service.py` lines 508-513:

```python
backend_type = get_effective_backend_type()
if backend_type != "chroma":
    raise ValueError(
        f"Graph queries (mode='graph') require ChromaDB backend. "
        f"Current backend: '{backend_type}'. "
        f"To use graph queries, set AGENT_BRAIN_STORAGE_BACKEND=chroma."
    )
```

And for `multi` mode (lines 620-631):
```python
if settings.ENABLE_GRAPH_INDEX and backend_type == "chroma":
    # use graph results
elif backend_type != "chroma":
    logger.info("Graph component skipped in multi-mode: graph queries require ChromaDB backend")
```

**Implications for wizard:**
- If user selects PostgreSQL backend AND wants GraphRAG, the wizard MUST warn them this is incompatible
- GraphRAG opt-in question (Step 5) already exists in setup wizard, but lacks the PostgreSQL warning
- The wizard should gate GraphRAG options: if PostgreSQL was selected, show only "No" option with explanation

### 2. BM25 vs PostgreSQL Full-Text Search

**Current behavior:** ChromaDB backend uses the LlamaIndex disk-based BM25 index (rank-bm25). PostgreSQL backend replaces BM25 with PostgreSQL `tsvector` full-text search.

Source: `agent-brain-server/agent_brain_server/storage/postgres/keyword_ops.py`:
- Uses `websearch_to_tsquery()` + `ts_rank()` on a weighted `tsvector` column
- Score normalized to 0-1 to match ChromaDB BM25 approach
- Language-configurable (default: english)

**What the wizard currently says:** Nothing about this difference.

**What the wizard should say when PostgreSQL is selected:**
> "PostgreSQL replaces the disk-based BM25 index with PostgreSQL's built-in full-text search (tsvector/websearch_to_tsquery). Keyword search (`--mode bm25`) still works identically from the user's perspective. No BM25 configuration needed."

**Additional PostgreSQL setting users may want to know about:**
- `storage.postgres.language` (default: "english") — tsvector search language
- Configurable in config.yaml under `storage.postgres.language`

### 3. Search Mode Education

**Current state:** Step 6 of wizard already asks about default query mode and shows the 5 modes. However, the education is minimal — no explanation of WHEN to use each mode.

**Current wizard Step 6 content:** Presents list of 5 modes (hybrid, semantic, bm25, graph, multi) with one-line descriptions.

**What's missing:**
- Practical guidance: what's the best starting mode?
- When to switch from hybrid to semantic/bm25/graph?
- Mode availability constraints (bm25 is "hybrid minus vector" not truly keyword-only)

**Mode reference from query_service.py and existing skill:**

| Mode | Description | Requires GraphRAG | Best For |
|------|-------------|------------------|---------|
| `hybrid` | Vector + BM25 via RRF (recommended) | No | Most searches |
| `semantic` | Pure vector similarity | No | Conceptual/fuzzy searches |
| `bm25` | Keyword-only via BM25/tsvector | No | Exact terms, fast |
| `graph` | Entity relationship traversal | Yes (ChromaDB only) | Code architecture, "what calls what" |
| `multi` | Vector + BM25 + graph via RRF | Yes (ChromaDB only) | Maximum recall |

**Note:** When PostgreSQL is backend, `bm25` mode uses PostgreSQL tsvector (not rank-bm25). The user experience is identical.

### 4. Cache Coverage (Embedding Cache + Query Cache)

**Current state in wizard:** Not mentioned at all.

**What exists in codebase:**
1. **Embedding cache** (Phase 16): Auto-enabled, aiosqlite two-layer LRU cache. Zero config needed. Reduces OpenAI API costs on reindex of unchanged files. Configurable: `EMBEDDING_CACHE_MAX_MEM_ENTRIES` (default: 1000) and `EMBEDDING_CACHE_MAX_DISK_MB` (default: 500).
2. **Query cache** (Phase 17): Auto-enabled, TTL-based cache for repeat queries. Configurable: `QUERY_CACHE_TTL` (default: 300s) and `QUERY_CACHE_MAX_SIZE` (default: 256). Graph/multi modes excluded from cache.

**What to mention in wizard (informational only, no config needed):**
> "Both embedding and query caches are auto-enabled. You pay nothing extra for reindexing unchanged files, and repeated queries return instantly. No configuration needed."

**Current SKILL.md coverage:** Embedding cache is documented in `configuring-agent-brain/SKILL.md` under "Embedding Cache Tuning". Query cache is NOT mentioned anywhere in the plugin/skill documentation.

### 5. Current Wizard Step Analysis

The wizard (`agent-brain-setup.md`) currently has these steps:

| Step | Action | Coverage Gap |
|------|--------|-------------|
| 1 | Check installation | None |
| 2 | Embedding provider | None |
| 3 | Summarization provider | None |
| 4 | Storage backend | Lacks BM25/tsvector info for PostgreSQL |
| 5 | GraphRAG opt-in | Lacks PostgreSQL incompatibility warning |
| 6 | Default query mode | Minimal mode education, no cache mention |
| 7 | Write config.yaml | None |
| 8 | Verify connectivity | None |
| 9 | Init project | None |
| 10 | PostgreSQL setup | None |
| 11 | Start server | None |
| 12 | Verify setup | None |

### 6. Wizard Tests Location

`agent-brain-plugin/tests/test_plugin_wizard_spec.py` — 11 regression tests covering wizard steps 2-7. Tests verify wizard structure (AskUserQuestion blocks, config keys, step count).

### 7. Files to Modify

**Plan 25-01 (wizard + tests):**
- `agent-brain-plugin/commands/agent-brain-setup.md` — add 3 coverage improvements
- `agent-brain-plugin/tests/test_plugin_wizard_spec.py` — add regression tests

**Plan 25-02 (skill + config docs):**
- `agent-brain-plugin/skills/configuring-agent-brain/SKILL.md` — add query cache section + clarify bm25/postgres
- `agent-brain-plugin/skills/configuring-agent-brain/references/configuration-guide.md` — add query cache config + postgres bm25 note

---

## Changes Summary

### agent-brain-setup.md (Step 4 — Storage Backend)
After the user selects PostgreSQL, add an informational note:
```
Note: PostgreSQL replaces the disk-based BM25 index with PostgreSQL full-text
search (tsvector). The --mode bm25 command still works identically. Language
can be configured via storage.postgres.language (default: "english").
```

### agent-brain-setup.md (Step 5 — GraphRAG)
Add conditional logic: If PostgreSQL backend was selected, present GraphRAG as:
```
GraphRAG requires ChromaDB backend. Since you selected PostgreSQL, GraphRAG
is not available. Continuing with graphrag.enabled: false.
```
If ChromaDB selected, keep existing 3-option prompt (No / Yes-Simple / Yes-Kuzu).

### agent-brain-setup.md (Step 6 — Query Mode)
Add cache mention at end of step output:
```
Note: Embedding and query caches are auto-enabled. Reindexing unchanged files
costs nothing (embedding cache). Repeated queries return instantly (query cache).
No configuration needed.
```

### configuring-agent-brain/SKILL.md
- Add query cache to "Embedding Cache Tuning" section (rename section to "Caching")
- Add note in PostgreSQL storage section about BM25 replacement by tsvector

### configuring-agent-brain/references/configuration-guide.md
- Add QUERY_CACHE_TTL and QUERY_CACHE_MAX_SIZE to environment variables table
- Add "Query Cache" subsection under GraphRAG/caching area
- Add note to PostgreSQL storage config about tsvector replacing BM25

---

## Dependency Analysis

- Plan 25-01 (wizard + tests): Independent — touches only plugin command file and test
- Plan 25-02 (skill + docs): Independent — touches only skill SKILL.md and reference guide
- Both plans are Wave 1 (no dependencies on each other)

---

## Test Strategy

For wizard changes (Plan 25-01), extend `test_plugin_wizard_spec.py`:
- Test Step 4 includes tsvector note when PostgreSQL selected
- Test Step 5 blocks GraphRAG when PostgreSQL selected
- Test Step 6 includes cache awareness text

These are structural tests (grep-based assertions on wizard markdown content).

---

## Out of Scope

- Implementing `query.default_mode` as a server config key (noted in existing wizard as "not yet supported" — implementing this would require server changes far beyond documentation)
- GraphRAG + PostgreSQL compatibility implementation (would require major refactor of graph storage layer)
- Reranking configuration (not currently surfaced by wizard — separate feature)
