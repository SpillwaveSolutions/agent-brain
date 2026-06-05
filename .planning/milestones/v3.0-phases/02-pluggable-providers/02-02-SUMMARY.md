---
phase: 02-pluggable-providers
plan: 02
subsystem: config, api
tags: [validation, strict-mode, health-check]
dependency_graph:
  requires: [provider-config, health-router]
  provides: [validation-severity, strict-mode, provider-health-endpoint]
  affects: [startup, cli]
tech_stack:
  added: []
  patterns: [severity-levels, fail-fast, health-checks]
key_files:
  created:
    - agent-brain-server/tests/unit/config/test_provider_validation.py
  modified:
    - agent-brain-server/agent_brain_server/config/provider_config.py
    - agent-brain-server/agent_brain_server/config/settings.py
    - agent-brain-server/agent_brain_server/api/main.py
    - agent-brain-server/agent_brain_server/api/routers/health.py
    - agent-brain-server/agent_brain_server/models/health.py
    - agent-brain-cli/agent_brain_cli/commands/start.py
decisions:
  - "Use ValidationSeverity enum (CRITICAL, WARNING) for structured error handling"
  - "CRITICAL errors block startup only in strict mode for backward compatibility"
  - "/health/providers endpoint provides debugging visibility without blocking"
  - "Strict mode is opt-in via --strict CLI flag or AGENT_BRAIN_STRICT_MODE env var"
metrics:
  duration_minutes: 5
  completed_date: 2026-02-09
  tasks_completed: 5
  commits: 7
  files_modified: 7
  files_created: 1
  tests_added: 8
---

# Phase 02 Plan 02: Strict Startup Validation Summary

**One-liner:** Structured validation severity levels with opt-in strict mode and provider health debugging endpoint

## What Was Built

Implemented a comprehensive strict validation system with severity levels (CRITICAL/WARNING), fail-fast startup behavior controlled by `--strict` flag, and a `/health/providers` debugging endpoint.

### Core Components

1. **ValidationError with Severity Levels** (provider_config.py)
   - `ValidationSeverity` enum: CRITICAL (blocks startup in strict mode), WARNING (logged only)
   - `ValidationError` dataclass with message, severity, provider_type, field
   - `has_critical_errors()` helper function
   - Updated `validate_provider_config()` to return structured ValidationError objects

2. **Strict Mode Configuration** (settings.py, main.py)
   - `AGENT_BRAIN_STRICT_MODE` setting (default: False for backward compatibility)
   - FastAPI lifespan validation: logs CRITICAL as errors, WARNING as warnings
   - Raises RuntimeError on critical errors when strict mode enabled
   - Stores strict_mode on app.state for health endpoint access

3. **CLI --strict Flag** (start.py)
   - Added `--strict` option to `agent-brain start` command
   - Sets `AGENT_BRAIN_STRICT_MODE=true` environment variable
   - Updated help text and examples

4. **/health/providers Endpoint** (health.py, models/health.py)
   - New endpoint: `GET /health/providers`
   - Returns `ProvidersStatus`: config_source, strict_mode, validation_errors, providers list
   - `ProviderHealth` per provider: type, name, model, status, message, dimensions
   - Health checks: embedding (with dimensions), summarization, reranker (if enabled)
   - Shows provider availability without blocking startup

5. **Unit Tests** (tests/unit/config/test_provider_validation.py)
   - 8 test cases covering validation severity behavior
   - Tests ValidationError string representation ([CRITICAL] vs [WARNING])
   - Tests has_critical_errors() function
   - Tests Ollama provider doesn't require API keys

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add ValidationError class with severity levels | a3332d2 | provider_config.py |
| 2 | Add provider health endpoint | caa08fa | health.py, models/health.py |
| 3 | Add strict mode to FastAPI lifespan | b42ce72 | settings.py, main.py |
| 4 | Add --strict flag to CLI start command | 6ba9591 | start.py |
| 5 | Add unit tests for validation severity | 5b41b1e | test_provider_validation.py |

Additional commits:
- 3e14863: Black formatting
- c0bbc44: Lint fixes (removed unused variables, fixed line lengths)

## Deviations from Plan

None - plan executed exactly as written.

## Key Decisions Made

1. **Backward Compatibility First**: Strict mode is opt-in (default: False) to avoid breaking existing deployments that may have warnings.

2. **Severity Levels**: CRITICAL for missing API keys (non-Ollama), WARNING for health check failures or optional issues.

3. **Health Endpoint Design**: Shows provider status without requiring API calls, enabling debugging without side effects.

4. **CLI Flag**: `--strict` is clear, discoverable, and follows common CLI patterns (like pytest's strict markers).

## Testing

- Unit tests: 8 new test cases in test_provider_validation.py
- All tests passing
- Coverage: Covers ValidationError class, validate_provider_config, has_critical_errors
- Manual verification: `agent-brain start --help` shows --strict flag

## Integration Points

### Input Dependencies
- Existing `provider_config.py` validation logic
- Existing `/health` router structure
- CLI start command flow

### Output Provides
- `ValidationError` class for structured error reporting
- `ValidationSeverity` enum for error classification
- `/health/providers` endpoint for debugging
- `--strict` CLI flag for fail-fast behavior
- `app.state.strict_mode` for runtime introspection

### Affects
- Server startup behavior (can now fail fast in strict mode)
- CLI start command (new --strict option)
- Health checking (new providers endpoint)

## Example Usage

```bash
# Start with warnings only (default)
agent-brain start

# Start with strict validation (fail on missing API keys)
agent-brain start --strict

# Check provider health
curl http://localhost:8000/health/providers
```

Example `/health/providers` response:
```json
{
  "config_source": "/path/to/config.yaml",
  "strict_mode": false,
  "validation_errors": [
    "[CRITICAL] embedding: Missing API key for openai embeddings. Set OPENAI_API_KEY environment variable."
  ],
  "providers": [
    {
      "provider_type": "embedding",
      "provider_name": "openai",
      "model": "text-embedding-3-large",
      "status": "unavailable",
      "message": "Missing API key",
      "dimensions": null
    },
    {
      "provider_type": "summarization",
      "provider_name": "anthropic",
      "model": "claude-haiku-4-5-20251001",
      "status": "healthy",
      "message": null
    }
  ],
  "timestamp": "2026-02-09T21:26:25Z"
}
```

## Quality Assurance

- [x] All tasks completed
- [x] Each task committed individually
- [x] Unit tests added and passing (8 tests)
- [x] Code formatted with black
- [x] Linting passed (ruff)
- [x] Type checking passed (mypy)
- [x] Manual verification of CLI flag

## Self-Check: PASSED

**Created files exist:**
- [x] agent-brain-server/tests/unit/config/test_provider_validation.py - FOUND

**Commits exist:**
- [x] a3332d2 - FOUND (ValidationError class)
- [x] caa08fa - FOUND (/health/providers endpoint)
- [x] b42ce72 - FOUND (strict mode to FastAPI lifespan)
- [x] 6ba9591 - FOUND (--strict CLI flag)
- [x] 5b41b1e - FOUND (unit tests)
- [x] 3e14863 - FOUND (formatting)
- [x] c0bbc44 - FOUND (lint fixes)

All claimed files and commits verified successfully.

## Next Steps

This plan completes PROV-06 (strict startup validation). Next plans:
- 02-03-PLAN.md: Provider switching E2E test (PROV-03)
- 02-04-PLAN.md: Ollama offline E2E test (PROV-04)

## Notes

- Strict mode provides fail-fast behavior for production deployments where configuration errors should be caught immediately
- Health endpoint enables debugging without impacting startup behavior
- Backward compatible: existing deployments continue to work with warnings
