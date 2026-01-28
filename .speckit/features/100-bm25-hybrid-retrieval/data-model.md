# Data Model: BM25 & Hybrid Retrieval

## New Enums

### QueryMode
Determines the retrieval strategy.
- `vector`: Pure semantic search using embeddings.
- `bm25`: Pure keyword search using BM25.
- `hybrid`: Combined search using both strategies (default).

## Updated Models

### QueryRequest
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| query | str | (required) | Search query text |
| top_k | int | 5 | Number of results to return |
| similarity_threshold | float | 0.7 | Minimum similarity (for vector/hybrid) |
| mode | QueryMode | hybrid | Retrieval mode |
| alpha | float | 0.5 | Weighting between vector (alpha) and BM25 (1-alpha). Only used in hybrid mode. |

### QueryResult
| Field | Type | Description |
|-------|------|-------------|
| text | str | Chunk content |
| source | str | Source file path |
| score | float | Combined/Primary score |
| chunk_id | str | Unique ID |
| vector_score | float (opt) | Score from vector search |
| bm25_score | float (opt) | Score from BM25 search |
| metadata | dict | Additional metadata |

## Persistence Models

### BM25IndexData (Internal)
Used for serializing the BM25 index.
- `nodes`: List of serialized LlamaIndex nodes.
- `bm25_obj`: Serialized BM25 object (if using `rank-bm25` directly).
- `last_updated`: Timestamp.
