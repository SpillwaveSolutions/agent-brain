---
phase: 17
slug: query-cache
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-12
---

# Phase 17 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x with pytest-asyncio |
| **Config file** | agent-brain-server/pyproject.toml |
| **Quick run command** | `cd agent-brain-server && poetry run pytest tests/test_query_cache.py -x` |
| **Full suite command** | `task before-push` |
| **Estimated runtime** | ~20 seconds (quick) / ~20 seconds (full) |

---

## Sampling Rate

- **After every task commit:** Run `cd agent-brain-server && poetry run pytest tests/test_query_cache.py -x`
- **After every plan wave:** Run `task before-push`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 17-01-01 | 01 | 1 | QCACHE-01 | unit | `poetry run pytest tests/test_query_cache.py -k "test_cache_hit"` | ❌ W0 | ⬜ pending |
| 17-01-02 | 01 | 1 | QCACHE-02 | unit | `poetry run pytest tests/test_query_cache.py -k "test_invalidate"` | ❌ W0 | ⬜ pending |
| 17-01-03 | 01 | 1 | QCACHE-04 | unit | `poetry run pytest tests/test_query_cache.py -k "test_graph_multi_bypass"` | ❌ W0 | ⬜ pending |
| 17-01-04 | 01 | 1 | QCACHE-03 | unit | `poetry run pytest tests/test_query_cache.py -k "test_ttl_expiry"` | ❌ W0 | ⬜ pending |
| 17-02-01 | 02 | 2 | QCACHE-01 | integration | `poetry run pytest tests/test_query_cache.py -k "test_query_service_cache"` | ❌ W0 | ⬜ pending |
| 17-02-02 | 02 | 2 | QCACHE-02 | integration | `poetry run pytest tests/test_query_cache.py -k "test_job_done_invalidates"` | ❌ W0 | ⬜ pending |
| 17-02-03 | 02 | 2 | QCACHE-05 | integration | `poetry run pytest tests/test_query_cache.py -k "test_health_metrics"` | ❌ W0 | ⬜ pending |
| 17-02-04 | 02 | 2 | QCACHE-06 | config | `poetry run pytest tests/test_query_cache.py -k "test_env_config"` | ❌ W0 | ⬜ pending |
| 17-02-05 | 02 | 2 | XCUT-04 | docs | manual review | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_query_cache.py` — stubs for QCACHE-01 through QCACHE-06
- [ ] `cachetools` added to pyproject.toml dependencies
- [ ] `types-cachetools` added to dev dependencies for mypy

*Existing test infrastructure (pytest, pytest-asyncio, conftest) covers framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Env vars documented | XCUT-04 | Documentation review | Check `docs/` and `CLAUDE.md` for `QUERY_CACHE_TTL` and `QUERY_CACHE_MAX_SIZE` entries |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
