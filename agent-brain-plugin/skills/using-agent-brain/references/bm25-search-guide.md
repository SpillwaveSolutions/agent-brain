# BM25 Keyword Search Guide

## Overview

BM25 (Best Matching 25) is a keyword-based search algorithm that finds exact term matches in your indexed documents. It's excellent for technical queries where you need precise word matching rather than semantic understanding.

## When to Use BM25 Search

**Choose BM25 when:**
- Looking for specific function names, class names, or API endpoints
- Searching for error codes, status codes, or technical terms
- Need exact word matches rather than conceptual similarity
- Working with code documentation, API references, or technical specifications
- The query contains specific technical jargon or identifiers

**Examples of BM25 queries:**
- `"AuthenticationError"` - Find exact error class references
- `"HTTP 404"` - Find status code documentation
- `"recursiveCharacterTextSplitter"` - Find specific function names
- `"OAuth2 flow"` - Find exact OAuth implementation details

## How to Use BM25 Search

### CLI Usage

```bash
# Basic BM25 search
agent-brain query "your exact terms" --mode bm25

# With custom threshold (lower for more results)
agent-brain query "functionName" --mode bm25 --threshold 0.1

# With result count limit
agent-brain query "error code" --mode bm25 --top-k 10
```

### API Usage

```bash
# POST /query endpoint
curl -X POST http://localhost:8000/query/ \
  -H "Content-Type: application/json" \
  -d '{
    "query": "AuthenticationError",
    "mode": "bm25",
    "threshold": 0.2,
    "top_k": 5
  }'
```

## BM25 Search Options

| Option | Default | Description | Use Case |
|--------|---------|-------------|----------|
| `--mode bm25` | Required | Selects BM25 algorithm | All BM25 searches |
| `--threshold F` | 0.7 | Minimum relevance score (0.0-1.0) | Lower for more results, higher for precision |
| `--top-k N` | 5 | Maximum results to return | Increase for comprehensive results |

## Why Choose BM25 Over Other Modes

**BM25 Advantages:**
- ⚡ **Fast**: ~10-20ms response time
- 🎯 **Precise**: Finds exact word matches
- 🔍 **Predictable**: Results based on term frequency and document length
- 💾 **Lightweight**: No API keys required

**When BM25 is better than Hybrid:**
- Searching for specific identifiers (function names, error codes)
- Technical documentation with exact terminology
- When you need guaranteed exact matches
- Performance-critical applications

**When BM25 is better than Vector:**
- Non-English text or technical jargon
- When semantic meaning could be misleading
- Code search and technical documentation
- Exact string matching requirements

## BM25 Algorithm Details

BM25 scores documents based on:
1. **Term Frequency (TF)**: How often the search term appears
2. **Inverse Document Frequency (IDF)**: How rare the term is across documents
3. **Document Length Normalization**: Shorter documents score higher for same term frequency

**Formula**: `score = Σ IDF(q_i) × (TF(q_i,D) × (k₁ + 1)) / (TF(q_i,D) + k₁ × (1 - b + b × |D|/avgDL))`

Where:
- `q_i`: Query terms
- `D`: Document
- `k₁ = 1.5` (term frequency saturation)
- `b = 0.75` (length normalization factor)

## Example Queries and Results

### Example 1: Function Name Search

**Query:** `agent-brain query "recursiveCharacterTextSplitter" --mode bm25`

**Response:**
```json
{
  "results": [
    {
      "text": "The recursiveCharacterTextSplitter splits text recursively using character separators...",
      "source": "/docs/api/text-splitters.md",
      "score": 0.85,
      "vector_score": null,
      "bm25_score": 0.85,
      "chunk_id": "chunk_123",
      "metadata": {
        "file_name": "text-splitters.md",
        "chunk_index": 0
      }
    }
  ],
  "query_time_ms": 12.5,
  "total_results": 1
}
```

### Example 2: Error Code Search

**Query:** `agent-brain query "HTTP 404" --mode bm25`

**Response:**
```json
{
  "results": [
    {
      "text": "HTTP 404 Not Found indicates the requested resource could not be found...",
      "source": "/docs/api/http-status-codes.md",
      "score": 0.92,
      "vector_score": null,
      "bm25_score": 0.92,
      "chunk_id": "chunk_456",
      "metadata": {
        "file_name": "http-status-codes.md",
        "chunk_index": 2
      }
    },
    {
      "text": "404 errors commonly occur when:\n- URL is mistyped\n- Resource was deleted...",
      "source": "/docs/troubleshooting/404-errors.md",
      "score": 0.78,
      "vector_score": null,
      "bm25_score": 0.78,
      "chunk_id": "chunk_789",
      "metadata": {
        "file_name": "404-errors.md",
        "chunk_index": 0
      }
    }
  ],
  "query_time_ms": 15.2,
  "total_results": 2
}
```

## Performance Characteristics

- **Response Time**: 10-50ms (fastest of all modes)
- **CPU Usage**: Low (pure algorithmic scoring)
- **Memory Usage**: Minimal (uses pre-built BM25 index)
- **Scalability**: Excellent (index built once, queried many times)

## Best Practices

1. **Use exact terms**: BM25 works best with specific words, not general concepts
2. **Lower threshold for technical searches**: Technical docs may need `threshold 0.1-0.3`
3. **Combine with domain knowledge**: Know what terms are likely to appear in your docs
4. **Use for code search**: Perfect for finding function definitions, class names, imports

## Common Issues

- **No results found**: Try lowering the threshold or using different terminology
- **Too many results**: Increase threshold or add more specific terms
- **Index not ready**: Ensure documents are indexed before searching (`agent-brain status`)

## Integration Examples

### In Scripts
```bash
#!/bin/bash
# Search for specific error codes
agent-brain query "$1" --mode bm25 --json | jq '.results[0].text'
```

### With Other Tools
```bash
# Find all mentions of a function
agent-brain query "myFunction" --mode bm25 --json | jq -r '.results[].source'
```

### API Integration
```python
import requests

response = requests.post('http://localhost:8000/query/', json={
    'query': 'AuthenticationError',
    'mode': 'bm25',
    'threshold': 0.2
})
results = response.json()['results']
```