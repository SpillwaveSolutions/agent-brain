# Requirements: Agent Brain

**Defined:** 2026-03-31
**Core Value:** Developers can semantically search their entire codebase and documentation through a single, fast, local-first API that understands code structure and relationships

## v1 Requirements

Requirements for v9.6.0 Runtime Support Parity & Backlog Cleanup. Each maps to roadmap phases.

### Test Isolation

- [ ] **ISO-01**: Developer can run runtime parity integration tests that install Agent Brain only inside repo-owned project fixtures and temporary paths, never user-global runtime config directories
- [ ] **ISO-02**: Developer can verify the generated project-local install tree for each runtime before headless CLI execution begins

### Codex Runtime

- [ ] **CODEX-01**: Developer can install Agent Brain into an isolated project directory for Codex and verify `.codex/skills/agent-brain/` plus `AGENTS.md` were generated in that project
- [ ] **CODEX-02**: Developer can invoke Codex headlessly from the isolated project and receive JSON status showing an installed Agent Brain skill or setup flow executed successfully

### OpenCode Runtime

- [ ] **OPEN-01**: Developer can install Agent Brain into an isolated project directory for OpenCode and verify `.opencode/plugins/agent-brain/` plus project-local `opencode.json` permission entries were generated
- [ ] **OPEN-02**: Developer can invoke OpenCode headlessly from the isolated project and receive JSON status showing an installed Agent Brain skill or setup flow executed successfully

### Gemini Runtime

- [ ] **GCLI-01**: Developer can install Agent Brain into an isolated project directory for Gemini CLI and verify `.gemini/plugins/agent-brain/` was generated in that project
- [ ] **GCLI-02**: Developer can invoke Gemini headlessly from the isolated project and receive JSON status showing an installed Agent Brain skill or setup flow executed successfully

### Runtime Hygiene

- [ ] **PARITY-01**: Runtime parity tests report unavailable CLIs, install verification failures, and malformed JSON as explicit per-runtime failures instead of silently skipping
- [ ] **PARITY-02**: Runtime-related pending todos and planning artifacts accurately reflect shipped Codex, OpenCode, and Gemini support with completed work removed from pending state

## v2 Requirements

Deferred to future release.

### CI Expansion

- **CI-01**: Runtime parity suite runs in CI with Codex, OpenCode, and Gemini CLIs provisioned automatically
- **CI-02**: Disposable-home global-install smoke tests exist for supported runtimes without touching a developer's real home directory

### Runtime Expansion

- **CLAUDE-01**: Claude runtime installation and headless invocation join the same parity matrix used for Codex, OpenCode, and Gemini

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Real global installs to `~/.codex`, `~/.config/opencode`, or `~/.config/gemini` during tests | User explicitly wants parity tests to protect the existing local environment |
| Interactive/manual runtime sessions | Milestone focuses on deterministic headless execution with machine-verifiable JSON status |
| New runtime adapters beyond Codex, OpenCode, and Gemini | The goal is parity for the currently targeted code-agent runtimes, not adapter expansion |
| New Gemini provider features unrelated to runtime parity | Current milestone scope is installation/execution parity, not provider capability expansion |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| ISO-01 | Phase 46 | Pending |
| ISO-02 | Phase 46 | Pending |
| PARITY-01 | Phase 46 | Pending |
| CODEX-01 | Phase 47 | Pending |
| CODEX-02 | Phase 47 | Pending |
| OPEN-01 | Phase 48 | Pending |
| OPEN-02 | Phase 48 | Pending |
| GCLI-01 | Phase 49 | Pending |
| GCLI-02 | Phase 49 | Pending |
| PARITY-02 | Phase 49 | Pending |

**Coverage:**
- v1 requirements: 10 total
- Mapped to phases: 10
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-31*
*Last updated: 2026-03-31 after initial definition for v9.6.0*
