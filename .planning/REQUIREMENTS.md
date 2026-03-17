# Requirements: Agent Brain v9.2.0 Documentation Accuracy Audit

**Defined:** 2026-03-16
**Core Value:** Developers can semantically search their entire codebase and documentation through a single, fast, local-first API that understands code structure and relationships

## v9.2.0 Requirements

Requirements for documentation accuracy audit. Each maps to roadmap phases.

### CLI & API Documentation

- [ ] **CLIDOC-01**: CLI root and all subcommand docs match `agent-brain --help` output
- [ ] **CLIDOC-02**: Runtime installation commands (install-agent) documented for all 5 runtimes
- [ ] **CLIDOC-03**: API endpoint docs match OpenAPI spec and source code
- [ ] **CLIDOC-04**: Job queue commands documented accurately

### Configuration Documentation

- [ ] **CFGDOC-01**: YAML configuration fields match source schema definitions
- [ ] **CFGDOC-02**: Environment variable docs match actual env var usage in code
- [ ] **CFGDOC-03**: Provider configuration docs match pluggable provider implementations

### User Guides

- [ ] **GUIDE-01**: USER_GUIDE.md reflects current CLI and features (v7-v9)
- [ ] **GUIDE-02**: QUICK_START.md installation steps verified working
- [ ] **GUIDE-03**: PLUGIN_GUIDE.md matches current plugin commands/agents/skills
- [ ] **GUIDE-04**: POSTGRESQL_SETUP.md verified against Docker Compose setup
- [ ] **GUIDE-05**: GRAPHRAG_GUIDE.md matches current graph query behavior

### Plugin Documentation

- [ ] **PLUGDOC-01**: All 30+ plugin command files match CLI behavior
- [ ] **PLUGDOC-02**: Plugin skill reference guides match current features
- [ ] **PLUGDOC-03**: Plugin agent descriptions match current capabilities

### Cross-References & Metadata

- [ ] **XREF-01**: All internal doc links resolve correctly
- [ ] **XREF-02**: File paths referenced in docs exist
- [ ] **XREF-03**: Audited docs have last_validated frontmatter

## Future Requirements

### Automated Documentation Testing

- **AUTODOC-01**: CI job that validates CLI --help against docs
- **AUTODOC-02**: Link checker in pre-push pipeline
- **AUTODOC-03**: Schema-to-docs diff detection

## Out of Scope

| Feature | Reason |
|---------|--------|
| Rewriting docs from scratch | Audit and fix, not rewrite |
| docs/plans/ audit | Historical plans are point-in-time artifacts, not user-facing |
| docs/design/ rewrite | Design docs are architectural records, only fix broken links |
| .claude/agents/ rewrite | Internal agent configs, not user documentation |
| New documentation creation | Only fix existing docs, no new guides |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CLIDOC-01 | Phase 29 | Pending |
| CLIDOC-02 | Phase 29 | Pending |
| CLIDOC-03 | Phase 29 | Pending |
| CLIDOC-04 | Phase 29 | Pending |
| CFGDOC-01 | Phase 30 | Pending |
| CFGDOC-02 | Phase 30 | Pending |
| CFGDOC-03 | Phase 30 | Pending |
| GUIDE-01 | Phase 31 | Pending |
| GUIDE-02 | Phase 31 | Pending |
| GUIDE-03 | Phase 31 | Pending |
| GUIDE-04 | Phase 31 | Pending |
| GUIDE-05 | Phase 31 | Pending |
| PLUGDOC-01 | Phase 32 | Pending |
| PLUGDOC-02 | Phase 32 | Pending |
| PLUGDOC-03 | Phase 32 | Pending |
| XREF-01 | Phase 33 | Pending |
| XREF-02 | Phase 33 | Pending |
| XREF-03 | Phase 33 | Pending |

**Coverage:**
- v9.2.0 requirements: 18 total
- Mapped to phases: 18
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-16*
*Last updated: 2026-03-16 — Traceability confirmed, roadmap phases 29-33 created*
