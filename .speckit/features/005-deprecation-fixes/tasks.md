# Implementation Tasks: Deprecation Warning Fixes

## Task Overview

| Task ID | Description | Status |
|---------|-------------|--------|
| T001 | Update settings.py to SettingsConfigDict | Complete |
| T002 | Remove event_loop fixture from conftest.py | Complete |
| T003 | Update pyproject.toml pytest config | Complete |
| T004 | Run tests and verify 0 warnings | Complete |
| T005 | Update spec status to Complete | Complete |

---

## T001: Update settings.py to SettingsConfigDict
**Priority**: P0
**Dependencies**: None

**File:** `doc-serve-server/src/config/settings.py`

**Changes:**
1. Add `SettingsConfigDict` to import
2. Replace `class Config:` block with `model_config = SettingsConfigDict(...)`

**Acceptance Criteria:**
- [ ] Import includes `SettingsConfigDict`
- [ ] `class Config:` block removed
- [ ] `model_config` attribute added with same values
- [ ] Settings still load correctly

---

## T002: Remove event_loop fixture from conftest.py
**Priority**: P0
**Dependencies**: T003 (config must be added first)

**File:** `doc-serve-server/tests/conftest.py`

**Changes:**
1. Delete the `event_loop` fixture (lines 20-25)
2. Remove `asyncio` import if no longer needed

**Acceptance Criteria:**
- [ ] No `event_loop` fixture in conftest.py
- [ ] No DeprecationWarning about event_loop

---

## T003: Update pyproject.toml pytest config
**Priority**: P0
**Dependencies**: None

**File:** `doc-serve-server/pyproject.toml`

**Changes:**
1. Add `asyncio_default_fixture_loop_scope = "function"`
2. Add `filterwarnings` for dependency warnings

**Acceptance Criteria:**
- [ ] pytest config includes loop scope setting
- [ ] Warning filters suppress dependency warnings

---

## T004: Run tests and verify 0 warnings
**Priority**: P0
**Dependencies**: T001, T002, T003

**Commands:**
```bash
task test 2>&1 | grep -E "(warning|Warning|WARN)"
```

**Acceptance Criteria:**
- [ ] All 91 tests pass
- [ ] No deprecation warnings in output
- [ ] Settings load correctly
- [ ] Async tests work

---

## T005: Update spec status to Complete
**Priority**: P1
**Dependencies**: T004

**Changes:**
- Update spec.md status from "In Progress" to "Complete"
- Update tasks.md statuses to Complete

**Acceptance Criteria:**
- [ ] Spec marked Complete
- [ ] All task statuses updated

---

## Completion Checklist

- [x] All tests pass (91 tests)
- [x] No deprecation warnings from project code
- [x] Settings still work with .env files
- [x] Async fixtures still work
- [x] SDD artifacts updated
