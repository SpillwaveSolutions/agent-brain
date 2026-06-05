---
phase: 21
slug: fix-duplicate-chunk-id
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-12
---

# Phase 21 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x with pytest-asyncio |
| **Config file** | agent-brain-server/pyproject.toml |
| **Quick run command** | `cd agent-brain-server && poetry run pytest tests/unit/storage/test_vector_store_metadata.py -x` |
| **Full suite command** | `task before-push` |
| **Estimated runtime** | ~2 seconds (quick) / ~20 seconds (full) |

---

## Sampling Rate

- **After every task commit:** Run quick vector store tests
- **After every plan wave:** Run `task before-push`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 21-01-01 | 01 | 1 | DEDUP-01 | unit | `poetry run pytest tests/unit/storage/ -k "duplicate"` | ❌ W0 | ⬜ pending |

---

## Wave 0 Requirements

- [ ] Test case for duplicate chunk IDs in `tests/unit/storage/test_vector_store_metadata.py`

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
