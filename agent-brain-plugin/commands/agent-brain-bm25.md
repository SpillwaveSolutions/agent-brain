---
name: agent-brain-bm25
description: Search using BM25 keyword matching for exact terms
parameters:
  - name: query
    description: The exact search terms
    required: true
  - name: top-k
    description: Number of results to return (1-20)
    required: false
    default: 5
skills:
  - using-agent-brain
---

# Agent Brain BM25 Search

## Purpose

Performs BM25 (Best Matching 25) keyword search for fast, exact term matching. This mode is optimized for technical queries where you know the exact terms you're looking for.

BM25 search is ideal for:
- Error messages and codes
- Function and class names
- Configuration keys and variables
- Technical identifiers
- When speed is critical (10-50ms response)
- Offline searching (no API calls)

## Usage

```
/agent-brain-bm25 <query> [--top-k <n>]
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| query | Yes | - | The exact search terms |
| --top-k | No | 5 | Number of results (1-20) |

### When to Use BM25 vs Other Modes

| Use BM25 | Use Semantic/Hybrid Instead |
|----------|----------------------------|
| "AuthenticationError" | "how does auth work" |
| "recursiveCharacterTextSplitter" | "text splitting strategies" |
| "OPENAI_API_KEY" | "API configuration" |
| "def process_document" | "document processing flow" |
| error codes, stack traces | conceptual explanations |
| exact function names | "functions that do X" |

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
agent-brain query "<query>" --mode bm25 --top-k <k>
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

# Multiple terms (finds documents with all terms)
agent-brain query "OAuth client_id redirect_uri" --mode bm25
```

## Output

### Result Format

For each result, present:

1. **Source**: File path or document name
2. **Score**: BM25 relevance score (higher is better)
3. **Content**: Relevant excerpt with matching terms highlighted

### Example Output

```
## BM25 Keyword Search Results for "AuthenticationError"

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
Search mode: bm25 (keyword)
Response time: 23ms
```

### Citation Format

When referencing results in responses:
- "The error is defined in `src/auth/exceptions.py`..."
- "According to the test in `tests/test_auth.py`..."

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
No results found
```

**Resolution:**
- Verify exact spelling of search terms
- Check if documents containing terms are indexed
- Try partial matches
- Use hybrid mode for conceptual queries: `--mode hybrid`

### Index Empty

```
Warning: No documents indexed
```

**Resolution:**
```bash
agent-brain index /path/to/docs
```

### BM25 Index Not Built

```
Error: BM25 index not available
```

**Resolution:**
```bash
# Re-index to rebuild BM25 index
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
2. **No API calls**: Works offline, no API costs
3. **Exact matching**: Finds precise terms without semantic drift
4. **Deterministic**: Same query always returns same results
5. **No embedding provider required**: Works with any configuration

### Limitations

1. **No conceptual understanding**: Won't find "authentication" when searching "login"
2. **Exact match bias**: Misspellings won't match
3. **No synonym expansion**: "error" won't match "exception"
4. **Term frequency dependent**: Common terms ranked lower

## BM25 Algorithm Details

BM25 scoring considers:
- **Term frequency (TF)**: How often the term appears in a document
- **Inverse document frequency (IDF)**: How rare the term is across all documents
- **Document length normalization**: Adjusts for document size

```
Score = IDF * (TF * (k1 + 1)) / (TF + k1 * (1 - b + b * (doc_length / avg_doc_length)))
```

Default parameters:
- k1 = 1.5 (term frequency saturation)
- b = 0.75 (document length normalization)

## Related Commands

- `/agent-brain-vector` - Pure semantic search
- `/agent-brain-hybrid` - Combined BM25 + semantic
- `/agent-brain-keyword` - Alias for BM25 search
