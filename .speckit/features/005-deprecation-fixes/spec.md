# Feature Specification: Deprecation Warning Fixes

## Metadata
- **Feature ID**: 005-deprecation-fixes
- **Status**: Complete
- **Priority**: P1
- **Created**: 2024-12-17
- **Updated**: 2024-12-17

## Overview

### Problem Statement
The test suite produces three deprecation warnings that indicate non-forward-compatible code patterns:
1. Pydantic V2 `class Config:` is deprecated
2. pytest-asyncio custom `event_loop` fixture is deprecated
3. Pydantic `validate_default` warning from dependencies

These warnings clutter test output and indicate code that will break in future library versions.

### Proposed Solution
Update the codebase to use modern patterns:
- Replace `class Config:` with `model_config = SettingsConfigDict()`
- Remove custom `event_loop` fixture, use pytest-asyncio config
- Filter dependency warnings that we cannot fix

### Success Criteria
- SC-001: `task test` produces 0 deprecation warnings from project code
- SC-002: All 91 tests continue to pass
- SC-003: Settings still load correctly from .env files
- SC-004: Async tests still execute properly

## User Stories

### US1: Clean Test Output
**As a** developer
**I want to** see clean test output without deprecation warnings
**So that** I can focus on actual test failures and not noise

**Acceptance Criteria:**
- AC1: No PydanticDeprecatedSince20 warnings
- AC2: No pytest-asyncio event_loop warnings
- AC3: Dependency warnings filtered from output

## Functional Requirements

### FR-001: Pydantic V2 Settings Configuration
Settings class shall use `model_config = SettingsConfigDict()` instead of `class Config:`.

### FR-002: pytest-asyncio Configuration
Test configuration shall use `asyncio_default_fixture_loop_scope` instead of custom fixture.

### FR-003: Warning Filters
pytest configuration shall filter warnings from dependencies that cannot be fixed.

## Technical Design

### Warning 1: PydanticDeprecatedSince20
**File:** `doc-serve-server/src/config/settings.py`
**Fix:** Replace `class Config:` with `model_config = SettingsConfigDict()`

### Warning 2: event_loop fixture deprecated
**File:** `doc-serve-server/tests/conftest.py`
**Fix:** Remove custom `event_loop` fixture, add config to pyproject.toml

### Warning 3: UnsupportedFieldAttributeWarning
**Source:** Pydantic internals/dependencies
**Fix:** Add warning filter in pytest configuration

## Testing Strategy

### T001: Verify Settings Load
After changes, verify `settings.API_HOST` and other values load correctly.

### T002: Verify Async Tests Work
Run `task test` and verify all async tests pass.

### T003: Verify No Warnings
Run `task test 2>&1 | grep -i warning` and verify no deprecation warnings.

## Dependencies

- pydantic-settings ^2.6.0
- pytest-asyncio ^0.24.0
