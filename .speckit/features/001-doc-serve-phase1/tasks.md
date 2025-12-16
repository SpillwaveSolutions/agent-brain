# Doc-Serve Phase 1 Implementation Tasks

**Feature**: Doc-Serve RAG-Based Document Indexing and Query System
**Version**: 1.0
**Generated From**: docs/design/doc-serve-sdd.md
**Date**: December 15, 2024

---

## Executive Summary

Phase 1 implementation consists of **28 tasks** organized into **7 categories**:
- Scaffolding & Setup (5 tasks)
- Core Infrastructure (4 tasks)
- Indexing Pipeline (4 tasks)
- Query Engine (3 tasks)
- API Layer (4 tasks)
- CLI Tool (4 tasks)
- Testing & Documentation (4 tasks)

**Critical Path**: Setup → Config → Models → Storage → Indexing → Query → API → CLI → Tests

**Estimated Total Effort**: ~40-50 hours of focused development

---

## Category 1: Scaffolding & Setup

### TASK-001: Create Monorepo Structure
- **Description**: Set up the monorepo directory structure with doc-serve-server, doc-svr-ctl, and doc-serve-skill directories
- **Dependencies**: None (starter task)
- **Complexity**: Low
- **Effort**: 30 minutes
- **Acceptance Criteria**:
  - [ ] doc-serve-server/ directory with src/ and tests/
  - [ ] doc-svr-ctl/ directory with src/ and tests/
  - [ ] doc-serve-skill/ directory with examples/
  - [ ] Root README.md linking to components

### TASK-002: Configure doc-serve-server pyproject.toml
- **Description**: Create Poetry configuration with all Phase 1 dependencies
- **Dependencies**: TASK-001
- **Complexity**: Low
- **Effort**: 30 minutes
- **Acceptance Criteria**:
  - [ ] pyproject.toml with FastAPI, LlamaIndex, Chroma, OpenAI, Anthropic deps
  - [ ] Dev dependencies: pytest, black, ruff, mypy
  - [ ] Build system configured
  - [ ] `poetry install` succeeds

### TASK-003: Configure doc-svr-ctl pyproject.toml
- **Description**: Create Poetry configuration for CLI tool
- **Dependencies**: TASK-001
- **Complexity**: Low
- **Effort**: 20 minutes
- **Acceptance Criteria**:
  - [ ] pyproject.toml with Click, httpx dependencies
  - [ ] Entry point configured for `doc-svr-ctl` command
  - [ ] Dev dependencies configured

### TASK-004: Create .env.example and Configuration Docs
- **Description**: Document required environment variables
- **Dependencies**: TASK-001
- **Complexity**: Low
- **Effort**: 20 minutes
- **Acceptance Criteria**:
  - [ ] .env.example with all required variables
  - [ ] Comments explaining each variable
  - [ ] .gitignore entries for .env files

### TASK-005: Initialize Git Repository
- **Description**: Set up Git with proper .gitignore
- **Dependencies**: TASK-001
- **Complexity**: Low
- **Effort**: 15 minutes
- **Acceptance Criteria**:
  - [ ] .gitignore for Python, IDE, env files
  - [ ] Initial commit with structure

---

## Category 2: Core Infrastructure

### TASK-006: Implement Settings Module
- **Description**: Create Pydantic settings class with all configuration options (SDD Section 4.1.6)
- **Dependencies**: TASK-002
- **Complexity**: Medium
- **Effort**: 1 hour
- **Acceptance Criteria**:
  - [ ] Settings class with all config options from SDD
  - [ ] Environment variable loading from .env
  - [ ] Sensible defaults for all optional settings
  - [ ] Validation for required fields (API keys)

### TASK-007: Implement Request/Response Models
- **Description**: Create Pydantic models for API requests and responses (SDD Section 4.1.5)
- **Dependencies**: TASK-002
- **Complexity**: Medium
- **Effort**: 1.5 hours
- **Acceptance Criteria**:
  - [ ] QueryRequest and QueryResponse models
  - [ ] IndexRequest and IndexResponse models
  - [ ] HealthStatus and IndexingStatus models
  - [ ] Field validation with appropriate constraints

### TASK-008: Implement Vector Store Manager
- **Description**: Create Chroma vector store wrapper with CRUD operations (SDD Section 4.1.4)
- **Dependencies**: TASK-006, TASK-007
- **Complexity**: High
- **Effort**: 3 hours
- **Acceptance Criteria**:
  - [ ] VectorStoreManager class with initialization
  - [ ] add_nodes() method for storing embeddings
  - [ ] similarity_search() method for querying
  - [ ] Persistent storage to disk
  - [ ] Thread-safe operations

### TASK-009: Implement State Manager
- **Description**: Create indexing state tracking for progress monitoring
- **Dependencies**: TASK-007
- **Complexity**: Medium
- **Effort**: 1 hour
- **Acceptance Criteria**:
  - [ ] IndexingState dataclass/model
  - [ ] Thread-safe state updates
  - [ ] Status tracking (indexing, ready, error)

---

## Category 3: Indexing Pipeline

### TASK-010: Implement Document Loader
- **Description**: Create document loading from folder with LlamaIndex (SDD Section 4.1.3)
- **Dependencies**: TASK-006
- **Complexity**: Medium
- **Effort**: 2 hours
- **Acceptance Criteria**:
  - [ ] DocumentLoader class
  - [ ] Support for .txt, .md, .pdf, .docx, .html
  - [ ] Recursive folder scanning
  - [ ] Metadata extraction (filename, path, size)

### TASK-011: Implement Context-Aware Chunker
- **Description**: Create text chunking with RecursiveCharacterTextSplitter pattern (SDD Section 4.1.3)
- **Dependencies**: TASK-010
- **Complexity**: High
- **Effort**: 2.5 hours
- **Acceptance Criteria**:
  - [ ] ContextAwareChunker class
  - [ ] Configurable chunk size (default 512 tokens)
  - [ ] Configurable overlap (default 50 tokens)
  - [ ] Token counting with tiktoken
  - [ ] Metadata preservation

### TASK-012: Implement Embedding Generator
- **Description**: Create OpenAI embedding generation with batching (SDD Section 4.1.3)
- **Dependencies**: TASK-006, TASK-011
- **Complexity**: High
- **Effort**: 2.5 hours
- **Acceptance Criteria**:
  - [ ] EmbeddingGenerator class
  - [ ] embed_query() for single queries
  - [ ] embed_nodes() for batch processing
  - [ ] Batch size limiting (100 per request)
  - [ ] Error handling for API failures

### TASK-013: Implement Indexing Service
- **Description**: Orchestrate the full indexing pipeline (SDD Section 4.1.2)
- **Dependencies**: TASK-008, TASK-010, TASK-011, TASK-012
- **Complexity**: High
- **Effort**: 3 hours
- **Acceptance Criteria**:
  - [ ] IndexingService class
  - [ ] start_indexing() with background processing
  - [ ] Progress tracking and callbacks
  - [ ] Error handling and recovery
  - [ ] State management (in_progress, completed, failed)

---

## Category 4: Query Engine

### TASK-014: Implement Query Service
- **Description**: Create query execution with embedding and search (SDD Section 4.1.2)
- **Dependencies**: TASK-008, TASK-012
- **Complexity**: Medium
- **Effort**: 2 hours
- **Acceptance Criteria**:
  - [ ] QueryService class
  - [ ] execute_query() method
  - [ ] is_ready() check for index state
  - [ ] Response formatting with scores and sources
  - [ ] Query timing measurement

### TASK-015: Implement Result Ranking and Filtering
- **Description**: Add similarity threshold filtering and result ranking
- **Dependencies**: TASK-014
- **Complexity**: Medium
- **Effort**: 1.5 hours
- **Acceptance Criteria**:
  - [ ] Configurable similarity threshold
  - [ ] top_k result limiting
  - [ ] Score-based ranking
  - [ ] Empty result handling

### TASK-016: Implement Query Caching (Optional)
- **Description**: Add LRU cache for query embeddings
- **Dependencies**: TASK-014
- **Complexity**: Low
- **Effort**: 1 hour
- **Acceptance Criteria**:
  - [ ] LRU cache for query embeddings
  - [ ] Cache invalidation on index updates
  - [ ] Configurable cache size

---

## Category 5: API Layer

### TASK-017: Implement FastAPI Application Scaffold
- **Description**: Create FastAPI app with lifespan management (SDD Section 4.1.1)
- **Dependencies**: TASK-006
- **Complexity**: Medium
- **Effort**: 1.5 hours
- **Acceptance Criteria**:
  - [ ] FastAPI app with title, version
  - [ ] Lifespan context manager for startup/shutdown
  - [ ] CORS middleware if needed
  - [ ] Router includes

### TASK-018: Implement Health Endpoints
- **Description**: Create /health and /health/status endpoints (SDD Section 4.1.1)
- **Dependencies**: TASK-017, TASK-009
- **Complexity**: Low
- **Effort**: 1 hour
- **Acceptance Criteria**:
  - [ ] GET /health returning HealthStatus
  - [ ] GET /health/status returning IndexingStatus
  - [ ] Proper HTTP status codes

### TASK-019: Implement Index Endpoints
- **Description**: Create POST /index and POST /index/add endpoints (SDD Section 4.1.1)
- **Dependencies**: TASK-017, TASK-013
- **Complexity**: Medium
- **Effort**: 2 hours
- **Acceptance Criteria**:
  - [ ] POST /index for new indexing jobs
  - [ ] POST /index/add for adding documents
  - [ ] Background task processing
  - [ ] Conflict detection (409 if already indexing)
  - [ ] Path validation

### TASK-020: Implement Query Endpoints
- **Description**: Create POST /query endpoint (SDD Section 4.1.1)
- **Dependencies**: TASK-017, TASK-014
- **Complexity**: Medium
- **Effort**: 1.5 hours
- **Acceptance Criteria**:
  - [ ] POST /query with QueryRequest body
  - [ ] QueryResponse with results
  - [ ] 503 if index not ready
  - [ ] 400 for invalid queries

---

## Category 6: CLI Tool

### TASK-021: Implement CLI Scaffold
- **Description**: Create Click-based CLI structure (SDD Section 4.2)
- **Dependencies**: TASK-003
- **Complexity**: Low
- **Effort**: 1 hour
- **Acceptance Criteria**:
  - [ ] Click group with subcommands
  - [ ] Help text for all commands
  - [ ] Version option

### TASK-022: Implement HTTP Client
- **Description**: Create httpx-based client for API communication
- **Dependencies**: TASK-021
- **Complexity**: Medium
- **Effort**: 1.5 hours
- **Acceptance Criteria**:
  - [ ] DocServeClient class
  - [ ] Methods for all API endpoints
  - [ ] Error handling and retries
  - [ ] Configurable base URL

### TASK-023: Implement Server Commands
- **Description**: Create server start/stop/status commands
- **Dependencies**: TASK-022
- **Complexity**: Medium
- **Effort**: 2 hours
- **Acceptance Criteria**:
  - [ ] `server start --port --host`
  - [ ] `server stop`
  - [ ] `server status`
  - [ ] Process management

### TASK-024: Implement Index and Query Commands
- **Description**: Create indexing and query commands
- **Dependencies**: TASK-022
- **Complexity**: Medium
- **Effort**: 2 hours
- **Acceptance Criteria**:
  - [ ] `index add <folder_path>`
  - [ ] `index status`
  - [ ] `query <text> --top-k --threshold`
  - [ ] Formatted output

---

## Category 7: Testing & Documentation

### TASK-025: Write Unit Tests for Core Components
- **Description**: Test settings, models, and storage layer
- **Dependencies**: TASK-006, TASK-007, TASK-008
- **Complexity**: Medium
- **Effort**: 3 hours
- **Acceptance Criteria**:
  - [ ] Settings loading tests
  - [ ] Model validation tests
  - [ ] Vector store CRUD tests
  - [ ] >80% coverage for core modules

### TASK-026: Write Unit Tests for Pipeline Components
- **Description**: Test document loader, chunker, embedding generator
- **Dependencies**: TASK-010, TASK-011, TASK-012
- **Complexity**: Medium
- **Effort**: 3 hours
- **Acceptance Criteria**:
  - [ ] Document loading tests
  - [ ] Chunking logic tests (with mocked tokenizer)
  - [ ] Embedding generation tests (with mocked API)
  - [ ] >80% coverage for pipeline modules

### TASK-027: Write Integration Tests
- **Description**: End-to-end API testing
- **Dependencies**: TASK-017, TASK-018, TASK-019, TASK-020
- **Complexity**: High
- **Effort**: 4 hours
- **Acceptance Criteria**:
  - [ ] Health endpoint tests
  - [ ] Index workflow tests
  - [ ] Query workflow tests
  - [ ] Error case testing

### TASK-028: Create Claude Code Skill Documentation
- **Description**: Write SKILL.md for Claude Code integration (SDD Section 4.3)
- **Dependencies**: TASK-020
- **Complexity**: Low
- **Effort**: 2 hours
- **Acceptance Criteria**:
  - [ ] SKILL.md with capabilities overview
  - [ ] Usage examples
  - [ ] Configuration instructions
  - [ ] Integration workflow

---

## Critical Path Analysis

```
TASK-001 → TASK-002 → TASK-006 → TASK-008 → TASK-013 → TASK-017 → TASK-019/TASK-020
           ↓
           TASK-007 → TASK-014 → TASK-020
           ↓
           TASK-010 → TASK-011 → TASK-012 → TASK-013
```

**Longest path**: 7 tasks (Setup → Config → Models → Storage → Indexing Service → API → Query Endpoint)

## Parallel Work Opportunities

After TASK-002 completes:
- **Track A**: TASK-006 → TASK-008 → TASK-013
- **Track B**: TASK-007 (can be done in parallel with Track A)
- **Track C**: TASK-003 → TASK-021 → TASK-022 (CLI can start in parallel)

## High-Complexity Tasks (Requires Extra Attention)

1. **TASK-008**: Vector Store Manager - Thread safety critical
2. **TASK-011**: Context-Aware Chunker - Token counting accuracy
3. **TASK-012**: Embedding Generator - API error handling
4. **TASK-013**: Indexing Service - State management complexity

## Implementation Order Recommendation

1. **Week 1**: TASK-001 through TASK-009 (Foundation)
2. **Week 2**: TASK-010 through TASK-016 (Pipeline & Query)
3. **Week 3**: TASK-017 through TASK-024 (API & CLI)
4. **Week 4**: TASK-025 through TASK-028 (Testing & Docs)

---

## Quick Reference

| Category | Tasks | Effort | Dependencies |
|----------|-------|--------|--------------|
| Scaffolding | 5 | ~2h | None |
| Infrastructure | 4 | ~6h | Scaffolding |
| Indexing | 4 | ~10h | Infrastructure |
| Query | 3 | ~4.5h | Infrastructure |
| API | 4 | ~6h | Indexing, Query |
| CLI | 4 | ~6.5h | Scaffolding |
| Testing | 4 | ~12h | All |
| **Total** | **28** | **~47h** | - |
