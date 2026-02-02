# Hybrid Search Guide

## Overview

Hybrid search combines the best of both vector semantic search and BM25 keyword search using Relative Score Fusion. It provides the most robust retrieval by leveraging both semantic understanding and exact term matching, then intelligently combining the results.

## When to Use Hybrid Search

**Choose hybrid search when:**
- You want the most comprehensive and accurate results
- The query combines both conceptual elements and specific technical terms
- You're unsure which search mode would work better
- You need high-quality results for critical applications
- The query involves both natural language and technical jargon

**Examples of hybrid queries:**
- `"how to implement OAuth2 authentication with JWT tokens"` - Combines concept + technical terms
- `"troubleshooting HTTP 500 errors in production"` - Error codes + troubleshooting concepts
- `"best practices for recursive text splitting algorithms"` - Methodology + specific algorithms
- `"configuring database connection pooling for high traffic"` - Configuration + technical terms

## How to Use Hybrid Search

### CLI Usage

```bash
# Basic hybrid search (default mode)
agent-brain query "implement authentication with error handling"

# With alpha weighting (70% vector, 30% BM25)
agent-brain query "oauth flow implementation" --alpha 0.7

# Show individual scores for debugging
agent-brain query "troubleshooting guide" --scores

# Custom settings for precision
agent-brain query "api documentation" --alpha 0.8 --threshold 0.6 --top-k 8
```

### API Usage

```bash
# POST /query endpoint (default hybrid)
curl -X POST http://localhost:8000/query/ \
  -H "Content-Type: application/json" \
  -d '{
    "query": "authentication implementation guide",
    "alpha": 0.6,
    "threshold": 0.5
  }'

# Explicit hybrid mode
curl -X POST http://localhost:8000/query/ \
  -H "Content-Type: application/json" \
  -d '{
    "query": "error handling patterns",
    "mode": "hybrid",
    "alpha": 0.7,
    "top_k": 10
  }'
```

## Hybrid Search Options

| Option | Default | Description | Use Case |
|--------|---------|-------------|----------|
| `--mode hybrid` | Default | Combines vector + BM25 | Best overall results |
| `--alpha F` | 0.5 | Weight balance (0.0=BM25, 1.0=vector) | Tune semantic vs keyword focus |
| `--threshold F` | 0.7 | Minimum combined score | Higher precision, fewer results |
| `--top-k N` | 5 | Maximum results | More comprehensive results |
| `--scores` | Optional | Show individual vector/BM25 scores | Debugging and transparency |

## Why Choose Hybrid Over Other Modes

**Hybrid Advantages:**
- 🎯 **Highest Quality**: Combines strengths of both approaches
- ⚖️ **Balanced Results**: Semantic understanding + exact matching
- 🎛️ **Tunable**: Alpha parameter for optimization
- 📊 **Transparent**: Individual scores for debugging
- 🏆 **Recommended Default**: Best overall performance for most queries

**When Hybrid is better than Vector-only:**
- Queries contain specific technical terms that vector search might miss
- Need guaranteed exact matches alongside semantic understanding
- Working with mixed technical/conceptual content

**When Hybrid is better than BM25-only:**
- Queries involve natural language or conceptual elements
- Want to find related content beyond exact keyword matches
- Technical terms might vary or use synonyms

## Alpha Weighting System

The `alpha` parameter controls the balance between vector and BM25 search:

- **`alpha = 1.0`**: 100% vector search (pure semantic)
- **`alpha = 0.8`**: 80% vector, 20% BM25 (mostly semantic, some keyword boost)
- **`alpha = 0.5`**: 50% vector, 50% BM25 (balanced - **recommended default**)
- **`alpha = 0.3`**: 20% vector, 80% BM25 (mostly keyword, some semantic boost)
- **`alpha = 0.0`**: 100% BM25 search (pure keyword)

**Choosing Alpha Values:**
- **Technical documentation**: Try `alpha = 0.3-0.4` (favor BM25 for exact terms)
- **Conceptual guides**: Try `alpha = 0.7-0.8` (favor vector for meaning)
- **Mixed content**: Keep `alpha = 0.5` (balanced approach)
- **API references**: Try `alpha = 0.4` (technical terms + some context)
- **Tutorials**: Try `alpha = 0.6` (explanations + specific code)

## Fusion Algorithm Details

Hybrid search uses **Relative Score Fusion**:

1. **Execute Both Searches**: Run vector and BM25 searches in parallel
2. **Normalize Scores**: Convert both score ranges to 0.0-1.0 scale
3. **Weighted Combination**: `final_score = alpha × vector_score + (1-alpha) × bm25_score`
4. **Re-rank Results**: Sort by combined scores
5. **Deduplication**: Remove duplicate results from overlapping matches

**Benefits**:
- Maintains ranking quality from both algorithms
- Allows fine-grained control via alpha parameter
- Provides best-of-both-worlds results
- Mathematically sound combination approach

## Example Queries and Results

### Example 1: Technical Implementation Query

**Query:** `agent-brain query "implement OAuth2 authentication with JWT tokens" --alpha 0.6 --scores`

**Response:**
```json
{
  "results": [
    {
      "text": "OAuth2 implementation guide: 1) Register application with OAuth provider, 2) Implement authorization code flow, 3) Handle token refresh, 4) Validate JWT tokens...",
      "source": "/docs/security/oauth-implementation.md",
      "score": 0.89,
      "vector_score": 0.85,
      "bm25_score": 0.93,
      "chunk_id": "chunk_123",
      "metadata": {
        "file_name": "oauth-implementation.md",
        "chunk_index": 0
      }
    },
    {
      "text": "JWT token structure: header.payload.signature - use HS256 for HMAC, RS256 for RSA signatures...",
      "source": "/docs/security/jwt-guide.md",
      "score": 0.82,
      "vector_score": 0.78,
      "bm25_score": 0.86,
      "chunk_id": "chunk_456",
      "metadata": {
        "file_name": "jwt-guide.md",
        "chunk_index": 1
      }
    }
  ],
  "query_time_ms": 1450.8,
  "total_results": 2
}
```

### Example 2: Troubleshooting Query

**Query:** `agent-brain query "fix HTTP 500 errors in production deployment"`

**Response:**
```json
{
  "results": [
    {
      "text": "HTTP 500 Internal Server Error typically indicates application crashes. Common causes: unhandled exceptions, database connection failures, resource exhaustion...",
      "source": "/docs/troubleshooting/http-500-errors.md",
      "score": 0.91,
      "vector_score": 0.88,
      "bm25_score": 0.94,
      "chunk_id": "chunk_789",
      "metadata": {
        "file_name": "http-500-errors.md",
        "chunk_index": 0
      }
    },
    {
      "text": "Production deployment checklist: 1) Environment variables set, 2) Database migrations run, 3) SSL certificates valid, 4) Monitoring configured...",
      "source": "/docs/deployment/production-checklist.md",
      "score": 0.79,
      "vector_score": 0.82,
      "bm25_score": 0.76,
      "chunk_id": "chunk_101",
      "metadata": {
        "file_name": "production-checklist.md",
        "chunk_index": 2
      }
    }
  ],
  "query_time_ms": 1320.3,
  "total_results": 2
}
```

## Performance Characteristics

- **Response Time**: 1000-1800ms (parallel vector + BM25 execution)
- **CPU Usage**: High (two search algorithms + fusion)
- **Memory Usage**: High (loads both vector and BM25 indexes)
- **API Costs**: Requires OpenAI API credits (for vector component)
- **Scalability**: Good (parallel execution, pre-computed indexes)

## Best Practices

1. **Start with defaults**: Use `alpha = 0.5` and `threshold = 0.7` initially
2. **Tune alpha for content type**: Adjust based on whether your docs are more technical or conceptual
3. **Use scores for debugging**: `--scores` flag helps understand result quality
4. **Combine with domain knowledge**: Know whether your docs favor technical terms or explanations

## Advanced Usage Patterns

### Technical Documentation Focus
```bash
# Favor BM25 for technical docs
agent-brain query "implement caching strategy" --alpha 0.3 --threshold 0.8
```

### Conceptual Documentation Focus
```bash
# Favor vector for conceptual docs
agent-brain query "understand microservices architecture" --alpha 0.8 --threshold 0.6
```

### Balanced General Queries
```bash
# Default balanced approach
agent-brain query "how to optimize database queries" --alpha 0.5 --top-k 10
```

## Common Issues

- **API key required**: Must have valid OpenAI API key for vector component
- **Slower than BM25**: Expected due to dual algorithm execution
- **Cost considerations**: Consumes OpenAI credits for each query
- **Alpha tuning needed**: May require experimentation for optimal results

## Integration Examples

### In Scripts
```bash
#!/bin/bash
# Comprehensive search with balanced weighting
agent-brain query "$1" --mode hybrid --alpha 0.5 --json | jq '.results[0]'
```

### With Other Tools
```bash
# Find comprehensive documentation
agent-brain query "complete $TOPIC guide" --mode hybrid --alpha 0.6 --json | jq -r '.results[].source'
```

### API Integration
```python
import requests

response = requests.post('http://localhost:8000/query/', json={
    'query': 'implement authentication with error handling',
    'mode': 'hybrid',
    'alpha': 0.6,  # 60% semantic, 40% keyword
    'threshold': 0.5,
    'top_k': 8
})
results = response.json()['results']
```

## Multi-Mode Fusion (Graph + Hybrid)

When GraphRAG is enabled, you can use `multi` mode to combine all four retrieval methods: Vector, BM25, Hybrid, and Graph. Multi-mode uses Reciprocal Rank Fusion (RRF) to merge results from all sources.

### How Multi-Mode Works

1. **Execute All Retrievers**: Run vector, BM25, and graph searches in parallel
2. **Compute Hybrid Score**: Combine vector + BM25 using alpha weighting
3. **Apply RRF**: Merge hybrid and graph results using Reciprocal Rank Fusion
4. **Re-rank Results**: Sort by combined RRF scores
5. **Deduplicate**: Remove duplicate chunks from overlapping matches

### RRF Formula

```
RRF_score = sum(1 / (k + rank_i)) for each retriever i
```

Where `k` is a smoothing constant (default: 60) and `rank_i` is the result's rank in retriever `i`.

### When to Use Multi-Mode

**Choose multi mode when:**
- Need the most comprehensive results possible
- Want both content relevance AND relationship context
- Investigating complex code paths
- Uncertain which single mode would work best
- Building knowledge exploration workflows

### Multi-Mode Usage

```bash
# CLI: Multi-mode with relationship details
agent-brain query "complete authentication implementation" --mode multi --include-relationships

# CLI: Multi-mode with custom settings
agent-brain query "payment processing flow" --mode multi --top-k 10 --traversal-depth 3
```

```python
# API: Multi-mode request
response = requests.post('http://localhost:8000/query/', json={
    'query': 'authentication flow with all dependencies',
    'mode': 'multi',
    'alpha': 0.6,
    'traversal_depth': 2,
    'include_relationships': True,
    'top_k': 10
})
```

### Multi-Mode Performance

- **Response Time**: 1500-2500ms (all retrievers + fusion)
- **Memory Usage**: Highest (loads all indexes)
- **Best Results**: Combines strengths of all retrieval methods

See [Graph Search Guide](graph-search-guide.md) for detailed GraphRAG documentation.

---

## Comparison Matrix

| Aspect | BM25 | Vector | Hybrid | Graph | Multi |
|--------|------|--------|--------|-------|-------|
| **Accuracy** | High (exact) | High (semantic) | Highest (both) | High (relationships) | Comprehensive |
| **Speed** | Fastest | Slow | Slow-Medium | Medium | Slowest |
| **API Required** | No | Yes | Yes | Yes | Yes |
| **Best For** | Technical terms | Concepts | General use | Dependencies | Everything |
| **Tuning** | Threshold only | Threshold only | Alpha + threshold | Depth + threshold | All options |
| **Transparency** | Single score | Single score | Dual scores | Graph score | All scores |
| **Cost** | Free | API credits | API credits | API credits | API credits |
| **Relationships** | No | No | No | Yes | Yes |