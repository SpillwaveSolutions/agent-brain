# Agent Brain Architecture

Agent Brain is a RAG-based document indexing and semantic search system.

## Components

### Vector Store
ChromaDB stores document embeddings for fast similarity search.
Documents are chunked, embedded via OpenAI text-embedding-3-large,
and stored in persistent collections.

### BM25 Index
A disk-based BM25 index provides keyword matching alongside
semantic search. This enables hybrid retrieval combining exact
keyword matches with conceptual similarity.

### Hybrid Retrieval
The hybrid retrieval pipeline merges BM25 and vector results using
Reciprocal Rank Fusion (RRF). An alpha parameter controls the
blend between keyword (alpha=0) and semantic (alpha=1) results.

## API Design

The REST API uses FastAPI with endpoints for:
- Health checks and status monitoring
- Document indexing with job queuing
- Multi-mode semantic search
- Index management and reset
