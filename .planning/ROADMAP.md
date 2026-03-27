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
- 🚧 **v9.5.0 Config Validation & Language Support** — Phases 41-45 (in progress)

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

## v9.5.0 Config Validation & Language Support (Phases 41-45)

**Milestone Goal:** Add config validation tooling, expand AST-aware language support to Object Pascal, improve the OpenCode installer to match reference quality, and establish performance benchmarks.

### Phases

- [x] **Phase 41: Bug Fixes & Reliability** — Close known defects blocking daily use (completed 2026-03-24)
- [x] **Phase 42: Object Pascal Language Support** — AST-aware ingestion for .pas/.pp/.dpr/.dpk files (completed 2026-03-25)
- [x] **Phase 43: OpenCode Installer Improvements** — Bring opencode_converter up to reference quality (completed 2026-03-25)
- [x] **Phase 44: Config Validation Tooling** — `agent-brain config validate` and migration diff commands (completed 2026-03-26)
- [ ] **Phase 45: Performance Benchmarking** — Query latency benchmarks and connection pool tuning

### Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 41. Bug Fixes & Reliability | 1/1 | Complete    | 2026-03-24 |
| 42. Object Pascal Language Support | 0/1 | Complete    | 2026-03-25 |
| 43. OpenCode Installer Improvements | 2/2 | Complete    | 2026-03-25 |
| 44. Config Validation Tooling | 2/2 | Complete    | 2026-03-26 |
| 45. Performance Benchmarking | 2/3 | In Progress|  |

## Phase Details

### Phase 41: Bug Fixes & Reliability
**Goal**: Known defects are resolved so daily use is unimpeded
**Depends on**: Nothing (first phase of milestone)
**Requirements**: BUGFIX-01, BUGFIX-02, BUGFIX-03, BUGFIX-04
**Success Criteria** (what must be TRUE):
  1. `agent-brain start` waits up to 120 seconds, allowing sentence-transformers to complete its first-run model download without timing out
  2. The `chroma_db` and `cache` directories resolve relative to `AGENT_BRAIN_STATE_DIR`, not the current working directory, so path-based bugs no longer occur when running from a different directory
  3. Server startup no longer emits ChromaDB PostHog telemetry errors in the console
  4. The Gemini provider works correctly using the `google-genai` package (migrated away from deprecated `google-generativeai`)
**Plans**: 1 plan

Plans:
- [ ] 41-01-PLAN.md — Fix state_dir path resolution + regression tests for all 4 bugfixes

---

### Phase 42: Object Pascal Language Support
**Goal**: Object Pascal source files are ingested with AST-aware chunking and are accessible via the `object-pascal` file type preset
**Depends on**: Phase 41
**Requirements**: LANG-01, LANG-02, LANG-03
**Success Criteria** (what must be TRUE):
  1. Running `agent-brain index /path/to/pascal-project` indexes `.pas`, `.pp`, `.dpr`, and `.dpk` files without errors
  2. Querying against indexed Pascal code returns results scoped to functions, procedures, and classes (not arbitrary byte ranges)
  3. `agent-brain index /path --include-type object-pascal` correctly filters to Pascal file extensions using the built-in preset
**Plans**: 2 plans

Plans:
- [ ] 44-01-PLAN.md — Config schema validation engine + validate CLI command
- [ ] 44-02-PLAN.md — Migration engine + migrate/diff commands + wizard integration

---

### Phase 43: OpenCode Installer Improvements
**Goal**: `agent-brain install-agent --agent opencode` produces a fully correct OpenCode installation that matches reference converter quality
**Depends on**: Phase 41
**Requirements**: OCDI-01, OCDI-02, OCDI-03, OCDI-04, OCDI-05, OCDI-06
**Success Criteria** (what must be TRUE):
  1. The generated `opencode.json` includes a `permissions` block that pre-authorizes the plugin directory so OpenCode does not prompt for permission on first use
  2. Installed files land in singular directory names (`agent/`, `command/`, `skill/`) not plural forms
  3. Agent frontmatter is fully converted: `name` field removed, color value is a hex string, `subagent_type` is mapped, and `tools` is a boolean object; `AskUserQuestion` maps to the `question` field
  4. All path references in installed files point to `~/.config/opencode` instead of `~/.claude`
  5. Running `install-agent --agent opencode` twice produces the same result as running it once (idempotent)
**Plans**: 2 plans

Plans:
- [ ] 43-01-PLAN.md — Types/parser extensions, tool maps, converter fixes (all 8 gaps)
- [ ] 43-02-PLAN.md — Comprehensive tests for all OCDI requirements + quality gate

---

### Phase 44: Config Validation Tooling
**Goal**: Users can validate, migrate, and diff their `config.yaml` from the CLI without manually reading schema documentation
**Depends on**: Phase 41
**Requirements**: CFGVAL-01, CFGVAL-02, CFGVAL-03, CFGVAL-04, CFGVAL-05
**Success Criteria** (what must be TRUE):
  1. `agent-brain config validate` exits non-zero and prints a human-readable error listing the specific field, line number, and a fix suggestion when `config.yaml` contains a schema violation
  2. `agent-brain config validate` exits 0 and prints "Config is valid" when `config.yaml` is correct
  3. `agent-brain config migrate` upgrades a config file from an older schema version to the current schema without requiring manual edits
  4. `agent-brain config diff` shows a colored diff of what the migration would change before applying it
  5. The setup wizard warns the user and pauses when it detects an invalid config, preventing a broken server start
**Plans**: 2 plans

Plans:
- [ ] 44-01-PLAN.md — Config schema validation engine + validate CLI command
- [ ] 44-02-PLAN.md — Migration engine + migrate/diff commands + wizard integration

---

### Phase 45: Performance Benchmarking
**Goal**: Reproducible query benchmark workflow with per-mode latency metrics, PostgreSQL pool timeout exposure, and baseline documentation
**Depends on**: Phase 42, Phase 43, Phase 44
**Requirements**: PERF-01, PERF-02, PERF-03
**Success Criteria** (what must be TRUE):
  1. A benchmark script exists that measures query latency across all retrieval modes (vector, bm25, hybrid, graph, multi) against a reference dataset
  2. `config.yaml` accepts a `storage.postgres.pool` section with documented keys (pool_size, max_overflow, pool_timeout) that are applied to the async SQLAlchemy engine
  3. A `docs/BENCHMARKS.md` file records baseline latency numbers for the reference dataset so regressions can be detected
**Plans**: 3 plans

Plans:
- [ ] 45-01-PLAN.md — Nested storage.postgres.* config schema validation + pool_timeout docs
- [ ] 45-02-PLAN.md — Benchmark mode support matrix + helper unit tests
- [ ] 45-03-PLAN.md — Baseline benchmark run + BENCHMARKS.md documentation

---
*Roadmap created: 2026-02-07*
*Last updated: 2026-03-26 — Phase 45 replanned (3 plans)*
