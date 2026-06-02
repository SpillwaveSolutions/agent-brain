# Agent Brain Roadmap

**Created:** 2026-02-07
**Core Value:** Developers can semantically search their entire codebase and documentation through a single, fast, local-first API that understands code structure and relationships

## Milestones

- ✅ **v3.0 Advanced RAG** — Phases 1-4 (shipped 2026-02-10)
- ✅ **v6.0 PostgreSQL Backend** — Phases 5-10 (shipped 2026-02-13)
- ✅ **v6.0.4 Plugin & Install Fixes** — Phase 11 (shipped 2026-02-22)
- ✅ **v7.0 Index Management & Content Pipeline** — Phases 12-14 (shipped 2026-03-05)
- ✅ **v8.0 Performance & Developer Experience** — Phases 15-25 (shipped 2026-03-15)
- ✅ **v9.0 Multi-Runtime Support** — Multi-runtime converter system (shipped 2026-03-16)
- ✅ **v9.1.0 Generic Skills-Based Runtime Portability** — Phases 26-28 (shipped 2026-03-16)
- ✅ **v9.4.0 Documentation Accuracy Audit & Reliability Closure** — Phases 29-33 + gap closure phases 36-40 (shipped 2026-03-20)
- ✅ **v9.3.0 LangExtract + Config Spec** — Phases 34-35 (shipped 2026-03-22)
- ✅ **v9.5.0 Config Validation & Language Support** — Phases 41-45 (shipped 2026-03-31)
- 🚧 **v9.6.0 Runtime Support Parity & Backlog Cleanup** — Phases 46-49 (in progress)

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

<details>
<summary>✅ v9.4.0 Documentation Accuracy Audit & Reliability Closure (Phases 29-33, 36-40) — SHIPPED 2026-03-20</summary>

**Full details:** [v9.4.0-ROADMAP.md](milestones/v9.4.0-ROADMAP.md)

</details>

---

<details>
<summary>✅ v9.3.0 LangExtract + Config Spec (Phases 34-35) — SHIPPED 2026-03-22</summary>

**Full details:** [v9.3.0-ROADMAP.md](milestones/v9.3.0-ROADMAP.md)

</details>

---

<details>
<summary>✅ v9.5.0 Config Validation & Language Support (Phases 41-45) — SHIPPED 2026-03-31</summary>

**Full details:** [v9.5.0-ROADMAP.md](milestones/v9.5.0-ROADMAP.md)

</details>

---

## v9.6.0 Runtime Support Parity & Backlog Cleanup (Phases 46-49)

**Milestone Goal:** Guarantee project-local, headless, JSON-verifiable end-to-end install parity for Codex, OpenCode, and Gemini without mutating the operator's global runtime environment.

### Phases

- [ ] **Phase 46: Project-Local Runtime Install Harness** — Shared integration folders, install verification, and failure reporting for runtime parity tests
- [ ] **Phase 47: Codex Runtime E2E Parity** — Project-local install plus headless Codex execution for installed Agent Brain skills
- [ ] **Phase 48: OpenCode Runtime E2E Parity** — Project-local install plus headless OpenCode execution for installed Agent Brain skills
- [ ] **Phase 49: Gemini Runtime E2E Parity & Backlog Cleanup** — Project-local install plus headless Gemini execution, then reconcile stale runtime planning artifacts

### Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 46. Project-Local Runtime Install Harness | 0/2 | Not started | - |
| 47. Codex Runtime E2E Parity | 0/2 | Not started | - |
| 48. OpenCode Runtime E2E Parity | 0/2 | Not started | - |
| 49. Gemini Runtime E2E Parity & Backlog Cleanup | 0/2 | Not started | - |

## Phase Details

### Phase 46: Project-Local Runtime Install Harness
**Goal**: Runtime parity tests have repo-owned integration projects, shared install verification, and explicit failure modes before any external CLI is invoked
**Depends on**: Nothing (first phase of milestone)
**Requirements**: ISO-01, ISO-02, PARITY-01
**Success Criteria** (what must be TRUE):
  1. Repo-owned integration project directories exist for runtime parity tests and are the only install targets used by the new suite
  2. Shared helpers verify expected install artifacts exist before runtime CLI execution begins
  3. Missing CLIs, malformed JSON, or accidental global install paths fail with explicit runtime-specific messages
**Plans**: 2 plans

Plans:
- [ ] 46-01-PLAN.md — Integration project fixtures + project-local install target plumbing
- [ ] 46-02-PLAN.md — Shared install verification + JSON status/error-reporting helpers

---

### Phase 47: Codex Runtime E2E Parity
**Goal**: Codex can install Agent Brain into an isolated project and execute an installed skill headlessly with JSON-verifiable status
**Depends on**: Phase 46
**Requirements**: CODEX-01, CODEX-02
**Success Criteria** (what must be TRUE):
  1. `agent-brain install-agent --agent codex --project --path <integration-dir>` writes `.codex/skills/agent-brain/` and `AGENTS.md` inside the integration project
  2. A headless Codex run from the integration project can invoke an installed Agent Brain skill or setup flow
  3. The Codex test records a JSON status payload that distinguishes install failure, execution failure, and success
**Plans**: 2 plans

Plans:
- [ ] 47-01-PLAN.md — Codex project-local install verification
- [ ] 47-02-PLAN.md — Codex headless execution + JSON status assertions

---

### Phase 48: OpenCode Runtime E2E Parity
**Goal**: OpenCode can install Agent Brain into an isolated project and execute an installed skill headlessly with JSON-verifiable status
**Depends on**: Phase 46
**Requirements**: OPEN-01, OPEN-02
**Success Criteria** (what must be TRUE):
  1. `agent-brain install-agent --agent opencode --project --path <integration-dir>` writes `.opencode/plugins/agent-brain/` and project-local `opencode.json` entries inside the integration project
  2. A headless OpenCode run from the integration project can invoke an installed Agent Brain skill or setup flow
  3. The OpenCode test records a JSON status payload and verifies no user-global OpenCode config paths were mutated
**Plans**: 2 plans

Plans:
- [ ] 48-01-PLAN.md — OpenCode project-local install verification
- [ ] 48-02-PLAN.md — OpenCode headless execution + JSON status assertions

---

### Phase 49: Gemini Runtime E2E Parity & Backlog Cleanup
**Goal**: Gemini can install Agent Brain into an isolated project and execute an installed skill headlessly with JSON-verifiable status, then runtime planning artifacts are reconciled with shipped support
**Depends on**: Phase 46, Phase 47, Phase 48
**Requirements**: GCLI-01, GCLI-02, PARITY-02
**Success Criteria** (what must be TRUE):
  1. `agent-brain install-agent --agent gemini --project --path <integration-dir>` writes `.gemini/plugins/agent-brain/` inside the integration project and verifies the expected generated files before execution
  2. A headless Gemini run from the integration project can invoke an installed Agent Brain skill or setup flow and emit JSON status
  3. Runtime-related pending todos and planning docs are reconciled with shipped Codex, OpenCode, and Gemini support so no completed work remains pending
**Plans**: 2 plans

Plans:
- [ ] 49-01-PLAN.md — Gemini project-local install verification + headless execution
- [ ] 49-02-PLAN.md — Runtime backlog cleanup + parity documentation updates

---
*Roadmap created: 2026-02-07*
*Last updated: 2026-03-31 — v9.6.0 initialized*
