---
name: agent-brain-vector
description: Search using semantic vector similarity for concepts
parameters:
  - name: query
    description: The conceptual search query
    required: true
  - name: top-k
    description: Number of results to return (1-20)
    required: false
    default: 5
  - name: threshold
    description: Minimum similarity score (0.0-1.0)
    required: false
    default: 0.3
skills:
  - using-agent-brain
---

# Agent Brain Vector Search

## Purpose

Performs semantic vector similarity search using embeddings. This mode understands meaning and concepts, finding relevant content even when exact terms don't match.

Vector search is ideal for:
- Conceptual questions ("how does X work")
- Natural language queries
- Finding related content
- Questions about purpose or design
- When exact terms are unknown

## Usage

```
/agent-brain-vector <query> [--top-k <n>] [--threshold <t>]
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| query | Yes | - | The conceptual search query |
| --top-k | No | 5 | Number of results (1-20) |
| --threshold | No | 0.3 | Minimum similarity (0.0-1.0) |

### When to Use Vector vs Other Modes

| Use Vector | Use BM25 Instead |
|------------|------------------|
| "how does authentication work" | "AuthenticationError" |
| "best practices for caching" | "LRUCache" |
| "explain the deployment process" | "deploy.yml" |
| "security considerations" | "CVE-2024-1234" |
| "similar to user validation" | "validate_user" |

## Execution

### Pre-flight Check

```bash
# Verify server is running
agent-brain status
```

If not running:
```bash
agent-brain start --daemon
```

### Search Command

```bash
agent-brain query "<query>" --mode vector --top-k <k> --threshold <t>
```

### Examples

```bash
# Conceptual question
agent-brain query "how does the caching system work" --mode vector

# Natural language
agent-brain query "best practices for handling errors" --mode vector

# Find related content
agent-brain query "similar to user authentication flow" --mode vector

# Lower threshold for more results
agent-brain query "security considerations" --mode vector --threshold 0.2

# More results
agent-brain query "explain the API design" --mode vector --top-k 10
```

## Output

### Result Format

For each result, present:

1. **Source**: File path or document name
2. **Score**: Semantic similarity score (0-1, higher is better)
3. **Content**: Relevant excerpt from the document

### Example Output

```
## Vector Search Results for "how does caching work"

### 1. docs/architecture/caching.md (Score: 0.92)
## Caching Architecture

The system implements a multi-tier caching strategy:

1. **L1 Cache (In-Memory LRU)**: Fast access for frequently used data
2. **L2 Cache (Redis)**: Distributed cache for cross-instance sharing
3. **L3 Cache (CDN)**: Edge caching for static assets

Cache invalidation uses a write-through strategy...

### 2. docs/performance/optimization.md (Score: 0.78)
## Caching for Performance

Proper cache configuration can improve response times by 10-100x.

**Configuration options:**
- TTL by resource type
- Cache warming strategies
- Invalidation webhooks

### 3. src/cache/redis_client.py (Score: 0.71)
class RedisCache:
    """
    Redis-based distributed cache implementation.

    Provides connection pooling, automatic reconnection,
    and configurable TTL per key prefix.
    """

---
Found 3 results above threshold 0.3
Search mode: vector (semantic)
Response time: 1247ms
```

### Citation Format

When referencing results in responses:
- "The caching architecture is documented in `docs/architecture/caching.md`..."
- "According to `docs/performance/optimization.md`..."

## Error Handling

### Server Not Running

```
Error: Could not connect to Agent Brain server
```

**Resolution:**
```bash
agent-brain start --daemon
```

### No Results Found

```
No results found above threshold 0.3
```

**Resolution:**
- Try lowering threshold: `--threshold 0.1`
- Rephrase the query
- Use hybrid mode for mixed queries: `--mode hybrid`
- Verify documents are indexed: `agent-brain status`

### API Key Missing

```
Error: OPENAI_API_KEY not set
```

**Resolution:**
```bash
export OPENAI_API_KEY="sk-proj-..."

# Or use local embeddings:
export EMBEDDING_PROVIDER=ollama
export EMBEDDING_MODEL=nomic-embed-text
```

### Embedding Provider Error

```
Error: Failed to generate embedding
```

**Resolution:**
- Check API key is valid
- For Ollama: ensure model is pulled and server is running
- Verify embedding provider configuration: `agent-brain verify`

### Index Empty

```
Warning: No documents indexed
```

**Resolution:**
```bash
agent-brain index /path/to/docs
```

## Performance Notes

| Metric | Typical Value |
|--------|---------------|
| Latency | 800-1500ms |
| API calls | 1 embedding call per query |
| Best for | Conceptual queries, natural language |

### Comparison with Other Modes

| Aspect | Vector | BM25 | Hybrid |
|--------|--------|------|--------|
| Speed | Slow | Fast | Medium |
| Exact terms | Poor | Excellent | Good |
| Concepts | Excellent | Poor | Good |
| API cost | Per query | Free | Per query |

### Embedding Quality Factors

Vector search quality depends on:
1. **Embedding model**: text-embedding-3-large > small > ada-002
2. **Document quality**: Well-written docs match better
3. **Query phrasing**: Natural language works best
4. **Threshold setting**: Lower for more recall, higher for precision

## How Vector Search Works

1. **Query embedding**: Your query is converted to a vector (e.g., 3072 dimensions for OpenAI large)
2. **Similarity calculation**: Cosine similarity computed against all indexed document vectors
3. **Ranking**: Documents sorted by similarity score
4. **Filtering**: Results below threshold are excluded

```
similarity(q, d) = dot(q, d) / (||q|| * ||d||)
```

## Related Commands

- `/agent-brain-bm25` - Pure keyword search
- `/agent-brain-hybrid` - Combined BM25 + semantic
- `/agent-brain-semantic` - Alias for vector search
- `/agent-brain-multi` - Multi-mode fusion search
