# Agent Brain Roadmap

**Created:** 2026-02-07
**Core Value:** Developers can semantically search their entire codebase and documentation through a single, fast, local-first API

## Milestones

- ✅ **v3.0 Advanced RAG** — Phases 1-4 (shipped 2026-02-10)
- ✅ **v6.0 PostgreSQL Backend** — Phases 5-10 (shipped 2026-02-13)
- ✅ **v6.0.4 Plugin & Install Fixes** — Phase 11 (shipped 2026-02-22)
- ✅ **v7.0 Index Management & Content Pipeline** — Phases 12-14 (shipped 2026-03-05)
- ✅ **v8.0 Performance & Developer Experience** — Phases 15-25 (shipped 2026-03-15)
- ✅ **v9.0 Multi-Runtime Support** — Multi-runtime converter system (shipped 2026-03-16)
- ✅ **v9.1.0 Generic Skills-Based Runtime Portability** — Phases 26-28 (shipped 2026-03-16)
- 🔧 **v9.2.0 Documentation Accuracy Audit** — Phases 29-33 (gap closure: phases 36-37 in progress)
- ⬜ **v9.3.0 LangExtract + Config Spec** — Phases 34-35
  - Phase 34: Config command spec + file watcher step (9-step wizard formalized)
  - Phase 35: LangExtract document graph extractor (multi-provider, retire LLMEntityExtractor as default)

## Phases

<details>
<summary>✅ v3.0 Advanced RAG (Phases 1-4) — SHIPPED 2026-02-10</summary>

**Full details:** [v3.0-ROADMAP.md](milestones/v3.0-ROADMAP.md)

</details>

<details>
<summary>✅ v6.0 PostgreSQL Backend (Phases 5-10) — SHIPPED 2026-02-13</summary>

**Full details:** [v6.0.4-ROADMAP.md](milestones/v6.0.4-ROADMAP.md)

</details>

<details>
<summary>✅ v6.0.4 Plugin & Install Fixes (Phase 11) — SHIPPED 2026-02-22</summary>

**Full details:** [v6.0.4-ROADMAP.md](milestones/v6.0.4-ROADMAP.md)

</details>

<details>
<summary>✅ v7.0 Index Management & Content Pipeline (Phases 12-14) — SHIPPED 2026-03-05</summary>

**Full details:** [v7.0-ROADMAP.md](milestones/v7.0-ROADMAP.md)

</details>

<details>
<summary>✅ v8.0 Performance & Developer Experience (Phases 15-25) — SHIPPED 2026-03-15</summary>

**Full details:** [v8.0-ROADMAP.md](milestones/v8.0-ROADMAP.md)

</details>

<details>
<summary>✅ v9.0 Multi-Runtime Support — SHIPPED 2026-03-16</summary>

Multi-runtime converter system with Claude, OpenCode, and Gemini support.

</details>

---

<details>
<summary>✅ v9.1.0 Generic Skills-Based Runtime Portability (Phases 26-28) — SHIPPED 2026-03-16</summary>

**Milestone Goal:** Add installer-based runtime transformation that converts Claude plugin format into skill-directory installations for Codex and any skill-based runtime.

### Phase 26: Generic Skill-Runtime Converter + Parser Extensions

**Goal:** Add `SkillRuntimeConverter` and extend parser/types to handle templates and scripts.

**Requirements:** SKILL-01 through SKILL-07, COMPAT-01, COMPAT-02, COMPAT-03

**Success Criteria:**
1. `agent-brain install-agent --agent skill-runtime --dir /tmp/test` produces skill dirs for all commands/agents/skills
2. Each SKILL.md has valid YAML frontmatter
3. Templates in assets/, scripts in scripts/
4. `--dry-run` lists planned files without writing
5. Existing converters unaffected (all existing tests pass)

**Plans:** 2 plans

Plans:
- [x] 26-01-PLAN.md — Types, parser extensions, SkillRuntimeConverter core
- [x] 26-02-PLAN.md — CLI integration, tests, dry-run support

---

### Phase 27: Codex Named Adapter + AGENTS.md Generation

**Goal:** Add `codex` as a named runtime preset built on the skill-runtime converter.

**Requirements:** CODEX-01 through CODEX-04

**Success Criteria:**
1. `agent-brain install-agent --agent codex` creates `.codex/skills/agent-brain/`
2. `AGENTS.md` generated at project root with Agent Brain section
3. Running twice doesn't duplicate the section
4. `--dry-run` shows both skill files and AGENTS.md

**Plans:** 1 plan

Plans:
- [x] 27-01-PLAN.md — CodexConverter, AGENTS.md generation, CLI integration, tests

---

### Phase 28: Documentation, Testing & Plan Archival

**Goal:** Comprehensive tests, docs, plan archival, version bump.

**Requirements:** DOC-01 through DOC-03, COMPAT-01, COMPAT-02

**Success Criteria:**
1. `task before-push` passes
2. `task pr-qa-gate` passes
3. All 5 converters tested against real plugin directory
4. Plan archived in docs/plans/

**Plans:** 1 plan

Plans:
- [x] 28-01-PLAN.md — Integration tests, user guide, CLAUDE.md updates

</details>

---

## v9.2.0 Documentation Accuracy Audit (Phases 29-33)

**Milestone Goal:** Ensure all documentation accurately reflects current software behavior — CLI commands, configuration schemas, APIs, examples, file paths, and installation instructions — serving as the quality gate before release.

- [x] **Phase 29: CLI & API Documentation** — Audit and fix CLI command docs and API endpoint docs (completed 2026-03-17)
- [x] **Phase 30: Configuration Documentation** — Audit and fix YAML config and environment variable docs
- [x] **Phase 31: User Guides** — Audit and fix all user-facing guides for v7-v9 feature accuracy
- [x] **Phase 32: Plugin Documentation** — Audit and fix plugin commands, skills, and agent descriptions (completed 2026-03-17)
- [x] **Phase 33: Cross-References & Metadata** — Verify all internal links, file paths, and add audit metadata (completed 2026-03-17)
- [x] **Phase 36: Fix Documentation Accuracy** — Close audit gaps: stale .agent-brain/ paths, config.json example, GRAPHRAG multi-mode claim (completed 2026-03-20)
- [x] **Phase 37: Complete Link Verification & Audit Metadata** — Fix anchor link bug, broken ToC links, stamp SKILL.md files, write VERIFICATION.md for phases 29-33 (completed 2026-03-19)
- [x] **Phase 38: Server Reliability & Provider Fixes** — Fix CWD-relative chroma_db/cache dirs, Broken pipe Ollama indexing, reranker start timeout, ChromaDB telemetry noise, Gemini provider migration, merge Object Pascal PR #115 (completed 2026-03-20)
- [x] **Phase 39: Plugin & Setup Wizard UX** — Fix setup-assistant permission gaps, eliminate approval fatigue, add AST+LangExtract GraphRAG option to wizard Step 7, auto-discover port in wizard Step 12 (completed 2026-03-20)

## Phase Details

### Phase 29: CLI & API Documentation

**Goal:** All CLI command documentation and API endpoint documentation accurately reflect current software behavior.
**Depends on:** Nothing (first phase of milestone)
**Requirements:** CLIDOC-01, CLIDOC-02, CLIDOC-03, CLIDOC-04
**Success Criteria** (what must be TRUE):
  1. Every CLI subcommand documented in docs matches the output of `agent-brain --help` and subcommand `--help` flags
  2. All 5 runtime installation commands (install-agent) are documented with correct syntax and options
  3. Every API endpoint documented in API reference matches the OpenAPI spec produced by the running server
  4. Job queue commands (`jobs`, `jobs --watch`, `jobs JOB_ID`, `jobs JOB_ID --cancel`) are documented accurately
**Plans:** 2/2 plans complete

Plans:
- [ ] 29-01-PLAN.md — CLI command documentation audit (--help vs docs)
- [ ] 29-02-PLAN.md — API endpoint documentation audit (source code vs API_REFERENCE.md)

---

### Phase 30: Configuration Documentation

**Goal:** All YAML configuration fields and environment variable documentation accurately reflect the source code schema definitions and actual runtime behavior.
**Depends on:** Phase 29
**Requirements:** CFGDOC-01, CFGDOC-02, CFGDOC-03
**Success Criteria** (what must be TRUE):
  1. Every YAML key documented in configuration reference matches a field in the server's Pydantic settings schema
  2. Every environment variable listed in docs matches a variable actually read by the server or CLI source code
  3. All 7 provider configurations (OpenAI, Anthropic, Ollama, Cohere, Gemini, Grok, SentenceTransformers) are documented with correct YAML structure
**Plans:** 2/2 plans complete

Plans:
- [x] 30-01-PLAN.md — YAML config fields and env var audit (settings.py vs CONFIGURATION.md + CLAUDE.md)
- [x] 30-02-PLAN.md — Provider configuration audit (provider_config.py vs PROVIDER_CONFIGURATION.md)

---

### Phase 31: User Guides

**Goal:** All user-facing guides accurately reflect v7-v9 features so a new user can follow them from start to finish without encountering stale instructions.
**Depends on:** Phase 30
**Requirements:** GUIDE-01, GUIDE-02, GUIDE-03, GUIDE-04, GUIDE-05
**Success Criteria** (what must be TRUE):
  1. USER_GUIDE.md reflects folder management, file type presets, content injection, eviction, file watcher, embedding cache, and multi-runtime install features
  2. QUICK_START.md installation steps execute successfully on a clean machine without errors or missing steps
  3. PLUGIN_GUIDE.md accurately describes all current plugin slash commands, agents, and skills
  4. POSTGRESQL_SETUP.md Docker Compose instructions produce a working PostgreSQL backend when followed
  5. GRAPHRAG_GUIDE.md query examples return results consistent with current graph query behavior
**Plans:** 2/2 plans complete

Plans:
- [x] 31-01-PLAN.md — Update USER_GUIDE.md and QUICK_START.md with v7-v9 features
- [x] 31-02-PLAN.md — Update PLUGIN_GUIDE.md, POSTGRESQL_SETUP.md, and GRAPHRAG_GUIDE.md

---

### Phase 32: Plugin Documentation

**Goal:** All plugin command files, skill reference guides, and agent descriptions accurately reflect current CLI and backend capabilities.
**Depends on:** Phase 31
**Requirements:** PLUGDOC-01, PLUGDOC-02, PLUGDOC-03
**Success Criteria** (what must be TRUE):
  1. All 30+ plugin command files contain descriptions and usage examples that match current CLI behavior
  2. Plugin skill reference guides list current features including file watcher, embedding cache, and multi-runtime install
  3. Plugin agent descriptions (researcher, indexer) match the actual capabilities and available tools in the current implementation
**Plans:** 3/3 plans complete

Plans:
- [x] 32-01-PLAN.md — Audit plugin command files A-K (bm25 through keyword, 15 files)
- [x] 32-02-PLAN.md — Audit plugin command files L-Z (list through version, 15 files)
- [x] 32-03-PLAN.md — Audit skill reference guides (16 files) and agent descriptions (3 files)

---

### Phase 33: Cross-References & Metadata

**Goal:** All internal documentation links resolve correctly, all referenced file paths exist, and audited files carry audit metadata for future validation tracking.
**Depends on:** Phase 32
**Requirements:** XREF-01, XREF-02, XREF-03
**Success Criteria** (what must be TRUE):
  1. Every internal link in audited docs (`[text](path)`) resolves to an existing file or anchor
  2. Every file path referenced in code examples, installation steps, and configuration examples exists in the repository
  3. Every audited documentation file has a `last_validated` frontmatter field set to the audit date
**Plans:** 2/2 plans complete

Plans:
- [x] 33-01-PLAN.md — Scan and fix broken internal links and file path references
- [x] 33-02-PLAN.md — Add last_validated frontmatter metadata to all audited docs

---

### Phase 36: Fix Documentation Accuracy

**Goal:** All stale directory path references and inaccurate behavioral claims in documentation are corrected so users following any doc from start to finish will not encounter wrong paths or misleading instructions.
**Depends on:** Phase 33 (audit identified the gaps)
**Requirements:** CFGDOC-01, GUIDE-02, GUIDE-03, GUIDE-05
**Gap Closure:** Closes gaps from v10.0 audit
**Success Criteria** (what must be TRUE):
  1. `docs/CONFIGURATION.md` config.json example documents actual fields written by `agent-brain init` (bind_host, port_range_start, port_range_end, auto_port, chunk_size, chunk_overlap, exclude_patterns)
  2. All stale `.claude/agent-brain/` path references replaced with `.agent-brain/` in CONFIGURATION.md, QUICK_START.md, and PLUGIN_GUIDE.md
  3. `docs/GRAPHRAG_GUIDE.md` corrected to state that `multi` mode gracefully adapts to non-ChromaDB backends (does not require ChromaDB)
  4. QUICK_START.md init flow and GRAPHRAG multi+PostgreSQL flow can be followed without inaccurate instructions
**Plans:** 2/2 plans complete

Plans:
- [ ] 36-01-PLAN.md — Fix stale .agent-brain/ paths in CONFIGURATION.md, QUICK_START.md, PLUGIN_GUIDE.md
- [ ] 36-02-PLAN.md — Fix config.json example fields in CONFIGURATION.md and correct GRAPHRAG_GUIDE.md multi-mode claim

---

### Phase 37: Complete Link Verification & Audit Metadata

**Goal:** The Phase 33 link verification script correctly checks all link types (including same-file anchors), broken ToC links in DEVELOPERS_GUIDE.md are fixed, SKILL.md root files receive audit metadata, and all milestone phases (29–33) have VERIFICATION.md files.
**Depends on:** Phase 36
**Requirements:** XREF-01, XREF-03
**Gap Closure:** Closes gaps from v10.0 audit
**Success Criteria** (what must be TRUE):
  1. `scripts/check_doc_links.py` correctly verifies same-file anchor links (the `is_url('#')` bug is fixed)
  2. All ToC anchors in `docs/DEVELOPERS_GUIDE.md` resolve to existing headings
  3. `agent-brain-plugin/skills/using-agent-brain/SKILL.md` and `agent-brain-plugin/skills/configuring-agent-brain/SKILL.md` have `last_validated` frontmatter
  4. VERIFICATION.md files exist for all 5 milestone phases (29, 30, 31, 32, 33)
**Plans:** 2/2 plans complete

Plans:
- [ ] 37-01-PLAN.md — Fix check_doc_links.py anchor bug, fix DEVELOPERS_GUIDE.md ToC anchors, stamp SKILL.md files
- [ ] 37-02-PLAN.md — Write VERIFICATION.md for phases 29–33

---

### Phase 38: Server Reliability & Provider Fixes

**Goal:** All known server-side bugs and provider deprecation issues are resolved so that Agent Brain runs stably under concurrent indexing load, resolves state directories correctly, starts without noise, and supports current provider APIs.
**Depends on:** Phase 37
**Requirements:** None (todo-driven bug fixes)
**Todos closed:** Fix chroma_db/cache CWD bug, Fix Broken pipe Ollama indexing, Fix start timeout for sentence-transformers reranker, Suppress ChromaDB telemetry PostHog error, Migrate Gemini provider to google-genai, Review and merge Object Pascal PR #115
**Success Criteria** (what must be TRUE):
  1. `chroma_db/` and `cache/` directories are created inside `AGENT_BRAIN_STATE_DIR`, not relative to CWD
  2. Indexing jobs with Ollama as embedding provider complete without Broken pipe errors under sequential load
  3. `agent-brain start` succeeds with sentence-transformers reranker without timeout errors on first init
  4. Server starts without ChromaDB PostHog telemetry errors in logs
  5. Gemini summarization provider uses `google-genai` package (no deprecation warnings)
  6. Object Pascal files are indexed correctly (PR #115 merged or equivalent changes applied)
**Plans:** 4/4 plans complete

Plans:
- [ ] 38-01-PLAN.md — Fix chroma_db/cache dirs (CWD → AGENT_BRAIN_STATE_DIR) + suppress ChromaDB telemetry error
- [ ] 38-02-PLAN.md — Fix Broken pipe Ollama indexing + Fix start timeout for sentence-transformers reranker
- [ ] 38-03-PLAN.md — Migrate Gemini provider to google-genai + merge/apply Object Pascal PR #115
- [ ] 38-04-PLAN.md — Add config wizard sub-command for Ollama batch_size and request_delay_ms

---

### Phase 39: Plugin & Setup Wizard UX

**Goal:** The setup wizard and plugin commands work without approval fatigue, have correct permission configurations, and offer AST+LangExtract as a first-class GraphRAG extraction option with automatic port discovery.
**Depends on:** Phase 38
**Requirements:** None (todo-driven UX improvements)
**Todos closed:** Fix setup-assistant permission gaps, Eliminate approval fatigue in setup commands, Add AST+LangExtract GraphRAG option to wizard Step 7, Auto-discover port in wizard Step 12
**Success Criteria** (what must be TRUE):
  1. setup-assistant agent has scoped Bash permission for scripts and Write/Edit permission for `~/.agent-brain/**` config paths
  2. `agent-brain-config` and `agent-brain-install` commands complete without triggering manual approval prompts for expected operations
  3. Wizard Step 7 offers "AST for code + LangExtract for docs" as an explicit, selectable GraphRAG extraction mode
  4. Wizard Step 12 auto-discovers an available port from the configured range instead of requiring manual input
**Plans:** 2/2 plans complete

Plans:
- [ ] 39-01-PLAN.md — Fix setup-assistant permission gaps + eliminate approval fatigue in setup commands
- [ ] 39-02-PLAN.md — Add AST+LangExtract wizard option (Step 7) + auto-discover port (Step 12)

---

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1-4 | v3.0 | 15/15 | Complete | 2026-02-10 |
| 5-10 | v6.0 | 12/12 | Complete | 2026-02-13 |
| 11 | v6.0.4 | 1/1 | Complete | 2026-02-22 |
| 12-14 | v7.0 | 7/7 | Complete | 2026-03-05 |
| 15-25 | v8.0 | 9/9 | Complete | 2026-03-15 |
| - | v9.0 | - | Complete | 2026-03-16 |
| 26 | v9.1.0 | 2/2 | Complete | 2026-03-16 |
| 27 | v9.1.0 | 1/1 | Complete | 2026-03-16 |
| 28 | v9.1.0 | 1/1 | Complete | 2026-03-16 |
| 29 | 2/2 | Complete    | 2026-03-17 | - |
| 30 | v9.2.0 | Complete    | 2026-03-17 | 2026-03-17 |
| 31 | 2/2 | Complete    | 2026-03-17 | 2026-03-17 |
| 32 | v9.2.0 | Complete    | 2026-03-17 | 2026-03-17 |
| 33 | v9.2.0 | Complete    | 2026-03-17 | 2026-03-17 |
| 34 | v9.3.0 | 0 plans     | Complete   | 2026-03-17 |
| 35 | v9.3.0 | 0 plans     | Complete   | 2026-03-17 |
| 36 | 2/2 | Complete   | 2026-03-20 | - |
| 37 | 2/2 | Complete    | 2026-03-19 | - |
| 38 | 4/4 | Complete    | 2026-03-20 | - |
| 39 | 2/2 | Complete   | 2026-03-20 | - |

---
*Roadmap created: 2026-02-07*
*Last updated: 2026-03-19 — Added phases 38-39 from todo backlog (10 todos captured into 2 phases)*
