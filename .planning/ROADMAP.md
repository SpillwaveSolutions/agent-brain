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
- ✅ **v9.4.0 Documentation Accuracy Audit & Reliability Closure** — Phases 29-33 + gap closure phases 36-40 (shipped 2026-03-20)
- ⬜ **v9.3.0 LangExtract + Config Spec** — Phases 34-35
  - Phase 34: Config command spec reconciliation (12-step wizard formalized)
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

<details>
<summary>✅ v9.4.0 Documentation Accuracy Audit & Reliability Closure (Phases 29-33, 36-40) — SHIPPED 2026-03-20</summary>

**Full details:** [v9.4.0-ROADMAP.md](milestones/v9.4.0-ROADMAP.md)

</details>

---

### Phase 34: Config Command Spec Reconciliation

**Goal:** Reconcile the 12-step config wizard SPEC with the command implementation, fix drift, and verify alignment.

**Requirements:** SPEC-AUDIT-01, SPEC-FIX-01, SPEC-FIX-02, SPEC-VERIFY-01, SPEC-DOC-01

**Success Criteria:**
1. SPEC.md title says "12-step wizard" (not "9-step")
2. All 12 steps aligned between spec and command
3. Drift checklist proves zero remaining drift
4. Downstream docs updated

**Plans:** 2/2 plans complete

Plans:
- [ ] 34-01-PLAN.md — Audit spec vs command, fix SPEC.md title, reconcile drift
- [ ] 34-02-PLAN.md — Create drift verification checklist, update SETUP_PLAYGROUND.md

---

### Phase 35: LangExtract Document Graph Extractor

**Goal:** LangExtract document graph extractor (multi-provider, retire LLMEntityExtractor as default)

**Plans:** 0 plans

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
| 34 | 2/2 | Complete   | 2026-03-22 | - |
| 35 | v9.3.0 | 0 plans     | Complete   | 2026-03-17 |
| 36 | 2/2 | Complete   | 2026-03-20 | - |
| 37 | 2/2 | Complete    | 2026-03-19 | - |
| 38 | 4/4 | Complete    | 2026-03-20 | - |
| 39 | 2/2 | Complete    | 2026-03-20 | - |
| 40 | 2/2 | Complete    | 2026-03-20 | - |

---
*Roadmap created: 2026-02-07*
*Last updated: 2026-03-20 — Phase 34 planned with 2 plans*
