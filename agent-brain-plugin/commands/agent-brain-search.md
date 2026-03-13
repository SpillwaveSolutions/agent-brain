---
name: agent-brain-search
description: Search indexed documentation using hybrid BM25+semantic retrieval
parameters:
  - name: query
    description: The search query text
    required: true
  - name: top-k
    description: Number of results to return (1-20)
    required: false
    default: 5
  - name: threshold
    description: Minimum relevance score (0.0-1.0)
    required: false
    default: 0.3
  - name: alpha
    description: Hybrid blend (0=BM25 only, 1=semantic only)
    required: false
    default: 0.5
skills:
  - using-agent-brain
---

# Agent Brain Hybrid Search

## Purpose

Performs hybrid search combining BM25 keyword matching with semantic vector similarity. This is the default and recommended search mode as it balances exact term matching with conceptual understanding.

Hybrid search is ideal for:
- General documentation queries
- When you need both precise term matching and conceptual relevance
- Comprehensive search results across different document types

## Usage

```
/agent-brain:agent-brain-search <query> [--top-k <n>] [--threshold <t>] [--alpha <a>]
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| query | Yes | - | The search query text |
| top-k | No | 5 | Number of results (1-20) |
| threshold | No | 0.3 | Minimum relevance score (0.0-1.0) |
| alpha | No | 0.5 | Hybrid blend factor |

### Alpha Tuning

The `--alpha` parameter controls the balance between vector and BM25:

- `alpha = 1.0`: 100% semantic (pure vector search)
- `alpha = 0.7`: 70% semantic, 30% keyword (favor meaning)
- `alpha = 0.5`: 50% each (balanced - default)
- `alpha = 0.3`: 30% semantic, 70% keyword (favor exact terms)
- `alpha = 0.0`: 100% keyword (pure BM25)

## Execution

### Pre-flight Check

Before executing the search, verify the server is running:

```bash
agent-brain status
```

If the server is not running, start it first:

```bash
agent-brain start
```

### Search Command

```bash
agent-brain query "<query>" --mode hybrid --top-k <top-k> --threshold <threshold> --alpha <alpha>
```

### Examples

```bash
# Basic hybrid search
agent-brain query "OAuth implementation" --mode hybrid

# More results with lower threshold
agent-brain query "error handling patterns" --mode hybrid --top-k 10 --threshold 0.2

# Favor keyword matching for technical terms
agent-brain query "AuthenticationError" --mode hybrid --alpha 0.3

# Favor semantic matching for concepts
agent-brain query "how does caching work" --mode hybrid --alpha 0.7
```

## Output

Format search results with source citations:

### Result Format

For each result, present:

1. **Source**: File path or document name
2. **Score**: Relevance score (normalized 0-1)
3. **Content**: Relevant excerpt from the document

### Example Output

```
## Search Results for "OAuth implementation"

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

**Resolution**: Start the server with `agent-brain start`

### No Results Found

```
No results found above threshold 0.3
```

**Resolution**:
- Try lowering the threshold: `--threshold 0.1`
- Try different search terms
- Verify documents are indexed: `agent-brain status`

### Invalid Alpha Value

```
Error: Alpha must be between 0.0 and 1.0
```

**Resolution**: Use a value between 0.0 and 1.0 for the alpha parameter

### API Key Missing

```
Error: OPENAI_API_KEY not set
```

**Resolution**: Set the environment variable:
```bash
export OPENAI_API_KEY="sk-proj-..."
```

### Index Empty

```
Warning: No documents indexed
```

**Resolution**: Index documents first:
```bash
agent-brain index /path/to/docs
```
