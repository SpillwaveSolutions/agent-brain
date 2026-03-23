---
last_validated: 2026-03-16
---

# Agent Brain System Architecture

This document provides a comprehensive overview of Agent Brain's architecture, design decisions, and unique value proposition in the RAG ecosystem.

## Table of Contents

- [Executive Summary](#executive-summary)
- [Why Agent Brain?](#why-agent-brain)
- [High-Level Architecture](#high-level-architecture)
- [Core Components](#core-components)
- [Data Flow](#data-flow)
- [Key Design Decisions](#key-design-decisions)
- [Comparison with Alternatives](#comparison-with-alternatives)

---

## Executive Summary

Agent Brain is a RAG (Retrieval-Augmented Generation) system designed specifically for AI coding assistants. It combines three retrieval paradigms into a unified, per-project knowledge system:

1. **BM25 Keyword Search** - Fast, precise matching for technical terms, function names, and error codes
2. **Semantic Vector Search** - Deep understanding of concepts and natural language queries
3. **GraphRAG Knowledge Graph** - Relationship-aware retrieval for dependencies, hierarchies, and connections

Unlike generic RAG solutions, Agent Brain is built with code-first priorities: AST-aware chunking, per-project isolation, and seamless integration with Claude Code.

### Key Differentiators

| Feature | Agent Brain | Generic RAG |
|---------|-------------|-------------|
| Code Understanding | AST-aware chunking for 8+ languages | Text-based splitting |
| Search Modes | 5 modes (BM25, Vector, Hybrid, Graph, Multi) | Usually 1-2 modes |
| Project Isolation | Per-project servers with auto-discovery | Shared instance |
| Knowledge Graphs | GraphRAG with entity extraction | Not available |
| Claude Integration | Native plugin and skill | Manual integration |

---

## Why Agent Brain?

### The Problem with Generic RAG

Traditional RAG systems treat all content as text. This works for documentation but fails for codebases:

- **Function boundaries ignored**: A function split mid-body loses context
- **No structural awareness**: Class hierarchies and import relationships are invisible
- **Single search mode**: Either keyword OR semantic, not both
- **No relationship tracking**: "What calls this function?" is unanswerable

### Agent Brain's Solution

Agent Brain treats code as a first-class citizen with:

1. **AST-Aware Chunking**: Uses tree-sitter to split code at semantic boundaries (functions, classes, methods)
2. **Hybrid Search**: Combines BM25 precision with vector semantics in a single query
3. **GraphRAG**: Builds a knowledge graph of entities and relationships for structural queries
4. **Per-Project Isolation**: Each project gets its own index with automatic port management

---

## High-Level Architecture

```
                                    +------------------------+
                                    |    Claude Code         |
                                    |    (Plugin/Skill)      |
                                    +------------------------+
                                              |
                                              v
+------------------+              +------------------------+
|  agent-brain-cli |  REST API   |  agent-brain-server    |
|                  |------------>|                        |
| - init           |             | FastAPI + Uvicorn      |
| - start/stop     |             +------------------------+
| - query          |                       |
| - index          |       +---------------+---------------+
| - status         |       |               |               |
+------------------+       v               v               v
                    +-----------+   +-----------+   +-----------+
                    | BM25      |   | ChromaDB  |   | GraphRAG  |
                    | Index     |   | Vectors   |   | Knowledge |
                    +-----------+   +-----------+   +-----------+
                          |               |               |
                          +-------+-------+-------+-------+
                                  |
                                  v
                         +----------------+
                         | Fusion Engine  |
                         | (RRF Scoring)  |
                         +----------------+
```

### Component Responsibilities

| Component | Role |
|-----------|------|
| **agent-brain-cli** | User-facing CLI for all operations |
| **agent-brain-server** | FastAPI REST API server handling indexing and queries |
| **BM25 Index** | Keyword-based retrieval using rank-bm25 |
| **ChromaDB** | Vector similarity search with OpenAI embeddings |
| **GraphRAG** | Knowledge graph for entity relationships |
| **Fusion Engine** | Combines results using Reciprocal Rank Fusion |

---

## Core Components

### 1. Document Loader

The document loader handles file discovery and content extraction.

**Location**: `agent-brain-server/agent_brain_server/indexing/document_loader.py`

**Capabilities**:
- Loads documents (.md, .txt, .pdf, .html, .rst)
- Loads code files (.py, .ts, .js, .java, .go, .rs, .c, .cpp, .cs)
- Automatic language detection via file extension and content patterns
- Metadata extraction (file size, path, source type)

**Supported Languages**: Python, TypeScript, JavaScript, Java, Go, Rust, C, C++, C#, Kotlin, Swift

### 2. Chunking Pipeline

The chunking system splits content into searchable units while preserving context.

**Location**: `agent-brain-server/agent_brain_server/indexing/chunking.py`

**Two Chunking Modes**:

| Mode | Used For | Strategy |
|------|----------|----------|
| **ContextAwareChunker** | Documents | Paragraph/sentence boundaries with overlap |
| **CodeChunker** | Source Code | AST-aware boundaries (function, class, method) |

**Code Chunker Features**:
- Uses LlamaIndex CodeSplitter with tree-sitter parsing
- Preserves symbol boundaries (never splits a function mid-body)
- Extracts rich metadata: symbol name, kind, line numbers, docstrings
- Generates optional LLM summaries for improved semantic search

### 3. Embedding Generator

Generates vector embeddings for semantic search.

**Location**: `agent-brain-server/agent_brain_server/indexing/embedding.py`

**Configuration**:
- Model: `text-embedding-3-large` (3072 dimensions)
- Batch processing: 100 chunks per batch
- Caching for repeated queries

### 4. Vector Store (ChromaDB)

Persistent vector storage for similarity search.

**Location**: `agent-brain-server/agent_brain_server/storage/vector_store.py`

**Features**:
- Thread-safe async operations
- Cosine similarity scoring
- Metadata filtering (source type, language, file path)
- Upsert support for incremental updates

### 5. BM25 Index

Keyword-based retrieval for exact term matching.

**Location**: `agent-brain-server/agent_brain_server/indexing/bm25_index.py`

**Features**:
- Persistent disk-based index
- LlamaIndex BM25Retriever integration
- Language and source type filtering
- Sub-50ms query latency

### 6. GraphRAG Index

Knowledge graph for relationship-aware retrieval.

**Location**: `agent-brain-server/agent_brain_server/indexing/graph_index.py`

**Features**:
- Entity extraction (LLM-based and code metadata)
- Relationship storage (imports, contains, calls, extends)
- Graph traversal for multi-hop queries
- Two storage backends: SimplePropertyGraphStore (default) and Kuzu (production)

### 7. Query Service

Orchestrates search across all indexes.

**Location**: `agent-brain-server/agent_brain_server/services/query_service.py`

**Query Modes**:

| Mode | Description | Use Case |
|------|-------------|----------|
| `bm25` | Keyword-only search | Technical terms, function names |
| `vector` | Semantic-only search | Concepts, explanations |
| `hybrid` | BM25 + Vector with Relative Score Fusion | Comprehensive results |
| `graph` | Knowledge graph traversal | Dependencies, relationships |
| `multi` | All three with Reciprocal Rank Fusion | Most comprehensive |

---

## Data Flow

### Indexing Flow

```
User Command: agent-brain index /path/to/project

1. Document Loading
   /path/to/project --> DocumentLoader --> LoadedDocument[]

2. Type Detection
   LoadedDocument --> LanguageDetector --> {source_type, language}

3. Chunking
   Documents --> ContextAwareChunker --> TextChunk[]
   Code Files --> CodeChunker (AST) --> CodeChunk[]

4. Embedding
   Chunks --> EmbeddingGenerator --> embeddings[]

5. Storage (Parallel)
   embeddings --> ChromaDB (vectors)
   chunks --> BM25Index (keywords)
   chunks --> GraphIndex (entities/relationships) [if enabled]
```

### Query Flow

```
User Query: agent-brain query "how does authentication work" --mode hybrid

1. Query Processing
   "how does..." --> QueryRequest{mode=hybrid, top_k=5}

2. Parallel Retrieval
   QueryRequest --> VectorSearch --> vector_results[]
   QueryRequest --> BM25Search --> bm25_results[]

3. Fusion (Hybrid Mode)
   vector_results + bm25_results --> RelativeScoreFusion --> fused_results[]

4. Ranking & Filtering
   fused_results --> RankByScore --> top_k results

5. Response
   results --> QueryResponse{results, query_time_ms}
```

---

## Key Design Decisions

### 1. Per-Project Isolation

**Decision**: Each project runs its own Agent Brain server with isolated indexes.

**Rationale**:
- No context pollution between projects
- Automatic port allocation prevents conflicts
- Server discovery via runtime.json enables multi-agent workflows
- Clean shutdown releases all resources

**Implementation**: `.agent-brain/` directory per project stores state, indexes, and runtime info.

`agent-brain init` writes CLI/runtime state such as `.agent-brain/config.json` and `runtime.json`, while provider/search configuration for setup flows is typically authored in `.agent-brain/config.yaml`; both files live under the same `.agent-brain/` root.

### 2. AST-Aware Chunking

**Decision**: Use tree-sitter for code parsing instead of text-based splitting.

**Rationale**:
- Functions and classes stay intact
- Symbol metadata (name, kind, line numbers) improves search relevance
- Enables structural queries ("find all methods in class X")
- Supports 8+ languages with consistent quality

### 3. Hybrid Search Default

**Decision**: Hybrid mode (BM25 + Vector) is the default search mode.

**Rationale**:
- BM25 excels at exact matches (function names, error codes)
- Vector search excels at semantic understanding
- Fusion provides best of both worlds
- Alpha parameter allows tuning (0 = pure BM25, 1 = pure vector)

### 4. GraphRAG as Optional

**Decision**: GraphRAG is disabled by default; users opt-in via configuration.

**Rationale**:
- Entity extraction adds indexing latency
- Graph storage requires additional memory
- Many use cases don't need relationship queries
- Progressive enhancement: enable when needed

### 5. LlamaIndex Foundation

**Decision**: Build on LlamaIndex rather than implementing RAG primitives from scratch.

**Rationale**:
- Battle-tested components (CodeSplitter, BM25Retriever)
- Active community and maintenance
- Plugin ecosystem (graph stores, embeddings)
- Focus on code-specific innovations, not RAG basics

---

## Comparison with Alternatives

### Agent Brain vs. LangChain RAG

| Aspect | Agent Brain | LangChain RAG |
|--------|-------------|---------------|
| Code Support | AST-aware, 8+ languages | Text-based only |
| Search Modes | 5 modes with fusion | Usually 1-2 modes |
| Graph Support | Built-in GraphRAG | Requires custom setup |
| Deployment | Per-project servers | Shared service |
| Claude Integration | Native plugin | Manual integration |

### Agent Brain vs. Copilot Workspace

| Aspect | Agent Brain | Copilot Workspace |
|--------|-------------|-------------------|
| Customization | Full control | Black box |
| Index Content | Your choice | Predetermined |
| Search Tuning | Mode/threshold control | None |
| Local Control | Full | Cloud-dependent |
| Cost | OpenAI embeddings only | Subscription |

### Agent Brain vs. Custom ChromaDB Setup

| Aspect | Agent Brain | Custom ChromaDB |
|--------|-------------|-----------------|
| Code Understanding | Built-in AST | DIY |
| BM25 Search | Included | Separate system |
| Graph Search | Included | Not available |
| CLI/API | Ready to use | Build yourself |
| Multi-project | Automatic | Manual setup |

---

## Next Steps

- [GraphRAG Integration Guide](GRAPHRAG_GUIDE.md) - Deep dive into knowledge graph features
- [Code Indexing Deep Dive](CODE_INDEXING.md) - AST-aware chunking explained
- [API Reference](API_REFERENCE.md) - Complete REST API documentation
- [Configuration Reference](CONFIGURATION.md) - All configuration options
