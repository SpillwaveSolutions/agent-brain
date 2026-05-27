---
gsd_state_version: 1.0
milestone: v9.6.0
milestone_name: Runtime Support Parity & Backlog Cleanup
current_phase: 46
status: parked
stopped_at: "Phase 46 shipped; v10.0.x patch series superseded the v9.6.0 milestone — awaiting next milestone definition"
last_updated: "2026-05-27T00:00:00Z"
progress:
  total_phases: 4
  completed_phases: 1
  total_plans: 8
  completed_plans: 2
---

# Agent Brain — Project State

**Last Updated:** 2026-05-27
**Current Milestone:** v9.6.0 Runtime Support Parity & Backlog Cleanup (parked; v10.0.x patch series shipped instead)
**Status:** v10.0.6 released; awaiting next milestone definition
**Current Phase:** 46 complete; v9.6.0 phases 47–49 deferred or absorbed into v10.0.x work

## Current Position

Phase: 46 (project-local-runtime-install-harness) — COMPLETE (v9.5.0)
Plan: 01–02
Status: Ready for next-milestone planning. The v9.6.0 follow-on phases (47 Codex parity, 48 OpenCode parity, 49 Gemini parity & backlog cleanup) were never executed as planned; instead the project shipped seven v10.0.x patch releases addressing GraphRAG durability, Kuzu resilience, PDF/indexing fixes, and the `agent-brain doctor` diagnostic.

## Project Reference

See: .planning/PROJECT.md (last updated 2026-03-31; review before defining next milestone)
**Core value:** Developers can semantically search their entire codebase and documentation through a single, fast, local-first API that understands code structure and relationships
**Current focus:** No active milestone — define v10.1 or v11 next

## Milestone Summary

```
v3.0 Advanced RAG:           [██████████] 100% (shipped 2026-02-10)
v6.0 PostgreSQL Backend:     [██████████] 100% (shipped 2026-02-13)
v6.0.4 Plugin & Install:     [██████████] 100% (shipped 2026-02-22)
v7.0 Index Mgmt & Pipeline:  [██████████] 100% (shipped 2026-03-05)
v8.0 Performance & DX:       [██████████] 100% (shipped 2026-03-15)
v9.0 Multi-Runtime:          [██████████] 100% (shipped 2026-03-16)
v9.1.0 Skill-Runtime:        [██████████] 100% (shipped 2026-03-16)
v9.3.0 LangExtract+Config:   [██████████] 100% (shipped 2026-03-22)
v9.4.0 Doc Accuracy Audit:   [██████████] 100% (shipped 2026-03-20)
v9.5.0 Config Val & Lang:    [██████████] 100% (shipped 2026-03-31)
v9.6.0 Runtime Parity:       [██▌       ]  25% (1/4 phases — parked)
v10.0.0–v10.0.6 Patch Train: [██████████] 100% (shipped 2026-05-25 → 2026-05-27)
  ├─ v10.0.0: agent-brain doctor diagnostic
  ├─ v10.0.1–2: release process fixes (changelog, plugin.json)
  ├─ v10.0.3: PDF chunk-ID collision fix
  ├─ v10.0.4: Kuzu graph search restoration + exclude_patterns fix
  ├─ v10.0.5: GraphRAG on Anthropic, jobs detail crash, Kuzu upgrade self-heal
  └─ v10.0.6: Kuzu corruption self-heal + triplet snapshots (#166)
```

## v9.6.0 Phase Overview (parked)

| Phase | Name | Requirements | Status |
|-------|------|--------------|--------|
| 46 | Project-Local Runtime Install Harness | ISO-01..02, PARITY-01 | Completed |
| 47 | Codex Runtime E2E Parity | CODEX-01..02 | Deferred — re-evaluate during next milestone |
| 48 | OpenCode Runtime E2E Parity | OPEN-01..02 | Deferred — re-evaluate during next milestone |
| 49 | Gemini Runtime E2E Parity & Backlog Cleanup | GCLI-01..02, PARITY-02 | Deferred — re-evaluate during next milestone |

## Accumulated Context

### Key Context Carried Forward

- `agent-brain install-agent` exposes `codex`, `opencode`, `gemini`, and `claude` targets in `agent-brain-cli/agent_brain_cli/commands/install_agent.py`
- Converter-level and CLI-level tests validate install behavior, but headless runtime parity for Codex/OpenCode/Gemini is still unverified
- `e2e-cli/` coverage is Claude-oriented and remains the natural base for runtime parity work if/when v9.6.0 phases 47–49 are revived
- v10.0.x focus was reliability of the graph layer (Kuzu) and operational visibility (`agent-brain doctor`)

### Decisions from Prior Milestones (still load-bearing)

- [Phase 27]: Codex support is a named runtime preset built on skill-runtime and must generate `.codex/skills/agent-brain/` plus idempotent `AGENTS.md`
- [Phase 41]: Gemini provider migrated to `google-genai` (commit `b19ab35`)
- [Phase 42]: Object Pascal language support shipped (commits `de34cd0`, `4777890`)
- [Phase 43]: OpenCode project installs update project-local `opencode.json`, keep singular directories, and preserve permission entries
- [v9.5.0 audit]: Runtime install behavior covered structurally; headless parity through real external CLIs still unverified
- [v10.0.6]: Kuzu graph store now self-heals from corruption via triplet snapshots

### Blockers/Concerns

- Headless Codex, OpenCode, and Gemini CLI binaries not guaranteed in every environment where a parity suite would run
- No active milestone — next planning step needs owner input on whether to revive v9.6.0 phases 47–49 or pivot to new themes (MCP server #167, Voyage AI #152, federated search #157, etc.)

### Pending Todos

All 7 previously-pending todos relating to shipped work were archived to `.planning/todos/done/` on 2026-05-27 with `closed_by_release` annotations. The remaining 3 todos have been promoted to GitHub issues:

- **[#170](https://github.com/SpillwaveSolutions/agent-brain/issues/170)** — fix(server): resolve chroma/bm25 dirs relative to `AGENT_BRAIN_STATE_DIR`, not CWD (real bug — `settings.py:34-35` defaults are CWD-relative)
- **[#171](https://github.com/SpillwaveSolutions/agent-brain/issues/171)** — feat(plugin): pre-authorize setup-assistant agent across 6 setup commands (audit-and-verify — spot-check shows all 6 commands have `context: fork` + `agent: setup-assistant`; needs fresh end-to-end run)
- **[#172](https://github.com/SpillwaveSolutions/agent-brain/issues/172)** — chore(plugin): verify setup-assistant permission scopes (audit-and-verify — required Bash/Write/Edit scopes already present in `setup-assistant.md:23-33`)

See `.planning/todos/pending/` for the source todo files; each carries a `Tracked in:` cross-reference back to its issue.

## Session Continuity

**Last Session:** 2026-05-27
**Stopped At:** v10.0.6 released; backlog triaged; 3 remaining todos promoted to GitHub issues
**Resume File:** None (no active phase)
**Next Action:** Run `/gsd:new-milestone` (or owner-led milestone definition) to scope v10.1 / v11. Likely candidates: revive runtime parity (v9.6.0 phases 47–49), MCP server (#153, #167), or queue prioritization (#157, #156).

---
*State updated: 2026-05-27 — synced with v10.0.6 release reality*
