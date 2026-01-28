# Doc-Serve Product Roadmap

**Version:** 1.1.0
**Last Updated:** 2026-01-28
**Status:** Active

---

## Vision

Doc-Serve is a local-first RAG (Retrieval-Augmented Generation) service that indexes documentation and source code, providing intelligent semantic search via API for CLI tools and Claude integration. The core principles are:

- **Privacy First:** Runs entirely on your machine with disk persistence
- **High Retrieval Quality:** Vector + keyword + hybrid search strategies
- **Operational Ergonomics:** CLI-first management experience
- **Future-Proof Flexibility:** Built on LlamaIndex abstractions
- **Phased Delivery:** Incremental value with each release

---

## Phase Summary

| Phase | Name | Spec ID | Status      | Priority | Transport |
|-------|------|---------|-------------|----------|-----------|
| 1 | Core Document RAG | 001-005 | COMPLETED   | - | HTTP |
| 2 | BM25 & Hybrid Retrieval | 100 | COMPLETED   | P1 | HTTP |
| 3 | Source Code Ingestion | 101 | COMPLETED   | P2 | HTTP |
| 3.1 | Multi-Instance Architecture | 109 | COMPLETED   | P1 | HTTP |
| 3.2 | C# Code Indexing | 110 | COMPLETED   | P2 | HTTP |
| 3.3 | Skill Instance Discovery | 111 | IN-PROGRESS | P2 | HTTP |
| 4 | UDS & Claude Plugin Evolution | 102 | Future      | P3 | HTTP + UDS |
| 5 | Pluggable Model Providers | 103 | Next        | P3 | HTTP + UDS |
| 6 | PostgreSQL/AlloyDB Backend | 104 | Future      | P4 | HTTP + UDS |
| 7 | AWS Bedrock Provider | 105 | Future      | P4 | HTTP + UDS |
| 8 | Google Vertex AI Provider | 106 | Future      | P4 | HTTP + UDS |

---

## Phase 1: Core Document RAG

**Status:** COMPLETED
**Spec Directory:** `specs/001-005`

### Delivered Capabilities

- **Document Ingestion:** PDF + Markdown (.md, .mdx) support
- **Context-Enriched Chunking:** Section/heading-aware chunking with Claude summarization
- **Vector Search:** Chroma vector database with OpenAI text-embedding-3-large
- **Persistent Storage:** Disk-based persistence across restarts
- **REST API:** `/query`, `/index`, `/health` endpoints
- **CLI Tool:** `doc-svr-ctl` with status, query, index, reset commands
- **Claude Skill:** Basic integration for conversational document search

### Technical Stack

- FastAPI + Uvicorn server
- LlamaIndex for document processing
- ChromaDB for vector storage
- OpenAI embeddings + Claude Haiku summarization

---

## Phase 2: BM25 & Hybrid Retrieval

**Status:** NEXT
**Spec Directory:** `specs/100-bm25-hybrid-retrieval`
**Transport:** HTTP only

### Scope

Add classic keyword search (BM25) alongside vector search, with hybrid retrieval combining both strategies using Reciprocal Rank Fusion (RRF).

### Key Features

- **BM25 Retriever:** Classic full-text keyword search
- **Hybrid Retrieval:** Combined vector + BM25 with configurable fusion
- **Retrieval Mode Selection:** API parameter for `vector`, `bm25`, or `hybrid` (default)
- **Alpha Tuning:** Configurable weight between vector and keyword scores
- **Enhanced Scoring Metadata:** Detailed score breakdowns in responses

### API Changes

```
POST /query
{
  "query": "search text",
  "mode": "hybrid",    // "vector" | "bm25" | "hybrid"
  "alpha": 0.5,        // fusion weight (0=BM25 only, 1=vector only)
  "top_k": 10
}
```

### Benefits

- Better precision for exact term matching (function names, error codes)
- Improved recall through combined retrieval strategies
- User control over search behavior

---

## Phase 3: Source Code Ingestion & Unified Corpus

**Status:** Planned
**Spec Directory:** `specs/101-code-ingestion`
**Transport:** HTTP

### Scope

Enable indexing of source code alongside documentation for unified corpus searches. This is critical for the book generation and corpus use cases.

### Key Features

- **Code Ingestion via CodeSplitter:**
  - Python (.py)
  - TypeScript/JavaScript (.ts, .tsx, .js, .jsx)
- **Unified Indexing:** Vector + BM25 across documents and code
- **Code Summaries:** SummaryExtractor generates natural language descriptions per code chunk
- **Extended Filters:** `source_type` (doc vs code), `language` filters in queries
- **AST-Aware Chunking:** Preserves function/class boundaries

### API Changes

```
POST /index
{
  "folder_path": "/path/to/project",
  "include_code": true,
  "languages": ["python", "typescript"]
}

POST /query
{
  "query": "authentication handler",
  "source_type": "code",    // "doc" | "code" | "all"
  "language": "python"
}
```

### Benefits

- Single search across documentation and implementation
- Code context improves answer quality for technical queries
- Enables corpus-based book/tutorial generation

---

## Phase 3.1: Multi-Instance Architecture

**Status:** COMPLETED
**Spec Directory:** `.speckit/features/109-multi-instance-architecture/`
**Transport:** HTTP

### Scope

Enable running multiple concurrent doc-serve instances with per-project isolation, automatic port allocation, and runtime discovery for agent integration.

### Key Features

- **Per-Project Isolation:** Each project gets its own server instance with isolated indexes
- **Auto-Port Allocation:** OS-assigned ports prevent conflicts between projects
- **State Directory:** Project state stored in `.claude/doc-serve/`
- **Runtime Discovery:** `runtime.json` enables agents and skills to find running instances
- **Lock File Protocol:** Prevents double-start of instances
- **Project Root Resolution:** Consistent detection via git or marker files

### New CLI Commands

```bash
doc-svr-ctl init              # Initialize project for doc-serve
doc-svr-ctl start --daemon    # Start server with auto-port
doc-svr-ctl stop              # Stop the server
doc-svr-ctl list              # List all running instances
```

### Benefits

- Work on multiple projects simultaneously
- No port conflicts between projects
- State travels with the project (can be version-controlled)
- Agents can automatically discover running servers

---

## Phase 3.2: C# Code Indexing

**Status:** COMPLETED
**Spec Directory:** `.speckit/features/110-csharp-code-indexing/`
**Transport:** HTTP

### Scope

Add C# language support to the code ingestion pipeline with AST-aware parsing.

### Key Features

- **File Extensions:** `.cs` and `.csx` (C# scripts)
- **AST-Aware Chunking:** Classes, methods, interfaces, properties, enums
- **XML Documentation:** Extracts `/// <summary>` comments as metadata
- **Language Filter:** Query with `--languages csharp`

### Benefits

- Full .NET ecosystem support
- Semantic search across C# codebases
- Rich metadata extraction for better search quality

---

## Phase 3.3: Skill Instance Discovery

**Status:** IN-PROGRESS
**Spec Directory:** `.speckit/features/111-skill-instance-discovery/`
**Transport:** HTTP

### Scope

Update the doc-serve Claude Code skill to leverage multi-instance architecture for automatic server discovery and lifecycle management.

### Key Features

- **Auto-Initialization:** Skill automatically runs `doc-svr-ctl init` when needed
- **Server Discovery:** Reads `runtime.json` to find running instances
- **Auto-Start:** Starts server automatically if no instance is running
- **Status Reporting:** Reports port, mode, instance ID, document count
- **Cross-Agent Sharing:** Multiple agents share the same server instance

### Benefits

- Zero-configuration skill usage
- No manual server management required
- Seamless multi-agent workflows

---

## Phase 4: UDS Transport & Claude Plugin Evolution

**Status:** Future
**Spec Directory:** `specs/102-uds-claude-plugin`
**Transport:** HTTP + optional UDS

### Scope

Add Unix Domain Socket (UDS) transport for lower-latency local communication and evolve the Claude plugin with richer capabilities.

### Key Features

- **UDS Transport:** Optional Unix Domain Socket alongside HTTP
- **Rich Slash Commands:**
  - `/search` - General semantic search
  - `/doc` - Documentation-only search
  - `/code` - Code-only search
- **Server Lifecycle Management:** Plugin auto-starts/stops server
- **Multi-Step Research Agent:** Break down complex questions

### Benefits

- ~10-50x latency improvement for local queries via UDS
- More intuitive Claude interaction patterns
- Autonomous research capabilities

---

## Phase 5: Pluggable Model Providers

**Status:** Future
**Spec Directory:** `specs/103-pluggable-providers`
**Transport:** HTTP + UDS

### Scope

Full configuration-driven model selection using LlamaIndex abstractions. No code changes required to switch providers.

### Supported Embedding Providers

| Provider | Models | Notes |
|----------|--------|-------|
| OpenAI | text-embedding-3-small/large, ada-002 | Default |
| Ollama | nomic-embed-text, bge, etc. | Local, offline |
| Cohere | embed-english-v3, embed-multilingual-v3 | Via API |

**Note:** Grok and Gemini currently lack public embedding APIs and are not supported for embeddings.

### Supported Summarization/LLM Providers

| Provider | Models | Notes |
|----------|--------|-------|
| Anthropic | Claude Haiku, Sonnet, Opus | Default |
| OpenAI | GPT-4o, GPT-4o-mini | Via API |
| Gemini | Flash, Pro | Via API |
| Grok | Via OpenAI-compatible endpoint | Via API |
| Ollama | Llama 3, Mistral, Qwen | Local, offline |

### Configuration Example

```yaml
# config.yaml
embedding:
  provider: ollama
  model: nomic-embed-text
  params:
    base_url: http://localhost:11434

summarization:
  provider: anthropic
  model: claude-3-5-sonnet-20241022
  params:
    api_key_env: ANTHROPIC_API_KEY
```

### Benefits

- Run completely offline with Ollama
- Cost optimization with different providers
- Enterprise flexibility

---

## Phase 6: PostgreSQL/AlloyDB Backend

**Status:** Future
**Spec Directory:** `specs/104-postgresql-backend`
**Transport:** HTTP + UDS

### Scope

Optional configuration-driven switch to PostgreSQL (local) or AlloyDB (managed/cloud) as persistent storage backend.

### Key Features

- **pgvector Extension:** High-performance vector similarity search
- **AlloyDB ScaNN Indexes:** Google Cloud's optimized vector indexing
- **Native Full-Text Search:** PostgreSQL tsvector/tsquery (BM25-like)
- **Hybrid Retrieval:** `hybrid_search=True` on PGVectorStore
- **JSONB Metadata:** Rich metadata with GIN indexes

### Benefits

- Superior scalability for very large corpora
- Built-in replication/backup
- Transactional consistency
- Mature PostgreSQL full-text engine replaces custom BM25

### Migration Path

1. Install `llama-index-vector-stores-postgres`
2. Update config.yaml with PostgreSQL connection
3. Re-index documents (one-time migration)

---

## Phase 7: AWS Bedrock Provider Support

**Status:** Future
**Spec Directory:** `specs/105-aws-bedrock`
**Transport:** HTTP + UDS

### Scope

Add full support for AWS Bedrock as a pluggable provider for both embeddings and summarization/completion LLMs.

### Supported Models

**Embeddings:**
- Amazon Titan Embed Text v1/v2
- Cohere Embed English/Multilingual v3

**Summarization/LLM:**
- Claude (via Bedrock)
- Titan Text
- Meta Llama
- Mistral
- Cohere Command

### Configuration

```yaml
embedding:
  provider: bedrock
  model: amazon.titan-embed-text-v2
  params:
    region: us-east-1

summarization:
  provider: bedrock
  model: anthropic.claude-3-sonnet
```

### Authentication

- Default AWS credentials chain
- Profile-based authentication
- Explicit keys/region configuration

### Benefits

- Enterprise-grade security/compliance
- Access to high-performance AWS-hosted models
- Cost optimization for AWS users

---

## Phase 8: Google Vertex AI Provider Support

**Status:** Future
**Spec Directory:** `specs/106-vertex-ai`
**Transport:** HTTP + UDS

### Scope

Add full support for Google Vertex AI as a pluggable provider for embeddings and summarization/completion LLMs.

### Supported Models

**Embeddings:**
- textembedding-gecko
- multimodalembedding

**Summarization/LLM:**
- Gemini 1.5 Flash/Pro
- gemini-1.0-pro

### Configuration

```yaml
embedding:
  provider: vertex
  model: textembedding-gecko@003
  params:
    project: my-gcp-project
    location: us-central1

summarization:
  provider: vertex
  model: gemini-1.5-flash
```

### Authentication

- Service account JSON
- Application Default Credentials (ADC)
- Explicit project/location

### Benefits

- Integration with Google Cloud ecosystem
- Strong multimodal capabilities with Gemini
- Enterprise features for GCP users

---

## Corpus/Book Generation Use Cases

Doc-Serve enables creating searchable, AI-queryable corpora from large documentation sets, codebases, or book collections. This is a key differentiator for technical content development.

### Use Case 1: AWS CDK Documentation Corpus

**Problem:** AWS CDK has extensive documentation across multiple languages and services. Developers need quick access to specific patterns and configurations.

**Solution with Doc-Serve:**

```bash
# Index AWS CDK documentation
doc-svr-ctl index ~/aws-cdk-docs/

# Index AWS CDK Python library source (Phase 3)
doc-svr-ctl index ~/aws-cdk-python/src/ --include-code

# Query during development
doc-svr-ctl query "S3 bucket with lifecycle rules and versioning"
```

**Sample Queries:**
- "How to create a Lambda function with VPC access?"
- "DynamoDB table with global secondary index pattern"
- "Cross-stack references best practices"
- "EventBridge rule for S3 object creation"

**Book Generation Application:**
- Index AWS CDK source + comprehensive PDF guide
- Create corpus for writing AWS CDK tutorials
- Claude can cite specific documentation and code examples

---

### Use Case 2: Claude/Anthropic Documentation Corpus

**Problem:** Building AI applications requires referencing Claude API docs, SDK documentation, and best practices frequently.

**Solution with Doc-Serve:**

```bash
# Index Claude documentation
doc-svr-ctl index ~/anthropic-docs/

# Index Claude SDK source (Phase 3)
doc-svr-ctl index ~/claude-sdk/src/ --include-code

# Query via Claude skill
"How do I implement streaming responses with the Python SDK?"
```

**Sample Queries:**
- "Claude tool use best practices"
- "Prompt caching implementation"
- "Error handling for rate limits"
- "Vision API usage patterns"

**Skill Generation Application:**
- Index Claude Code documentation
- Create corpus for writing Claude Code skills
- Skills can reference authoritative source material

---

### Use Case 3: Internal Technical Manual

**Problem:** Large organizations have extensive internal documentation that teams need to search effectively for onboarding and reference.

**Solution with Doc-Serve:**

```bash
# Index internal documentation
doc-svr-ctl index ~/company-docs/architecture/
doc-svr-ctl index ~/company-docs/onboarding/
doc-svr-ctl index ~/company-docs/api-guides/

# Index internal code (Phase 3)
doc-svr-ctl index ~/company-monorepo/libs/ --include-code

# Team members query via Claude skill
"What is our authentication flow for mobile apps?"
```

**Benefits:**
- New team members find answers faster
- Reduced dependency on tribal knowledge
- Consistent answers across the organization

---

### Use Case 4: Open Source Project Contribution

**Problem:** Contributing to large open source projects requires understanding existing patterns, conventions, and implementation details.

**Solution with Doc-Serve:**

```bash
# Index project documentation
doc-svr-ctl index ~/kubernetes/docs/

# Index project source code (Phase 3)
doc-svr-ctl index ~/kubernetes/pkg/ --include-code

# Query for contribution patterns
doc-svr-ctl query "How are admission controllers implemented?"
```

**Sample Queries:**
- "Pod scheduling algorithm"
- "Custom resource definition validation"
- "Controller reconciliation loop pattern"

**Benefits:**
- Faster ramp-up for contributors
- Understand conventions before submitting PRs
- Find similar implementations to reference

---

## Recommended Next Actions

1. **Implement Phase 2** (BM25 + Hybrid Retrieval) - Immediate retrieval quality improvements
2. **Proceed to Phase 3** (Code Ingestion) - Enables unified corpus searches
3. **Phase 5 for Local-Only** - Run completely offline with Ollama
4. **Phase 6 for Scale** - PostgreSQL backend for large corpora

Model provider flexibility (Phases 5, 7, 8) and PostgreSQL backend (Phase 6) are cleanly deferred until the core retrieval enhancements are stable.

---

## Appendix: Numbering Convention

- **001-099:** Phase 1 specs (existing, completed)
- **100-199:** Roadmap phases 2-8 (future development)
- **200+:** Reserved for future expansion

See `docs/roadmaps/spec-mapping.md` for full phase-to-spec mapping.
