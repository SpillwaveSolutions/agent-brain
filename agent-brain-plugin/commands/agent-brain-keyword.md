---
name: agent-brain-keyword
description: Search using BM25 keyword matching for exact terms
parameters:
  - name: query
    description: The exact search terms
    required: true
  - name: top-k
    description: Number of results (1-20)
    required: false
    default: 5
skills:
  - using-agent-brain
---

# Agent Brain Keyword Search

## Purpose

Performs BM25 keyword search for fast, exact term matching. This mode is optimized for technical queries where you know the exact terms, function names, error codes, or identifiers.

Keyword search is ideal for:
- Error messages and codes
- Function and class names
- Configuration keys
- Technical identifiers
- When speed is critical (10-50ms response)

## Usage

```
/agent-brain:agent-brain-keyword <query> [--top-k <n>]
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| query | Yes | - | The exact search terms |
| top-k | No | 5 | Number of results (1-20) |

### When to Use Keyword Search

| Use Keyword/BM25 | Use Semantic Instead |
|------------------|----------------------|
| "AuthenticationError" | "how does auth work" |
| "recursiveCharacterTextSplitter" | "text splitting strategies" |
| "OPENAI_API_KEY" | "API configuration" |
| "def process_document" | "document processing flow" |
| error codes, stack traces | conceptual explanations |

## Execution

### Pre-flight Check

Verify the server is running:

```bash
agent-brain status
```

### Search Command

```bash
agent-brain query "<query>" --mode bm25 --top-k <top-k>
```

### Examples

```bash
# Search for error message
agent-brain query "ConnectionRefusedError" --mode bm25

# Search for function name
agent-brain query "process_document" --mode bm25

# Search for configuration key
agent-brain query "EMBEDDING_MODEL" --mode bm25

# More results
agent-brain query "AuthenticationError" --mode bm25 --top-k 10

# Search for multiple terms
agent-brain query "OAuth client_id redirect_uri" --mode bm25
```

## Output

Format search results with source citations:

### Result Format

For each result, present:

1. **Source**: File path or document name
2. **Score**: BM25 relevance score
3. **Content**: Relevant excerpt with matching terms highlighted

### Example Output

```
## Keyword Search Results for "AuthenticationError"

### 1. src/auth/exceptions.py (Score: 12.4)
class AuthenticationError(Exception):
    """Raised when authentication fails."""
    def __init__(self, message: str, code: str = "AUTH_FAILED"):
        self.code = code
        super().__init__(message)

### 2. tests/test_auth.py (Score: 8.7)
def test_invalid_credentials_raises_authentication_error():
    with pytest.raises(AuthenticationError) as exc:
        auth_client.authenticate("invalid", "credentials")
    assert exc.value.code == "AUTH_FAILED"

### 3. docs/errors/authentication.md (Score: 6.2)
## AuthenticationError

Raised when user credentials are invalid or expired.

**Common causes:**
- Invalid API key
- Expired token
- Missing credentials

---
Found 3 results
```

### Citation Format

When referencing results in responses, always cite the source:

- "The error is defined in `src/auth/exceptions.py`..."
- "According to the test in `tests/test_auth.py`..."

## Error Handling

### Server Not Running

```
Error: Could not connect to Agent Brain server
```

**Resolution**: Start the server with `agent-brain start`

### No Results Found

```
No results found
```

**Resolution**:
- Verify the exact spelling of search terms
- Try partial matches or wildcards if supported
- Use semantic search for conceptual queries: `--mode vector`
- Check if documents are indexed: `agent-brain status`

### Index Empty

```
Warning: No documents indexed
```

**Resolution**: Index documents first:
```bash
agent-brain index /path/to/docs
```

### BM25 Index Not Built

```
Error: BM25 index not available
```

**Resolution**: Re-index documents to build the BM25 index:
```bash
agent-brain reset --yes
agent-brain index /path/to/docs
```

## Performance Notes

| Metric | Typical Value |
|--------|---------------|
| Latency | 10-50ms |
| API calls | None (local computation) |
| Best for | Exact terms, technical queries |

### Advantages Over Semantic Search

1. **Speed**: 10-50ms vs 800-1500ms for semantic
2. **No API calls**: Works offline, no OpenAI costs
3. **Exact matching**: Finds precise terms without semantic drift
4. **Deterministic**: Same query always returns same results

### Limitations

1. **No conceptual understanding**: Won't find "authentication" when searching "login"
2. **Exact match bias**: Misspellings won't match
3. **No synonym expansion**: "error" won't match "exception"
