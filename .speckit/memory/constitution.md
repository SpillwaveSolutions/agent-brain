<!--
Sync Impact Report
==================
Version change: 0.0.0 → 1.0.0 (initial ratification)
Modified principles: N/A (new constitution)
Added sections:
  - Core Principles (5 principles)
  - Technology Stack
  - Development Workflow
  - Governance
Removed sections: N/A
Templates requiring updates:
  - .specify/templates/plan-template.md: ✅ compatible (Constitution Check section exists)
  - .specify/templates/spec-template.md: ✅ compatible (requirements structure aligns)
  - .specify/templates/tasks-template.md: ✅ compatible (phase structure supports modularity)
Follow-up TODOs: None
-->

# Doc-Serve Constitution

A document indexing and retrieval system providing vector search, BM25 keyword search,
and hybrid retrieval via REST API, with Claude Code skill integration.

## Core Principles

### I. Monorepo Modularity

Each package in the monorepo MUST be independently testable and releasable:

- **doc-serve-server**: FastAPI REST server - MUST have its own test suite, dependencies,
  and deployment configuration
- **doc-serve-skill**: Claude Code skill - MUST function independently given a running server
- **doc-svr-ctl**: CLI tool - MUST be installable and usable without importing server internals

Cross-package dependencies MUST flow in one direction: `skill/ctl → server` (never reverse).
Shared types or contracts MUST be defined in a shared location or duplicated explicitly.

### II. OpenAPI-First

All REST endpoints MUST be defined in an OpenAPI specification before implementation:

- Schema changes MUST be reviewed and approved before code changes
- Request/response models MUST be generated from or validated against the OpenAPI spec
- Breaking changes to the API MUST increment the major version
- The `/docs` endpoint MUST expose the interactive OpenAPI documentation

This ensures the Claude skill and CLI can reliably integrate with the server contract.

### III. Test-Alongside

Tests MUST be written during implementation, not after:

- New features MUST include tests in the same PR/commit
- Coverage MUST NOT decrease on any merge to main
- Integration tests MUST cover: indexing flow, query flow, health endpoints
- Contract tests MUST verify OpenAPI compliance

Test categories:
- **Unit tests**: Individual functions and classes
- **Integration tests**: End-to-end flows (index → query → response)
- **Contract tests**: API schema compliance

### IV. Observability

All components MUST be observable in production:

- **Health endpoints**: `/health` and `/status` MUST indicate indexing state
  (idle, indexing, ready, error)
- **Structured logging**: JSON format with correlation IDs for request tracing
- **Metrics**: Query latency, index size, embedding generation time MUST be measurable
- **Error reporting**: Failures MUST include actionable context (document path, query text,
  embedding model used)

The skill MUST be able to determine server readiness programmatically via health endpoints.

### V. Simplicity

Complexity MUST be justified and minimized:

- Start with the simplest solution that works (YAGNI)
- No premature abstractions - wait for the third use case
- Prefer standard library and well-maintained dependencies over custom solutions
- Configuration MUST have sensible defaults; advanced options are optional
- Document "why" for any non-obvious design choice

If a feature requires more than 3 new dependencies or 500+ lines of code,
it MUST be documented in the Complexity Tracking section of the implementation plan.

## Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Package Manager | Poetry | Dependency isolation per package |
| Web Framework | FastAPI | Native OpenAPI, async support |
| Vector Store | Chroma | Thread-safe, local-first |
| Indexing | LlamaIndex | Hybrid retrieval, chunking strategies |
| Embeddings | OpenAI text-embedding-3-large | Production quality, well-documented |
| Summarization | Claude (Haiku) | Context-aware chunking assistance |
| Testing | pytest | Standard, async support |

Technology changes MUST be approved via constitution amendment.

## Development Workflow

### Branch Strategy

- `main`: Protected, requires passing tests and review
- `feature/*`: Feature development branches
- `fix/*`: Bug fix branches

### PR Requirements

1. All tests pass
2. No decrease in coverage
3. OpenAPI spec updated if API changes
4. At least one approval for non-trivial changes

### Commit Messages

Follow conventional commits: `type(scope): description`
- Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`
- Scope: `server`, `skill`, `ctl`, `api`, `index`, `search`

## Governance

This constitution supersedes all other development practices for Doc-Serve.

### Amendment Process

1. Propose change via PR to this file
2. Document rationale and impact
3. Update dependent templates if principles change
4. Require explicit approval from project maintainer
5. Increment constitution version per semantic versioning:
   - MAJOR: Principle removal or incompatible redefinition
   - MINOR: New principle or significant expansion
   - PATCH: Clarification or non-semantic refinement

### Compliance

- All PRs MUST pass Constitution Check in implementation plans
- Violations MUST be documented in Complexity Tracking with justification
- Repeated unjustified violations warrant process review

**Version**: 1.0.0 | **Ratified**: 2025-12-15 | **Last Amended**: 2025-12-15
