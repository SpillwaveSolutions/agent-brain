# Agent Brain v9.1.0 — Generic Skills-Based Runtime Portability Requirements

**Milestone:** v9.1.0
**Goal:** Add installer-based runtime transformation that converts Claude plugin format into skill-directory installations for Codex and any skill-based runtime.
**Created:** 2026-03-16

## v9.1.0 Requirements

### Generic Skill-Runtime Converter (SKILL)

- [ ] **SKILL-01**: `install-agent --agent skill-runtime --dir <path>` converts all plugin artifacts into skill directories
- [ ] **SKILL-02**: Commands become individual skill directories with SKILL.md and shell wrapper scripts
- [ ] **SKILL-03**: Agents become orchestration skill directories referencing dependent skills
- [ ] **SKILL-04**: Existing skills copied with references intact
- [ ] **SKILL-05**: Templates and scripts included as skill assets
- [ ] **SKILL-06**: `--dir` is required for skill-runtime target (no default)
- [ ] **SKILL-07**: Parser extracts templates and scripts into PluginBundle

### Codex Named Adapter (CODEX)

- [ ] **CODEX-01**: `install-agent --agent codex` installs to `.codex/skills/agent-brain/`
- [ ] **CODEX-02**: AGENTS.md generated/updated at project root with Agent Brain guidance
- [ ] **CODEX-03**: AGENTS.md update is idempotent (HTML comment markers)
- [ ] **CODEX-04**: Codex skills include invocation guidance headers

### Compatibility (COMPAT)

- [ ] **COMPAT-01**: Existing claude/opencode/gemini converters unaffected
- [ ] **COMPAT-02**: All existing tests continue to pass
- [ ] **COMPAT-03**: `--dry-run` works for skill-runtime and codex targets

### Documentation (DOC)

- [ ] **DOC-01**: User guide covers skill-runtime and codex installation
- [ ] **DOC-02**: Developer guide explains adding new converters
- [ ] **DOC-03**: Original plan spec archived in docs/plans/

## Traceability

| REQ-ID | Phase | Status |
|--------|-------|--------|
| SKILL-01 | Phase 26 | Pending |
| SKILL-02 | Phase 26 | Pending |
| SKILL-03 | Phase 26 | Pending |
| SKILL-04 | Phase 26 | Pending |
| SKILL-05 | Phase 26 | Pending |
| SKILL-06 | Phase 26 | Pending |
| SKILL-07 | Phase 26 | Pending |
| CODEX-01 | Phase 27 | Pending |
| CODEX-02 | Phase 27 | Pending |
| CODEX-03 | Phase 27 | Pending |
| CODEX-04 | Phase 27 | Pending |
| COMPAT-01 | Phase 26 | Pending |
| COMPAT-02 | Phase 26 | Pending |
| COMPAT-03 | Phase 26 | Pending |
| DOC-01 | Phase 28 | Pending |
| DOC-02 | Phase 28 | Pending |
| DOC-03 | Phase 28 | Pending |

## Out of Scope

- **MCP Server**: User prefers Skill + CLI model
- **Cursor/Qwen specific adapters**: Users use `--agent skill-runtime --dir` for these
- **Codex TOML config generation**: Not needed — Codex uses skills, not agent configs
