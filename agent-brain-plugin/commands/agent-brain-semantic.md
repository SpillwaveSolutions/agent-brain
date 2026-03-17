---
name: agent-brain-semantic
description: Search using semantic vector similarity for conceptual queries
parameters:
  - name: query
    description: The conceptual search query
    required: true
  - name: top-k
    description: Number of results (1-20)
    required: false
    default: 5
  - name: threshold
    description: Minimum similarity score (0.0-1.0)
    required: false
    default: 0.3
skills:
  - using-agent-brain
---

# Agent Brain Semantic Search

## Purpose

Performs pure semantic vector search using OpenAI embeddings. This mode finds documents based on meaning and conceptual similarity rather than exact keyword matching.

Semantic search is ideal for:
- Conceptual questions ("how does X work?")
- Finding related documentation even without exact term matches
- Natural language queries
- Discovering documents about similar concepts

## Usage

```
/agent-brain:agent-brain-semantic <query> [--top-k <n>] [--threshold <t>]
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| query | Yes | - | The conceptual search query |
| --top-k, -k | No | 5 | Number of results (1-20) |
| --threshold, -t | No | 0.3 | Minimum similarity score (0.0-1.0) |
| --source-types | No | - | Filter by source type (doc,code,test) |
| --languages | No | - | Filter by programming language |
| --file-paths | No | - | Filter by file path patterns (wildcards) |
| --scores | No | false | Show individual vector/BM25 scores |
| --full | No | false | Show full text content |
| --json | No | false | Output as JSON |
| --url | No | from config | Server URL (env: AGENT_BRAIN_URL) |

### When to Use Semantic Search

| Use Semantic Search | Use BM25/Keyword Instead |
|---------------------|--------------------------|
| "how does authentication work" | "AuthenticationError" |
| "best practices for caching" | "cache_ttl_seconds" |
| "explain the data model" | "UserSchema" |
| "what is the purpose of..." | exact function names |

## Execution

### Pre-flight Check

Verify the server is running and has indexed documents:

```bash
agent-brain status
```

Expected output shows:
- Server status: healthy
- Document count: > 0
- Mode: project or shared

### Search Command

```bash
agent-brain query "<query>" --mode vector --top-k <top-k> --threshold <threshold>
```

### Examples

```bash
# Conceptual query
agent-brain query "how does the authentication system work" --mode vector

# More results for broader exploration
agent-brain query "best practices for error handling" --mode vector --top-k 10

# Higher threshold for more precise matches
agent-brain query "explain caching strategy" --mode vector --threshold 0.5

# Lower threshold to find tangentially related docs
agent-brain query "security considerations" --mode vector --threshold 0.2
```

## Output

Format search results with source citations:

### Result Format

For each result, present:

1. **Source**: File path or document name
2. **Score**: Semantic similarity score (0-1)
3. **Content**: Relevant excerpt from the document

### Example Output

```
## Semantic Search Results for "how does caching work"

### 1. docs/architecture/caching.md (Score: 0.92)
The caching layer uses a multi-tier approach with in-memory LRU cache
for hot data and Redis for distributed caching. Cache invalidation
follows the write-through pattern...

### 2. docs/performance/optimization.md (Score: 0.78)
Performance optimization relies heavily on caching strategies.
The system implements time-based expiration with configurable TTL
values per resource type...

### 3. src/cache/redis_client.py (Score: 0.71)
"""Redis cache client with connection pooling and retry logic."""
class RedisCache:
    def __init__(self, ttl: int = 3600):
        ...

---
Found 3 results above threshold 0.3
```

### Citation Format

When referencing results in responses, always cite the source:

- "The caching documentation (`docs/architecture/caching.md`) explains..."
- "Based on the performance guide..."

## Error Handling

### Server Not Running

```
Error: Could not connect to Agent Brain server
```

**Resolution**: Start the server with `agent-brain start`

### No Results Found

```
No results found above threshold 0.3
```

**Resolution**:
- Try lowering the threshold: `--threshold 0.1`
- Rephrase the query with different conceptual terms
- Consider using hybrid search for better coverage: `--mode hybrid`

### Embedding Provider Not Configured

```
Error: Embedding provider not configured
```

**Resolution**: Semantic search requires a configured embedding provider:
```bash
# OpenAI (cloud)
export OPENAI_API_KEY="sk-proj-..."

# Or use local Ollama (free, no API key)
# Configure in config.yaml: embedding.provider: ollama
```

### Slow Response

Semantic search typically takes 800-1500ms due to embedding generation.

**If consistently slow**:
- Check network connectivity to OpenAI API
- Consider using BM25 for time-sensitive queries
- Use hybrid search with lower alpha for faster results

### Index Empty

```
Warning: No documents indexed
```

**Resolution**: Index documents first:
```bash
agent-brain index /path/to/docs
```

## Performance Notes

| Metric | Typical Value |
|--------|---------------|
| Latency | 800-1500ms |
| API calls | 1 embedding request per query |
| Best for | Conceptual queries, natural language |
