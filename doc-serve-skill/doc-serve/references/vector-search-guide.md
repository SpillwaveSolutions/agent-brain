# Vector Search Guide

## Overview

Vector search uses semantic similarity to find documents based on meaning rather than exact word matches. It converts both your query and documents into vector embeddings, then finds the most similar vectors using mathematical distance calculations.

## When to Use Vector Search

**Choose vector search when:**
- Looking for conceptual understanding or semantic similarity
- The query uses natural language descriptions
- You want to find related content even if exact terms don't match
- Working with conceptual documentation, tutorials, or explanatory content
- The query involves synonyms, related concepts, or abstract ideas

**Examples of vector queries:**
- `"How do I authenticate users?"` - Finds authentication-related content even with different terminology
- `"troubleshooting connection issues"` - Finds related problems and solutions
- `"best practices for error handling"` - Finds conceptual guidance on error management
- `"understanding OAuth flow"` - Finds explanations of OAuth concepts

## How to Use Vector Search

### CLI Usage

```bash
# Basic vector search (default mode)
doc-svr-ctl query "how does authentication work"

# Explicit vector mode
doc-svr-ctl query "troubleshooting guide" --mode vector

# With custom settings
doc-svr-ctl query "error handling patterns" --mode vector --threshold 0.5 --top-k 10
```

### API Usage

```bash
# POST /query endpoint
curl -X POST http://localhost:8000/query/ \
  -H "Content-Type: application/json" \
  -d '{
    "query": "how does authentication work",
    "mode": "vector",
    "threshold": 0.5,
    "top_k": 8
  }'
```

## Vector Search Options

| Option | Default | Description | Use Case |
|--------|---------|-------------|----------|
| `--mode vector` | Default | Uses semantic similarity | Conceptual queries |
| `--threshold F` | 0.7 | Similarity cutoff (0.0-1.0) | Higher = more relevant, fewer results |
| `--top-k N` | 5 | Maximum results | More results for exploration |

## Why Choose Vector Over Other Modes

**Vector Advantages:**
- 🧠 **Semantic Understanding**: Finds meaning, not just keywords
- 🔄 **Flexible Matching**: Works with synonyms and related concepts
- 🌍 **Language Agnostic**: Works across languages and domains
- 🎯 **Conceptual Search**: Great for tutorials and explanations

**When Vector is better than BM25:**
- Natural language queries
- Conceptual or explanatory content
- When exact terminology might vary
- Cross-language or multilingual content

**When Vector is better than Hybrid:**
- Pure semantic understanding needed
- No exact technical terms to match
- Performance-critical applications
- When keyword matching could be misleading

## Vector Algorithm Details

Vector search uses:
1. **Text Embedding**: Converts text to high-dimensional vectors (3072 dimensions for text-embedding-3-large)
2. **Cosine Similarity**: Measures angle between query and document vectors
3. **Ranking**: Sorts by similarity score (higher = more similar)

**Similarity Range**: 0.0 (completely dissimilar) to 1.0 (identical meaning)

**Embedding Model**: OpenAI text-embedding-3-large (high quality, semantic understanding)

## Example Queries and Results

### Example 1: Conceptual Query

**Query:** `doc-svr-ctl query "how does user authentication work"`

**Response:**
```json
{
  "results": [
    {
      "text": "User authentication involves validating credentials against a user database. The process typically includes: 1) Username/password verification, 2) Token generation for session management, 3) Optional two-factor authentication...",
      "source": "/docs/security/auth-overview.md",
      "score": 0.87,
      "vector_score": 0.87,
      "bm25_score": null,
      "chunk_id": "chunk_123",
      "metadata": {
        "file_name": "auth-overview.md",
        "chunk_index": 0
      }
    },
    {
      "text": "OAuth 2.0 provides a secure way to authenticate users without sharing passwords. The flow involves: authorization request, user consent, token exchange...",
      "source": "/docs/api/oauth-integration.md",
      "score": 0.82,
      "vector_score": 0.82,
      "bm25_score": null,
      "chunk_id": "chunk_456",
      "metadata": {
        "file_name": "oauth-integration.md",
        "chunk_index": 1
      }
    }
  ],
  "query_time_ms": 1240.5,
  "total_results": 2
}
```

### Example 2: Troubleshooting Query

**Query:** `doc-svr-ctl query "connection problems and solutions"`

**Response:**
```json
{
  "results": [
    {
      "text": "Common connection issues: 1) Network timeouts - increase timeout values, 2) SSL certificate problems - verify certificates, 3) Firewall blocking - check port access...",
      "source": "/docs/troubleshooting/network-issues.md",
      "score": 0.91,
      "vector_score": 0.91,
      "bm25_score": null,
      "chunk_id": "chunk_789",
      "metadata": {
        "file_name": "network-issues.md",
        "chunk_index": 0
      }
    },
    {
      "text": "Database connection pooling can prevent connection exhaustion. Configure minimum and maximum pool sizes based on your application load...",
      "source": "/docs/database/connection-pooling.md",
      "score": 0.78,
      "vector_score": 0.78,
      "bm25_score": null,
      "chunk_id": "chunk_101",
      "metadata": {
        "file_name": "connection-pooling.md",
        "chunk_index": 2
      }
    }
  ],
  "query_time_ms": 1180.2,
  "total_results": 2
}
```

## Performance Characteristics

- **Response Time**: 800-1500ms (requires API calls to OpenAI)
- **CPU Usage**: Medium (vector similarity calculations)
- **Memory Usage**: High (loads all document vectors)
- **API Costs**: Requires OpenAI API credits
- **Scalability**: Good (vectors pre-computed, similarity calculated locally)

## Best Practices

1. **Use natural language**: Vector search works best with conversational queries
2. **Adjust thresholds carefully**: Start with 0.7, lower to 0.3-0.5 for more results
3. **Combine with domain knowledge**: Understand what concepts are covered in your docs
4. **Use for exploration**: Great for discovering related content you didn't know existed

## Common Issues

- **API key required**: Must have valid OpenAI API key
- **Slow responses**: Expected due to API calls (800-1500ms typical)
- **Cost considerations**: Each query consumes OpenAI credits
- **No exact matches**: Won't find content that uses completely different terminology

## Integration Examples

### In Scripts
```bash
#!/bin/bash
# Semantic search for troubleshooting
doc-svr-ctl query "fix $1 problem" --mode vector --json | jq '.results[0].text'
```

### With Other Tools
```bash
# Find related documentation
doc-svr-ctl query "best practices for $TOPIC" --mode vector --json | jq -r '.results[].source'
```

### API Integration
```python
import requests

response = requests.post('http://localhost:8000/query/', json={
    'query': 'how to handle errors gracefully',
    'mode': 'vector',
    'threshold': 0.6
})
results = response.json()['results']
```

## Comparison with Other Modes

| Aspect | Vector | BM25 | Hybrid |
|--------|--------|------|--------|
| **Speed** | Slow (1-2s) | Fast (10-50ms) | Medium (1-2s) |
| **Precision** | Semantic | Exact terms | Balanced |
| **API Required** | Yes | No | Yes |
| **Best For** | Concepts | Technical terms | General use |
| **Language Support** | Excellent | Good | Excellent |