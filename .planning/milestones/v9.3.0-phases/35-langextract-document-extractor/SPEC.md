# Phase 35: LangExtract Document Extractor

## Goal

Add `LangExtractExtractor` for document-chunk graph extraction. Code chunks continue using
`CodeMetadataExtractor`. `LLMEntityExtractor` (Anthropic-only) becomes a legacy fallback.

---

## Routing Logic

```
source_type == "code"     → CodeMetadataExtractor (AST, no API key — unchanged)
source_type == "document" → LangExtractExtractor  (multi-provider: Anthropic/Claude,
                                                    OpenAI, Gemini, Ollama)
                            ↓ graceful degradation if langextract not installed → []
                            ↓ legacy fallback if GRAPH_USE_LLM_EXTRACTION=true → LLMEntityExtractor
```

---

## New Settings (settings.py)

| Setting | Default | Description |
|---------|---------|-------------|
| `GRAPH_DOC_EXTRACTOR` | `"langextract"` | `"langextract"` or `"none"` |
| `GRAPH_LANGEXTRACT_PROVIDER` | `""` | Override provider (default: `SUMMARIZATION_PROVIDER`) |
| `GRAPH_LANGEXTRACT_MODEL` | `""` | Override model (default: `SUMMARIZATION_MODEL`) |

---

## Provider Resolution (LangExtractExtractor)

Priority order:
1. `GRAPH_LANGEXTRACT_PROVIDER` (explicit override)
2. `SUMMARIZATION_PROVIDER` (reuse configured summarization provider)
3. `"ollama"` (safe default)

Model priority:
1. `GRAPH_LANGEXTRACT_MODEL` (explicit override)
2. `SUMMARIZATION_MODEL` (reuse configured summarization model)
3. `""` (langextract provider default)

---

## LangExtractExtractor Design

```python
class LangExtractExtractor:
    def __init__(self, provider, model, max_triplets): ...
    def extract_triplets(self, text, max_triplets, source_chunk_id) -> list[GraphTriple]: ...
    def _convert_relations(self, relations, source_chunk_id) -> list[GraphTriple]: ...
```

- `extract_triplets` uses lazy import (`try: from langextract import extract_relations`)
- Returns `[]` gracefully when langextract not installed
- Handles both dict-style and object-style relation returns from langextract
- Handles `head`/`tail` field names as aliases for `subject`/`object`

---

## GraphIndexManager Changes

Added `langextract_extractor` parameter. Updated `_extract_from_document`:

```python
# 1. code chunks → CodeMetadataExtractor (unchanged)
# 2. doc chunks → LangExtractExtractor (new, when GRAPH_DOC_EXTRACTOR=langextract)
# 3. legacy fallback → LLMEntityExtractor (when GRAPH_USE_LLM_EXTRACTION=true, non-code)
```

`LLMEntityExtractor` is **retained** in the codebase but no longer the default path for
documents. It remains active only when `GRAPH_USE_LLM_EXTRACTION=true` and
`GRAPH_DOC_EXTRACTOR != "langextract"`.

---

## Config Command Update

Step 7 (GraphRAG) now shows three extractor options:
1. AST / Code Metadata (recommended for code repos)
2. LLM Entity Extractor (legacy, Anthropic-only)
3. LangExtract (multi-provider, uses `SUMMARIZATION_PROVIDER`)

---

## Files Changed

| File | Change |
|------|--------|
| `agent_brain_server/config/settings.py` | Added `GRAPH_DOC_EXTRACTOR`, `GRAPH_LANGEXTRACT_PROVIDER`, `GRAPH_LANGEXTRACT_MODEL` |
| `agent_brain_server/indexing/graph_extractors.py` | Added `LangExtractExtractor`, `get_langextract_extractor`, updated `reset_extractors` |
| `agent_brain_server/indexing/graph_index.py` | Added `LangExtractExtractor` import and routing in `_extract_from_document` |
| `agent-brain-plugin/commands/agent-brain-config.md` | Step 7 + Step 9 updates |
| `tests/unit/test_graph_extractors.py` | Added `TestLangExtractExtractor` test class |

---

## Verification Checklist

- [x] `task before-push` passes (285 tests, 74% coverage)
- [x] `LangExtractExtractor` tests pass with mocked langextract
- [x] Graceful degradation: `langextract` not installed → returns `[]`
- [x] Routing: code chunks → `CodeMetadataExtractor`, doc chunks → `LangExtractExtractor`
- [x] `GRAPH_DOC_EXTRACTOR=none` → no LLM extraction for documents
- [x] Plugin deployed: `~/.claude/plugins/agent-brain/commands/agent-brain-config.md` updated
- [x] Phase 34 spec created at `.planning/phases/34-config-command-spec/SPEC.md`
