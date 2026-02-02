---
name: agent-brain-hybrid
description: Search using hybrid BM25 + semantic with alpha tuning
parameters:
  - name: query
    description: The search query text
    required: true
  - name: alpha
    description: Balance between vector (1.0) and BM25 (0.0)
    required: false
    default: 0.5
  - name: top-k
    description: Number of results to return (1-20)
    required: false
    default: 5
  - name: threshold
    description: Minimum relevance score (0.0-1.0)
    required: false
    default: 0.3
skills:
  - using-agent-brain
---

# Agent Brain Hybrid Search

## Purpose

Performs hybrid search combining BM25 keyword matching with semantic vector similarity. This is the default and most versatile search mode, balancing exact term matching with conceptual understanding.

Hybrid search is ideal for:
- General documentation queries
- Mixed technical and conceptual questions
- When you need both precise terms and semantic relevance
- Comprehensive search across diverse content

## Usage

```
/agent-brain-hybrid <query> [--alpha <a>] [--top-k <n>] [--threshold <t>]
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| query | Yes | - | The search query text |
| --alpha | No | 0.5 | Hybrid blend factor (0.0-1.0) |
| --top-k | No | 5 | Number of results (1-20) |
| --threshold | No | 0.3 | Minimum relevance score (0.0-1.0) |

### Alpha Tuning Guide

The `--alpha` parameter controls the blend between semantic and keyword matching:

| Alpha | Semantic | BM25 | Best For |
|-------|----------|------|----------|
| 1.0 | 100% | 0% | Pure semantic (concepts, explanations) |
| 0.7 | 70% | 30% | Favor meaning over exact terms |
| 0.5 | 50% | 50% | Balanced (default) |
| 0.3 | 30% | 70% | Favor exact terms with some semantic |
| 0.0 | 0% | 100% | Pure keyword (exact terms only) |

### When to Adjust Alpha

| Query Type | Suggested Alpha |
|------------|-----------------|
| "how does authentication work" | 0.7 |
| "OAuth implementation guide" | 0.5 |
| "AuthenticationError handling" | 0.3 |
| "def process_document" | 0.0 |

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
agent-brain query "<query>" --mode hybrid --alpha <alpha> --top-k <k> --threshold <t>
```

### Examples

```bash
# Balanced hybrid search (default)
agent-brain query "OAuth implementation" --mode hybrid

# Favor semantic understanding
agent-brain query "how does caching work" --mode hybrid --alpha 0.7

# Favor exact terms
agent-brain query "ConnectionRefusedError" --mode hybrid --alpha 0.3

# More results with lower threshold
agent-brain query "error handling patterns" --mode hybrid --top-k 10 --threshold 0.2

# Full custom search
agent-brain query "authentication flow" --mode hybrid --alpha 0.6 --top-k 8 --threshold 0.25
```

## Output

### Result Format

For each result, present:

1. **Source**: File path or document name
2. **Score**: Combined relevance score (normalized 0-1)
3. **Content**: Relevant excerpt from the document

### Example Output

```
## Hybrid Search Results for "OAuth implementation"
Alpha: 0.5 (balanced)

### 1. docs/auth/oauth-guide.md (Score: 0.89)
OAuth 2.0 implementation requires configuring the authorization endpoint,
token endpoint, and callback URL. The recommended flow for server-side
applications is the Authorization Code flow...

### 2. src/auth/oauth_client.py (Score: 0.76)
class OAuthClient:
    """Handles OAuth 2.0 authentication flow."""
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        ...

### 3. docs/api/authentication.md (Score: 0.71)
The API supports OAuth 2.0 Bearer tokens. Include the token in the
Authorization header: `Authorization: Bearer <token>`...

---
Found 3 results above threshold 0.3
Search mode: hybrid (alpha=0.5)
```

### Citation Format

When referencing results in responses, always cite the source:

- "According to `docs/auth/oauth-guide.md`..."
- "The implementation in `src/auth/oauth_client.py` shows..."

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
- Adjust alpha based on query type
- Try different search terms
- Verify documents are indexed: `agent-brain status`

### Invalid Alpha Value

```
Error: Alpha must be between 0.0 and 1.0
```

**Resolution:** Use a value in the range [0.0, 1.0]

### API Key Missing (for semantic component)

```
Error: OPENAI_API_KEY not set
```

**Resolution:**
```bash
export OPENAI_API_KEY="sk-proj-..."
# Or use Ollama for local embeddings:
export EMBEDDING_PROVIDER=ollama
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
| Latency | 1000-1800ms |
| API calls | 1 embedding call |
| Best for | General queries, mixed content |

### Comparison with Other Modes

| Mode | Speed | Exact Match | Concepts | Use Case |
|------|-------|-------------|----------|----------|
| BM25 | Fast | Excellent | Poor | Technical terms |
| Vector | Slow | Poor | Excellent | Concepts |
| **Hybrid** | Medium | Good | Good | **Balanced** |

## Related Commands

- `/agent-brain-bm25` - Pure keyword search
- `/agent-brain-vector` - Pure semantic search
- `/agent-brain-search` - Alias for hybrid search
- `/agent-brain-multi` - Multi-mode fusion search
