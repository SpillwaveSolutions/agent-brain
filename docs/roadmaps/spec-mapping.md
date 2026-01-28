# Doc-Serve Spec Mapping

**Version:** 1.1.0
**Last Updated:** 2026-01-28

Maps product roadmap phases to specification directories for traceability.

---

## Phase to Spec Directory Mapping

| Phase | Roadmap Section | Spec Directory | Status      | Priority |
|-------|-----------------|----------------|-------------|----------|
| 1 | Core Document RAG | `specs/001-005/` | COMPLETED   | - |
| 2 | BM25 & Hybrid Retrieval | `specs/100-bm25-hybrid-retrieval/` | COMPLETED   | P1 |
| 3 | Source Code Ingestion | `specs/101-code-ingestion/` | COMPLETED   | P2 |
| 3.1 | Multi-Instance Architecture | `.speckit/features/109-multi-instance-architecture/` | COMPLETED | P1 |
| 3.2 | C# Code Indexing | `.speckit/features/110-csharp-code-indexing/` | COMPLETED | P2 |
| 3.3 | Skill Instance Discovery | `.speckit/features/111-skill-instance-discovery/` | DRAFT | P2 |
| 4 | UDS & Claude Plugin | `specs/102-uds-claude-plugin/` | Future      | P3 |
| 5 | Pluggable Providers | `specs/103-pluggable-providers/` | NEXT        | P3 |
| 6 | PostgreSQL/AlloyDB | `specs/104-postgresql-backend/` | Future      | P4 |
| 7 | AWS Bedrock | `specs/105-aws-bedrock/` | Future      | P4 |
| 8 | Google Vertex AI | `specs/106-vertex-ai/` | Future      | P4 |

---

## Phase 1 Specs (Completed)

These specs represent the completed Phase 1 work:

| Spec ID | Name | Status | Description |
|---------|------|--------|-------------|
| 001 | Phase 1 Core Server | Implemented | FastAPI server with vector search |
| 002 | CLI Tool | Implemented | doc-svr-ctl management CLI |
| 003 | CLI Entry Points | Implemented | Package entry point configuration |
| 004 | Taskfile Support | Implemented | Task runner integration |
| 005 | Deprecation Fixes | Implemented | Pydantic V2, pytest-asyncio updates |

---

## Roadmap Specs (100-Series)

These specs represent upcoming phases from the product roadmap:

| Spec ID | Phase | Name | Artifacts |
|---------|-------|------|-----------|
| 100 | 2 | BM25 & Hybrid Retrieval | spec.md, plan.md, tasks.md, quickstart.md, research.md, data-model.md |
| 101 | 3 | Source Code Ingestion | spec.md, plan.md, tasks.md |
| 102 | 4 | UDS & Claude Plugin | spec.md, plan.md (pending), tasks.md (pending) |
| 103 | 5 | Pluggable Providers | spec.md, plan.md (pending), tasks.md (pending) |
| 104 | 6 | PostgreSQL/AlloyDB Backend | spec.md, plan.md (pending), tasks.md (pending) |
| 105 | 7 | AWS Bedrock Provider | spec.md, plan.md (pending), tasks.md (pending) |
| 106 | 8 | Vertex AI Provider | spec.md, plan.md (pending), tasks.md (pending) |

---

## Feature Specs (109-Series)

These specs represent features implemented via Spec-Driven Development:

| Spec ID | Phase | Name | Status | Artifacts |
|---------|-------|------|--------|-----------|
| 109 | 3.1 | Multi-Instance Architecture | COMPLETED | spec.md, plan.md, tasks.md, quickstart.md, research.md, data-model.md |
| 110 | 3.2 | C# Code Indexing | COMPLETED | spec.md, plan.md, tasks.md, quickstart.md, research.md |
| 111 | 3.3 | Skill Instance Discovery | DRAFT | spec.md, tasks.md |

---

## Numbering Convention

| Range | Purpose | Example |
|-------|---------|---------|
| 001-099 | Phase 1 specs (original features) | `001-phase1-core-server` |
| 100-199 | Roadmap phases 2-8 | `100-bm25-hybrid-retrieval` |
| 200-299 | Reserved for future phases | - |
| 300+ | Reserved for expansion | - |

---

## Spec Artifacts

Each spec directory should contain:

| File | Purpose | Created By |
|------|---------|------------|
| `spec.md` | Feature specification with user stories | `/speckit.specify` or manual |
| `plan.md` | Implementation plan with steps | `/speckit.plan` |
| `tasks.md` | Actionable task breakdown | `/speckit.tasks` |
| `research.md` | Optional research notes | Manual |
| `checklists/` | Optional quality checklists | `/speckit.checklist` |

---

## Workflow

### Creating New Spec from Roadmap

1. Identify the phase from `product-roadmap.md`
2. Create spec directory: `specs/1XX-feature-name/`
3. Create `spec.md` using template or `/speckit.specify`
4. Generate plan: `/speckit.plan`
5. Generate tasks: `/speckit.tasks`

### Implementing a Spec

1. Create feature branch: `git checkout -b 1XX-feature-name`
2. Follow tasks in `tasks.md`
3. Update spec status when complete
4. Update this mapping document

---

## References

- **Product Roadmap:** `docs/roadmaps/product-roadmap.md`
- **Spec Template:** `.specify/templates/spec-template.md`
- **Constitution:** `.specify/memory/constitution.md`
