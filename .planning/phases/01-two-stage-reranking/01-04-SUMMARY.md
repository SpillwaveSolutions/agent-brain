# 01-04 Summary: OllamaRerankerProvider Implementation

## Status: COMPLETE

## What Was Done

### Task 1: Implemented OllamaRerankerProvider

Created `/agent-brain-server/agent_brain_server/providers/reranker/ollama.py`:

- **OllamaRerankerProvider class** - Uses Ollama chat completions API for relevance scoring
- **Prompt-based scoring** - Uses a structured prompt that instructs the model to output a 0-10 score
- **Concurrent scoring with rate limiting** - Uses `asyncio.Semaphore` to limit concurrent requests (default 5)
- **Graceful error handling** - Returns 0.0 score on any failure (connection, HTTP, parsing)
- **Score parsing** - Regex-based extraction handles various model output formats
- **Document truncation** - Limits document length to 2000 chars to avoid context overflow
- **is_available()** - Checks Ollama connectivity via `/api/tags` endpoint
- **close()** method - Properly closes httpx AsyncClient
- **Provider registration** - Automatically registers with ProviderRegistry on import

Key implementation details:
```python
RERANK_PROMPT = (
    "You are a relevance scoring system. "
    "Score how relevant the document is to the query.\n\n"
    "Query: {query}\n\n"
    "Document: {document}\n\n"
    "Instructions:\n"
    "- Output ONLY a single number from 0 to 10\n"
    "- 10 = perfectly relevant, directly answers the query\n"
    "- 5 = somewhat relevant, related topic\n"
    "- 0 = completely irrelevant\n"
    "- Do not output any other text, just the number\n\n"
    "Score:"
)
```

### Task 2: Updated Package Exports

Updated `/agent-brain-server/agent_brain_server/providers/reranker/__init__.py`:
- Added export for `OllamaRerankerProvider`
- Import triggers automatic registration with ProviderRegistry

### Bonus Fix: SentenceTransformerRerankerProvider Type Error

Fixed a mypy type error in `sentence_transformers.py` line 119:
- Changed `r["corpus_id"]` to `int(r["corpus_id"])` for proper type inference

## Files Modified

1. **Created**: `agent-brain-server/agent_brain_server/providers/reranker/ollama.py`
   - OllamaRerankerProvider implementation (210 lines)

2. **Modified**: `agent-brain-server/agent_brain_server/providers/reranker/__init__.py`
   - Added OllamaRerankerProvider export

3. **Fixed**: `agent-brain-server/agent_brain_server/providers/reranker/sentence_transformers.py`
   - Type cast fix for corpus_id (mypy error)

## Verification Results

### All Quality Checks Pass
```
task before-push
- Format: OK
- Lint: OK
- Typecheck: OK
- Server tests: 383 passed
- CLI tests: 74 passed
```

### Registered Providers
Both reranker providers are now registered:
- `sentence-transformers` - CrossEncoder-based (fast, accurate)
- `ollama` - Chat completion-based (local, any model)

## Must-Haves Verification

| Requirement | Status |
|-------------|--------|
| OllamaRerankerProvider uses chat completions for scoring | DONE |
| Provider gracefully handles Ollama connection failures | DONE |
| Provider is registered with ProviderRegistry on import | DONE |

## Notes

- The Ollama provider is slower than SentenceTransformers but offers fully local inference without HuggingFace model downloads
- Recommended models: `llama3.2:1b`, `gemma2:2b`, or specialized reranker models if available
- Concurrent scoring uses semaphore rate limiting to prevent overwhelming Ollama
- Score parsing uses regex to handle various output formats (integer, decimal, with/without text)
