---
phase: 22
slug: restore-setup-wizard
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-12
---

# Phase 22 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (regression test) + grep verification |
| **Config file** | agent-brain-server/pyproject.toml |
| **Quick run command** | `cd agent-brain-server && poetry run pytest tests/test_plugin_wizard_spec.py -x` |
| **Full suite command** | `task before-push` |
| **Estimated runtime** | ~2 seconds (quick) / ~20 seconds (full) |

---

## Sampling Rate

- **After every task commit:** Run quick wizard spec test
- **After every plan wave:** Run `task before-push`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 22-01-01 | 01 | 1 | WIZARD-01 | content | `grep "AskUserQuestion" agent-brain-plugin/skills/configuring-agent-brain/SKILL.md` | ✅ | ⬜ pending |
| 22-01-02 | 01 | 1 | WIZARD-02 | regression | `poetry run pytest tests/test_plugin_wizard_spec.py -x` | ❌ W0 | ⬜ pending |

---

## Wave 0 Requirements

- [ ] `tests/test_plugin_wizard_spec.py` — regression test checking wizard prompts exist in SKILL.md files

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Full wizard flow works in Claude Code | UX | Requires live session | Run `/agent-brain:agent-brain-setup` and verify all config questions appear |

---

## Validation Sign-Off

- [ ] All tasks have automated verify
- [ ] Regression test prevents future wizard degradation
- [ ] Wave 0 covers all MISSING references
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
