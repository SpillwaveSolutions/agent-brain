---
phase: 19
slug: plugin-and-skill-updates-for-embedding-cache-management
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-12
---

# Phase 19 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Manual validation (documentation-only phase) |
| **Config file** | none — no code changes |
| **Quick run command** | `ls agent-brain-plugin/commands/agent-brain-cache.md` |
| **Full suite command** | `task before-push` (verify no regressions) |
| **Estimated runtime** | ~60 seconds |

---

## Sampling Rate

- **After every task commit:** Verify file exists and has correct YAML front-matter
- **After every plan wave:** Check all updated files for consistency
- **Before `/gsd:verify-work`:** Full `task before-push` must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 19-01-01 | 01 | 1 | cache-cmd | file check | `test -f agent-brain-plugin/commands/agent-brain-cache.md` | ❌ W0 | ⬜ pending |
| 19-01-02 | 01 | 1 | help-update | grep check | `grep -q 'cache' agent-brain-plugin/commands/agent-brain-help.md` | ✅ | ⬜ pending |
| 19-01-03 | 01 | 1 | api-docs | grep check | `grep -q '/index/cache' agent-brain-plugin/skills/using-agent-brain/references/api_reference.md` | ✅ | ⬜ pending |
| 19-01-04 | 01 | 1 | skill-update | grep check | `grep -q 'cache' agent-brain-plugin/skills/using-agent-brain/SKILL.md` | ✅ | ⬜ pending |
| 19-01-05 | 01 | 1 | agent-update | grep check | `grep -qi 'embedding.cache' agent-brain-plugin/agents/search-assistant.md` | ✅ | ⬜ pending |
| 19-01-06 | 01 | 1 | config-skill | grep check | `grep -q 'EMBEDDING_CACHE' agent-brain-plugin/skills/configuring-agent-brain/SKILL.md` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements. No code or test stubs needed — this is a documentation-only phase.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Slash command activates | cache-cmd | Requires running Claude Code with plugin | Run `/agent-brain-cache` in Claude Code, verify it triggers |
| Help lists cache | help-update | Visual check | Run `/agent-brain-help`, verify Cache Commands category appears |
| Skill triggers on cache queries | skill-update | Requires Claude Code skill matching | Ask Claude "check my cache hit rate", verify skill activates |

---

## Validation Sign-Off

- [ ] All tasks have file/grep verify commands
- [ ] Sampling continuity: all tasks have automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
