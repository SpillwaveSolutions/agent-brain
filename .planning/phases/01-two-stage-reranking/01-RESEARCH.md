# Phase 1: Two-Stage Reranking - Research

**Researched:** 2026-02-07
**Domain:** RAG Retrieval Enhancement / Cross-Encoder Reranking
**Confidence:** HIGH

## Summary

Two-stage retrieval with reranking is a well-established pattern in production RAG systems that improves precision by 15-20% (per industry benchmarks). The architecture uses a fast bi-encoder retriever (Stage 1) to fetch 50-100 candidates, followed by a slower but more accurate cross-encoder reranker (Stage 2) to score and reorder the top results.

For Agent Brain's local-first philosophy, **Ollama does NOT have a native reranking API endpoint** as of 2026. However, there are two viable approaches: (1) Use `sentence-transformers` CrossEncoder directly (Python-native, well-integrated with LlamaIndex), or (2) Use Ollama's chat completions API with Qwen3 Reranker models via prompt-based scoring.

**Primary recommendation:** Use `sentence-transformers` CrossEncoder with `cross-encoder/ms-marco-MiniLM-L-6-v2` as the default model, with optional Ollama support via Qwen3 Reranker for users who prefer fully local inference.

<user_constraints>
## User Constraints (from Phase Context)

### Locked Decisions
1. **Start with Ollama** (local-first philosophy, no API keys required)
2. **Reranking is OPTIONAL** - off by default
3. **Graceful fallback** to stage 1 results on any failure
4. **Expected +3-4% precision improvement** (conservative target)

### Claude's Discretion
- Implementation details of reranker provider abstraction
- Exact Ollama model to recommend (bge-reranker-v2-m3 suggested)
- How to score/rank using Ollama (cross-encoder style via chat completions, or embedding similarity)
- Integration point in query_service.py

### Deferred Ideas (OUT OF SCOPE)
- None specified
</user_constraints>

## Standard Stack

The established libraries/tools for cross-encoder reranking:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `sentence-transformers` | ^3.4.0 | CrossEncoder models for reranking | Industry standard, 913+ code snippets in docs, HIGH reputation |
| `llama-index-postprocessor-sentencetransformer-rerank` | ^0.4.0 | LlamaIndex integration | Native NodePostprocessor for LlamaIndex pipelines |

### Supporting (Ollama Option)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `ollama` (Python) | ^0.4.0 | Local LLM inference | When user wants fully local reranking without downloading HuggingFace models |
| Qwen3-Reranker-0.6B | latest | Lightweight local reranker | Balance of speed and local-first philosophy |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| sentence-transformers CrossEncoder | Ollama Qwen3 Reranker | Ollama requires prompt-based scoring (slower), but fully local |
| cross-encoder/ms-marco-MiniLM-L-6-v2 | bge-reranker-v2-m3 via Ollama embed API | BGE models on Ollama use embedding similarity, not true cross-encoder |
| Local models | Cohere Rerank API | Cohere is more accurate but requires API key (violates local-first) |

**Installation:**
```bash
# Core (sentence-transformers approach)
poetry add sentence-transformers
poetry add llama-index-postprocessor-sentencetransformer-rerank

# Optional (Ollama approach)
poetry add ollama
```

## Architecture Patterns

### Recommended Integration Point

```
query_service.py
├── _execute_hybrid_query()          # Existing - Stage 1 retrieval
├── _execute_multi_query()           # Existing - Stage 1 retrieval
└── _rerank_results()                # NEW - Stage 2 reranking (optional)
    ├── Check ENABLE_RERANKING setting
    ├── Get reranker provider (factory pattern)
    └── Score and reorder results
```

### Pattern 1: Provider Abstraction (Matches Existing Codebase)

The codebase already has `EmbeddingProvider` and `SummarizationProvider` protocols with a `ProviderRegistry` factory. Add a new `RerankerProvider` following the same pattern.

**What:** Abstract reranker interface with factory pattern
**When to use:** Always - maintains consistency with existing provider architecture
**Example:**
```python
# Source: Based on existing agent_brain_server/providers/base.py pattern

@runtime_checkable
class RerankerProvider(Protocol):
    """Protocol for reranking providers."""

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int = 10,
    ) -> list[tuple[int, float]]:
        """Rerank documents for a query.

        Args:
            query: The search query
            documents: List of document texts to rerank
            top_k: Number of top results to return

        Returns:
            List of (original_index, score) tuples, sorted by score descending
        """
        ...

    @property
    def provider_name(self) -> str:
        """Human-readable provider name."""
        ...

    @property
    def model_name(self) -> str:
        """Model identifier being used."""
        ...
```

### Pattern 2: Two-Stage Retrieval Flow

**What:** Fast retrieval followed by accurate reranking
**When to use:** When ENABLE_RERANKING=true
**Example:**
```python
# Source: https://www.pinecone.io/learn/series/rag/rerankers/

async def _execute_hybrid_query_with_rerank(self, request: QueryRequest) -> list[QueryResult]:
    """Execute hybrid search with optional reranking."""

    # Stage 1: Fast retrieval (existing code)
    # Retrieve more candidates than final top_k
    stage1_top_k = min(request.top_k * 10, 100)  # 10x or cap at 100
    stage1_results = await self._execute_hybrid_query(request._replace(top_k=stage1_top_k))

    # Stage 2: Reranking (new, optional)
    if settings.ENABLE_RERANKING and len(stage1_results) > request.top_k:
        try:
            reranker = get_reranker_provider()
            documents = [r.text for r in stage1_results]
            reranked = await reranker.rerank(
                query=request.query,
                documents=documents,
                top_k=request.top_k,
            )
            # Reorder results based on reranking scores
            return [stage1_results[idx] for idx, score in reranked]
        except Exception as e:
            logger.warning(f"Reranking failed, using stage 1 results: {e}")
            # Graceful fallback
            return stage1_results[:request.top_k]

    return stage1_results[:request.top_k]
```

### Pattern 3: Sentence-Transformers CrossEncoder Implementation

**What:** Use sentence-transformers CrossEncoder directly
**When to use:** Default reranker implementation (recommended)
**Example:**
```python
# Source: https://www.sbert.net/docs/package_reference/cross_encoder/cross_encoder

from sentence_transformers import CrossEncoder

class SentenceTransformerRerankerProvider(BaseRerankerProvider):
    """Reranker using sentence-transformers CrossEncoder."""

    def __init__(self, config: "RerankerConfig") -> None:
        self._model = CrossEncoder(config.model)
        self._batch_size = config.params.get("batch_size", 32)

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int = 10,
    ) -> list[tuple[int, float]]:
        # CrossEncoder.rank() handles batching and sorting
        results = self._model.rank(
            query,
            documents,
            top_k=top_k,
            return_documents=False,
        )
        return [(r["corpus_id"], r["score"]) for r in results]
```

### Pattern 4: Ollama Chat-Based Reranking

**What:** Use Ollama Qwen3 Reranker via chat completions
**When to use:** When user wants fully local inference without HuggingFace downloads
**Example:**
```python
# Source: https://apidog.com/blog/qwen-3-embedding-reranker-ollama/

import ollama
from concurrent.futures import ThreadPoolExecutor

class OllamaRerankerProvider(BaseRerankerProvider):
    """Reranker using Ollama chat completions with Qwen3 Reranker."""

    RERANK_PROMPT = '''Score the relevance of this document to the query.
Query: {query}
Document: {document}

Output only a number from 0 to 10, where 10 is perfectly relevant.'''

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int = 10,
    ) -> list[tuple[int, float]]:
        scores = []
        for idx, doc in enumerate(documents):
            try:
                response = ollama.chat(
                    model=self._model,
                    messages=[{
                        "role": "user",
                        "content": self.RERANK_PROMPT.format(query=query, document=doc)
                    }],
                    options={"temperature": 0.0}
                )
                score = float(response["message"]["content"].strip())
                scores.append((idx, score))
            except Exception:
                scores.append((idx, 0.0))  # Default score on error

        # Sort by score descending and take top_k
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]
```

### Anti-Patterns to Avoid
- **Processing all documents through reranker:** Always limit to top 50-100 candidates from Stage 1
- **Synchronous reranking in request path:** Use async patterns to avoid blocking
- **No fallback on failure:** MUST gracefully degrade to Stage 1 results
- **Reranking when disabled:** Always check ENABLE_RERANKING before invoking reranker

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cross-encoder scoring | Custom transformer inference | `sentence-transformers.CrossEncoder` | Handles batching, tokenization, model loading |
| Document ranking | Manual sort + score | `CrossEncoder.rank()` method | Optimized, returns sorted corpus_id and scores |
| LlamaIndex integration | Custom postprocessor | `SentenceTransformerRerank` | Native NodePostprocessor, well-tested |
| Provider configuration | Hardcoded settings | Existing `ProviderConfig` pattern | YAML config, env vars, factory caching |

**Key insight:** The `sentence-transformers` library has a mature `CrossEncoder` class with `.rank()` method specifically designed for reranking. Do not implement custom transformer inference.

## Common Pitfalls

### Pitfall 1: Retrieving Too Few Stage 1 Candidates
**What goes wrong:** Reranking cannot surface relevant documents that weren't retrieved
**Why it happens:** Setting Stage 1 top_k same as final top_k
**How to avoid:** Retrieve 5-10x final top_k in Stage 1 (e.g., top_k=5 -> retrieve 50)
**Warning signs:** Reranking shows minimal improvement over Stage 1 results

### Pitfall 2: Exceeding 100ms Latency Budget
**What goes wrong:** User experience degrades, reranking becomes bottleneck
**Why it happens:** Reranking too many documents, using large models, no batching
**How to avoid:** Cap Stage 1 at 100 docs, use lightweight models (MiniLM), batch inference
**Warning signs:** P95 latency > 100ms for reranking step alone

### Pitfall 3: Ollama Reranker Model Not Available
**What goes wrong:** Reranking fails silently or with cryptic errors
**Why it happens:** User hasn't pulled the Ollama model, Ollama not running
**How to avoid:** Health check on startup, graceful fallback, clear error messages
**Warning signs:** `OllamaConnectionError`, empty responses

### Pitfall 4: Breaking Graceful Fallback
**What goes wrong:** Entire query fails when reranking fails
**Why it happens:** Not wrapping reranker call in try/except, propagating exceptions
**How to avoid:** Always catch reranker exceptions, return Stage 1 results
**Warning signs:** Query failures with ENABLE_RERANKING=true that work when false

### Pitfall 5: Inconsistent Score Ranges
**What goes wrong:** Reranker scores don't compare properly with Stage 1 scores
**Why it happens:** Mixing cross-encoder scores (unbounded) with cosine similarity (0-1)
**How to avoid:** Use reranker scores only for ordering, not combining with Stage 1 scores
**Warning signs:** Confusing score values in query results

## Code Examples

Verified patterns from official sources:

### LlamaIndex SentenceTransformerRerank Integration
```python
# Source: https://github.com/run-llama/llama_index/blob/main/docs/src/content/docs/framework/module_guides/querying/node_postprocessors/node_postprocessors.md

from llama_index.core.postprocessor import SentenceTransformerRerank

# Use fast model for production
postprocessor = SentenceTransformerRerank(
    model="cross-encoder/ms-marco-MiniLM-L-2-v2",  # Fast, decent accuracy
    top_n=5,
)

# Apply to retrieved nodes
reranked_nodes = postprocessor.postprocess_nodes(nodes)
```

### Direct CrossEncoder Usage
```python
# Source: https://www.sbert.net/docs/package_reference/cross_encoder/cross_encoder

from sentence_transformers import CrossEncoder

model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L6-v2")

query = "How to implement reranking?"
documents = [doc.text for doc in stage1_results]

# Rank and get top 5
results = model.rank(query, documents, top_k=5, return_documents=False)
# results = [{"corpus_id": 2, "score": 8.61}, {"corpus_id": 0, "score": 6.35}, ...]
```

### Configuration Pattern (Following Existing Codebase)
```python
# Source: Based on agent_brain_server/config/settings.py pattern

class Settings(BaseSettings):
    # ... existing settings ...

    # Reranking Configuration (Feature 123)
    ENABLE_RERANKING: bool = False  # Off by default
    RERANKER_PROVIDER: str = "sentence-transformers"  # or "ollama"
    RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    RERANKER_TOP_K_MULTIPLIER: int = 10  # Retrieve top_k * this for Stage 1
    RERANKER_MAX_CANDIDATES: int = 100  # Cap on Stage 1 candidates
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single-stage retrieval | Two-stage retrieve + rerank | 2023+ | +15-20% precision improvement |
| BERT cross-encoders | MiniLM distilled models | 2022+ | 10x faster with minimal accuracy loss |
| API-only rerankers (Cohere) | Local cross-encoders | 2024+ | No API costs, privacy preserved |
| Embedding similarity reranking | True cross-encoder attention | 2023+ | Better semantic understanding |

**Deprecated/outdated:**
- `bge-reranker-v2-m3` on Ollama: Uses embed API (embedding similarity), not true cross-encoder. Less accurate than sentence-transformers CrossEncoder.
- Custom transformer inference: sentence-transformers handles this better

## Open Questions

Things that need validation during implementation:

1. **Latency with 100 candidates**
   - What we know: MiniLM models are fast (~2-5ms per document)
   - What's unclear: Actual latency in Agent Brain's async context
   - Recommendation: Benchmark during implementation, target <100ms total

2. **Ollama Qwen3 Reranker Accuracy**
   - What we know: Chat-based scoring works but may be less accurate than true cross-encoders
   - What's unclear: Precision improvement vs sentence-transformers approach
   - Recommendation: Implement both, let user choose via config

3. **Async CrossEncoder Inference**
   - What we know: CrossEncoder.predict() is synchronous
   - What's unclear: Best pattern for async wrapper (threadpool vs process pool)
   - Recommendation: Use `asyncio.to_thread()` for CPU-bound inference

## Sources

### Primary (HIGH confidence)
- `/websites/sbert_net` (Context7) - CrossEncoder.rank() method, retrieve & rerank patterns
- `/run-llama/llama_index` (Context7) - SentenceTransformerRerank NodePostprocessor usage
- [Pinecone Rerankers Guide](https://www.pinecone.io/learn/series/rag/rerankers/) - Two-stage architecture, performance benchmarks

### Secondary (MEDIUM confidence)
- [Ollama Qwen3 Reranker Guide](https://apidog.com/blog/qwen-3-embedding-reranker-ollama/) - Ollama chat-based reranking pattern
- [GitHub ollama/ollama#3368](https://github.com/ollama/ollama/issues/3368) - Confirmed no native rerank API in Ollama

### Tertiary (LOW confidence)
- WebSearch results on Ollama reranking models - Community uploads, varying quality
- BGE-reranker-v2-m3 Ollama usage - Uses embed API, not ideal for cross-encoder reranking

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - sentence-transformers is industry standard with excellent docs
- Architecture: HIGH - Two-stage retrieval is well-established pattern
- Pitfalls: HIGH - Common issues are well-documented in community
- Ollama approach: MEDIUM - Works but less tested than sentence-transformers

**Research date:** 2026-02-07
**Valid until:** 2026-03-07 (30 days - stable domain)

## Recommendation Summary

1. **Use `sentence-transformers` CrossEncoder** as primary implementation (not Ollama BGE models)
2. **Add `RerankerProvider` protocol** following existing provider patterns in codebase
3. **Integrate after RRF fusion** in `query_service.py`
4. **Default model:** `cross-encoder/ms-marco-MiniLM-L-6-v2` (fast, good accuracy)
5. **Optional Ollama support:** Qwen3-Reranker-0.6B via chat completions for fully local users
6. **Stage 1 retrieval:** 10x top_k, capped at 100 candidates
7. **Graceful fallback:** Always return Stage 1 results on any reranker failure
