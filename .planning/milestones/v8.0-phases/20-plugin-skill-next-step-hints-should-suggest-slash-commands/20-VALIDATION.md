---
phase: 20
slug: plugin-skill-slash-hints
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-12
---

# Phase 20 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | grep-based content verification (no code changes) |
| **Config file** | N/A |
| **Quick run command** | `grep -r "Next.*agent-brain " agent-brain-plugin/ \| grep -v "agent-brain:"` |
| **Full suite command** | `grep -rn "Next\|next step\|Also available" agent-brain-plugin/ \| grep "agent-brain " \| grep -v "agent-brain:" \| grep -v "poetry\|pip\|bash"` |
| **Estimated runtime** | ~1 second |

---

## Sampling Rate

- **After every task commit:** Run quick grep to verify no bare CLI hints remain
- **After every plan wave:** Run full grep verification
- **Before `/gsd:verify-work`:** Full grep must return zero results
- **Max feedback latency:** 1 second

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements — no new test files needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Slash commands appear in Claude autocomplete | UX | Requires live Claude Code session | Run `/agent-brain:agent-brain-init` and verify next-step shows slash commands |

---

## Validation Sign-Off

- [ ] All "next step" hints use `/agent-brain:agent-brain-*` format
- [ ] Bash code fences still use bare CLI commands
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
