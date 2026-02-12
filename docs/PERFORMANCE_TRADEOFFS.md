# ChromaDB vs PostgreSQL: Performance Tradeoffs

This guide helps you choose the right storage backend for your Agent Brain deployment.

## Summary

- **ChromaDB** is the simplest local-first option with minimal setup.
- **PostgreSQL + pgvector** scales better for large datasets and gives you mature SQL tooling.

## Comparison

| Dimension | ChromaDB (default) | PostgreSQL + pgvector |
|----------|--------------------|-----------------------|
| Setup complexity | Low | Medium (Docker Compose or managed PG) |
| Local dev experience | Excellent | Good (needs pgvector image) |
| Operational tooling | Basic | Strong (SQL, backups, monitoring) |
| Scalability | Good for small/medium | Better for large datasets |
| Index tuning | Limited | HNSW tuning available |
| Full-text search | BM25 | PostgreSQL tsvector |
| Hybrid search | Supported | Supported |
| Ecosystem integration | Minimal | Strong (SQL clients, BI, etc.) |

## When to Choose ChromaDB

- You want the fastest setup with zero database administration.
- Your dataset is small or medium (tens of thousands of documents).
- You prefer a self-contained local-first stack.
- You do not need SQL-level operational tooling.

## When to Choose PostgreSQL

- Your dataset is large (100k+ documents or rapidly growing).
- You want stronger operational tooling (backups, monitoring, SQL access).
- You need pgvector HNSW tuning for performance or recall control.
- Your team already runs PostgreSQL and prefers a single database stack.

## Tuning Considerations

- **PostgreSQL HNSW** indexes require tuning (`hnsw_m`, `hnsw_ef_construction`).
- Large indexes can take time and memory to build (plan for growth).
- Increase `pool_size` and `pool_max_overflow` for heavy indexing workloads.

## Migration Note

Agent Brain does not migrate data between ChromaDB and PostgreSQL. Switching
backends requires re-indexing documents after the change.

## Quick Decision Guide

- **Local demo or small team:** ChromaDB
- **Production or large corpora:** PostgreSQL + pgvector
