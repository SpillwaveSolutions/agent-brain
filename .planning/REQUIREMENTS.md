# Requirements: Agent Brain

**Defined:** 2026-03-23
**Core Value:** Developers can semantically search their entire codebase and documentation through a single, fast, local-first API that understands code structure and relationships

## v1 Requirements

Requirements for v9.5.0 milestone. Each maps to roadmap phases.

### Config Validation

- [x] **CFGVAL-01**: User can run `agent-brain config validate` to check config.yaml correctness against schema
- [x] **CFGVAL-02**: Validation reports specific errors with line numbers and fix suggestions
- [x] **CFGVAL-03**: User can run config migration tool to upgrade between schema versions
- [x] **CFGVAL-04**: User can see interactive config diff showing what changed between versions
- [x] **CFGVAL-05**: Config validate integrates with setup wizard (warn on invalid config before proceeding)

### Language Support

- [ ] **LANG-01**: Object Pascal files (.pas, .pp, .dpr, .dpk) are ingested with AST-aware chunking
- [ ] **LANG-02**: Object Pascal support includes function/procedure/class extraction via tree-sitter
- [ ] **LANG-03**: File type presets include an `object-pascal` preset for --include-type shorthand

### OpenCode Installer

- [x] **OCDI-01**: OpenCode converter writes `opencode.json` with permission pre-authorization for plugin directory
- [x] **OCDI-02**: OpenCode converter uses singular directory names (agent/, command/, skill/) not plural
- [x] **OCDI-03**: Agent frontmatter fully converted: name removal, color hex, subagent_type mapping, tools object
- [x] **OCDI-04**: Path references rewritten from ~/.claude to ~/.config/opencode
- [x] **OCDI-05**: AskUserQuestion tool mapped to question in agent frontmatter conversion
- [x] **OCDI-06**: OpenCode installer is idempotent (reinstall refreshes without duplication)

### Performance

- [x] **PERF-01**: Query performance benchmark suite exists measuring latency across retrieval modes
- [x] **PERF-02**: PostgreSQL connection pool settings are tunable via config.yaml with documented defaults
- [ ] **PERF-03**: Benchmark results documented with baseline numbers for reference datasets

### Bug Fixes

- [x] **BUGFIX-01**: agent-brain start timeout defaults to 120s to support sentence-transformers first init
- [x] **BUGFIX-02**: chroma_db and cache dirs resolve relative to AGENT_BRAIN_STATE_DIR, not CWD
- [x] **BUGFIX-03**: ChromaDB telemetry PostHog capture() error suppressed on startup
- [x] **BUGFIX-04**: Gemini provider migrated from deprecated google-generativeai to google-genai package

## v2 Requirements

Deferred to future release.

### Config Advanced

- **CFGADV-01**: Config validation as pre-commit hook
- **CFGADV-02**: Config schema auto-generation from Pydantic settings model

### Language Expansion

- **LANGX-01**: Kotlin AST-aware ingestion
- **LANGX-02**: Swift AST-aware ingestion
- **LANGX-03**: Scala AST-aware ingestion

## Out of Scope

| Feature | Reason |
|---------|--------|
| Full config GUI/TUI editor | CLI-first philosophy — wizard handles interactive config |
| Automated config rollback | Config changes are manual; users can git-restore |
| OpenCode plugin marketplace registration | OpenCode doesn't have a marketplace system yet |
| GraphRAG on PostgreSQL | Deferred — stays ChromaDB-only per v6.0 decision |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| BUGFIX-01 | Phase 41 | Complete |
| BUGFIX-02 | Phase 41 | Complete |
| BUGFIX-03 | Phase 41 | Complete |
| BUGFIX-04 | Phase 41 | Complete |
| LANG-01 | Phase 42 | Pending |
| LANG-02 | Phase 42 | Pending |
| LANG-03 | Phase 42 | Pending |
| OCDI-01 | Phase 43 | Complete |
| OCDI-02 | Phase 43 | Complete |
| OCDI-03 | Phase 43 | Complete |
| OCDI-04 | Phase 43 | Complete |
| OCDI-05 | Phase 43 | Complete |
| OCDI-06 | Phase 43 | Complete |
| CFGVAL-01 | Phase 44 | Complete |
| CFGVAL-02 | Phase 44 | Complete |
| CFGVAL-03 | Phase 44 | Complete |
| CFGVAL-04 | Phase 44 | Complete |
| CFGVAL-05 | Phase 44 | Complete |
| PERF-01 | Phase 45 | Complete |
| PERF-02 | Phase 45 | Complete |
| PERF-03 | Phase 45 | Pending |

**Coverage:**
- v1 requirements: 21 total
- Mapped to phases: 21
- Unmapped: 0 (100% coverage)

---
*Requirements defined: 2026-03-23*
*Last updated: 2026-03-23 — traceability complete, all 21 requirements mapped to Phases 41-45*
