# Quickstart: BM25 & Hybrid Retrieval

## API Usage

### Hybrid Search (Default)
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "recursive character text splitter"}'
```

### BM25-only Search
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "recursive character text splitter", "mode": "bm25"}'
```

### Hybrid Search with custom Alpha
Higher alpha favors semantic/vector search.
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "error code 404", "mode": "hybrid", "alpha": 0.2}'
```

## CLI Usage

### Query with mode
```bash
doc-svr-ctl query "authentication" --mode bm25
```

### Query hybrid with alpha
```bash
doc-svr-ctl query "authentication" --mode hybrid --alpha 0.8
```

## Expected Response Metadata
Results will now include `vector_score` and `bm25_score`:
```json
{
  "results": [
    {
      "text": "...",
      "source": "docs/guide.md",
      "score": 0.85,
      "vector_score": 0.72,
      "bm25_score": 0.95,
      "chunk_id": "chunk_123"
    }
  ],
  "query_time_ms": 145.2,
  "total_results": 1
}
```
