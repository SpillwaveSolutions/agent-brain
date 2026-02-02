---
name: agent-brain-multi
description: Search using multi-mode fusion combining all search modes
parameters:
  - name: query
    description: The comprehensive search query
    required: true
  - name: top-k
    description: Number of results to return (1-20)
    required: false
    default: 5
  - name: threshold
    description: Minimum relevance score (0.0-1.0)
    required: false
    default: 0.3
  - name: include-relationships
    description: Include entity relationships from graph
    required: false
    default: true
skills:
  - using-agent-brain
---

# Agent Brain Multi-Mode Search

## Purpose

Performs multi-mode fusion search combining BM25 keyword matching, semantic vector search, and GraphRAG relationships using Reciprocal Rank Fusion (RRF). This is the most comprehensive search mode, finding results from all angles.

Multi-mode search is ideal for:
- Complex queries requiring comprehensive results
- When you want both content matches AND relationships
- Investigating full implementation details
- Combining technical terms with conceptual understanding
- When you're not sure which mode would be best

## Usage

```
/agent-brain-multi <query> [--top-k <n>] [--threshold <t>] [--include-relationships]
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| query | Yes | - | The comprehensive search query |
| --top-k | No | 5 | Number of results (1-20) |
| --threshold | No | 0.3 | Minimum relevance score (0.0-1.0) |
| --include-relationships | No | true | Include graph relationships |

### How Multi-Mode Works

1. **BM25 Search**: Finds exact term matches
2. **Vector Search**: Finds semantically similar content
3. **Graph Search**: Finds related entities and relationships
4. **RRF Fusion**: Combines results using Reciprocal Rank Fusion

```
RRF_score(d) = Σ 1/(k + rank_i(d))
```

Where `k` is a constant (typically 60) and `rank_i(d)` is the rank of document `d` in result list `i`.

## Execution

### Pre-flight Check

```bash
# Verify server is running and capabilities
agent-brain status
```

Multi-mode works best with all indices available:
- BM25 index: Built during indexing
- Vector index: Requires embedding provider
- Graph index: Requires `ENABLE_GRAPH_INDEX=true`

### Search Command

```bash
agent-brain query "<query>" --mode multi --top-k <k> --threshold <t> --include-relationships
```

### Examples

```bash
# Comprehensive implementation search
agent-brain query "complete authentication implementation" --mode multi

# Include all relationships
agent-brain query "payment processing flow" --mode multi --include-relationships

# More results for exploration
agent-brain query "error handling patterns" --mode multi --top-k 10

# Lower threshold for broader search
agent-brain query "caching strategy" --mode multi --threshold 0.2
```

## Output

### Result Format

For each result, present:

1. **Source**: File path or document name
2. **Score**: RRF-fused relevance score
3. **Matched By**: Which modes found this result
4. **Content**: Relevant excerpt
5. **Relationships**: (if enabled) Connected entities

### Example Output

```
## Multi-Mode Search Results for "complete authentication implementation"

### 1. src/auth/oauth_client.py (RRF Score: 0.94)
**Matched by:** BM25, Vector, Graph

class OAuthClient:
    """
    Complete OAuth 2.0 client implementation.

    Handles authorization code flow, token refresh,
    and automatic retry with exponential backoff.
    """

    def authenticate(self, code: str) -> Token:
        ...

**Relationships:**
- CALLS → validate_token() in src/auth/validator.py
- CALLS → refresh_token() in src/auth/token_manager.py
- IMPORTS ← AuthService in src/services/auth_service.py

---

### 2. docs/auth/oauth-guide.md (RRF Score: 0.87)
**Matched by:** Vector, BM25

## OAuth 2.0 Implementation Guide

This guide covers the complete OAuth 2.0 implementation including:
- Authorization Code Flow
- Token Management
- Security Best Practices

### Getting Started
...

---

### 3. src/auth/token_manager.py (RRF Score: 0.72)
**Matched by:** Graph, Vector

class TokenManager:
    """Manages token lifecycle including refresh and revocation."""

    def refresh_token(self, token: Token) -> Token:
        ...

**Relationships:**
- CALLED_BY ← OAuthClient.authenticate()
- CALLS → cache.set() in src/cache/redis_client.py
- INHERITS → BaseTokenManager

---

Found 3 results above threshold 0.3
Search modes used: BM25 + Vector + Graph
Response time: 2341ms
```

### Mode Contribution Legend

| Badge | Meaning |
|-------|---------|
| BM25 | Found via keyword matching |
| Vector | Found via semantic similarity |
| Graph | Found via relationship traversal |

Results matched by multiple modes are typically more relevant.

## Error Handling

### Server Not Running

```
Error: Could not connect to Agent Brain server
```

**Resolution:**
```bash
agent-brain start --daemon
```

### Graph Index Not Available

```
Warning: Graph index not enabled. Multi-mode will use BM25 + Vector only.
```

**Resolution (optional):**
```bash
export ENABLE_GRAPH_INDEX=true
agent-brain stop && agent-brain start --daemon
agent-brain reset --yes
agent-brain index /path/to/code
```

Multi-mode gracefully degrades if graph is unavailable.

### No Results Found

```
No results found above threshold 0.3
```

**Resolution:**
- Try lowering threshold: `--threshold 0.1`
- Try a more specific or broader query
- Verify documents are indexed: `agent-brain status`

### API Key Missing

```
Error: OPENAI_API_KEY not set (required for vector component)
```

**Resolution:**
```bash
export OPENAI_API_KEY="sk-proj-..."
```

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
| Latency | 1500-2500ms |
| API calls | 1 embedding call |
| Best for | Comprehensive search, complex queries |

### When to Use Multi vs Other Modes

| Query Type | Recommended Mode |
|------------|------------------|
| Quick lookup of exact term | BM25 |
| Conceptual question | Vector |
| Balanced general search | Hybrid |
| **Comprehensive investigation** | **Multi** |
| Dependency/relationship query | Graph |

### Resource Usage

Multi-mode uses the most resources:
- Runs all three search modes
- Combines results with RRF
- Optional graph traversal

Consider using more targeted modes for simple queries.

## Graceful Degradation

Multi-mode adapts to available capabilities:

| Available | Modes Used |
|-----------|------------|
| BM25 + Vector + Graph | Full multi-mode |
| BM25 + Vector | Hybrid-like fusion |
| BM25 only | BM25 results only |
| Vector only | Vector results only |

Check server status to see available capabilities:
```bash
agent-brain status
```

## Related Commands

- `/agent-brain-hybrid` - Balanced BM25 + semantic
- `/agent-brain-graph` - Relationship-focused search
- `/agent-brain-bm25` - Fast keyword search
- `/agent-brain-vector` - Semantic concept search
