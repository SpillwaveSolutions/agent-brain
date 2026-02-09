# Phase 2: Pluggable Providers - Research Findings

**Date:** 2026-02-08
**Status:** Research Complete

## Executive Summary

The provider infrastructure is **substantially implemented** but has critical gaps in validation, testing, and documentation. The core architecture (factory, config, providers) works. The main gaps are:

1. **PROV-07 is NOT implemented** - No dimension mismatch detection
2. **PROV-03 is PARTIALLY done** - Config switching works but lacks E2E verification
3. **PROV-06 is PARTIAL** - Startup validation exists but doesn't fail on critical errors
4. Integration tests for provider combinations are missing

---

## Requirements Status Table

| Requirement | Status | Evidence | Gap |
|-------------|--------|----------|-----|
| **PROV-01** | DONE | `provider_config.py` EmbeddingConfig, YAML loading, OpenAI/Ollama/Cohere registered | None |
| **PROV-02** | DONE | `provider_config.py` SummarizationConfig, Anthropic/OpenAI/Gemini/Grok/Ollama registered | None |
| **PROV-03** | PARTIAL | Config file switching implemented; tested in `test_config.py` | No E2E test proving runtime switching works |
| **PROV-04** | DONE | Ollama providers exist; `get_api_key()` returns None for Ollama; `health_check()` implemented | No offline mode E2E test |
| **PROV-05** | DONE | `api_key_env` field, `get_api_key()` reads from `os.getenv()`, never stores keys in YAML | None |
| **PROV-06** | PARTIAL | `validate_provider_config()` called in `lifespan()`, logs warnings | Does NOT fail on critical errors - only warns |
| **PROV-07** | MISSING | `ProviderMismatchError` defined but **never raised**; no dimension check on index | Need dimension validation during indexing |

---

## Detailed Gap Analysis

### PROV-03: Config-Only Switching (PARTIAL)

**What Works:**
- `_find_config_file()` searches standard locations
- `load_provider_settings()` parses YAML to Pydantic models
- `ProviderRegistry.get_embedding_provider()` instantiates based on config
- Unit tests verify config parsing

**Gap:**
- No E2E test proving: "change config.yaml -> restart server -> different provider used"
- No CLI command to show active provider configuration

**Recommendation:** Add integration test for provider switching

### PROV-06: Startup Validation (PARTIAL)

**What Works:**
```python
# In api/main.py lifespan():
validation_errors = validate_provider_config(provider_settings)
if validation_errors:
    for error in validation_errors:
        logger.warning(f"Provider config warning: {error}")
    # Log but don't fail - providers may work if keys are set later
```

**Gap:**
- Validation only **warns** - server starts even with missing API keys
- No distinction between critical (OpenAI without key) vs recoverable errors
- Comment suggests this is intentional: "providers may work if keys are set later"

**Risk:**
- User runs server, starts indexing, gets cryptic error later
- Better to fail fast on startup

**Recommendation:**
1. Add `--strict` flag to fail on validation errors
2. Add health endpoint `/health/providers` showing provider status
3. Distinguish between "configured but untested" vs "critical missing"

### PROV-07: Dimension Mismatch (MISSING)

**What Exists:**
- Each provider implements `get_dimensions()` with correct values:
  - OpenAI: 3072 (text-embedding-3-large), 1536 (small/ada-002)
  - Ollama: 768 (nomic-embed-text), 1024 (mxbai-embed-large)
  - Cohere: 1024 (v3.0), 384 (light-v3.0)
- `ProviderMismatchError` exception defined in `providers/exceptions.py`
- Exception is **never raised** anywhere in code

**Gap:**
- ChromaDB collection has no metadata about which provider/model created it
- No check on indexing: "Does new embedding dimension match existing?"
- No check on query: "Is query embedding same dimension as index?"

**What Could Go Wrong:**
1. User indexes with OpenAI (3072d), changes to Ollama (768d)
2. Query embedding is 768d, stored embeddings are 3072d
3. ChromaDB may silently fail or return garbage results

**Recommendation:**
1. Store embedding config metadata in collection on creation
2. Validate on startup: if collection exists, check dimensions match
3. Validate on indexing: reject if dimension mismatch
4. Add `--force` flag to allow re-indexing with different provider

---

## Key Files That Need Modification

### For PROV-06 Enhancement (Strict Validation)

| File | Change |
|------|--------|
| `agent_brain_server/api/main.py` | Add strict mode, fail on critical validation errors |
| `agent_brain_server/config/provider_config.py` | Add severity levels to validation errors |
| `agent_brain_cli/commands/*.py` | Add `--strict` flag to start command |

### For PROV-07 (Dimension Mismatch)

| File | Change |
|------|--------|
| `agent_brain_server/storage/vector_store.py` | Store/check embedding metadata in collection |
| `agent_brain_server/services/indexing_service.py` | Validate dimensions before indexing |
| `agent_brain_server/services/query_service.py` | Validate query embedding dimensions |
| `agent_brain_server/api/main.py` | Dimension validation in startup |

### For PROV-03 Testing

| File | Change |
|------|--------|
| `e2e/integration/test_provider_switching.py` | NEW - E2E test for provider switching |
| `e2e/fixtures/` | Add config.yaml variants for different providers |

---

## Risks and Pitfalls

### 1. ChromaDB Dimension Handling
ChromaDB does NOT enforce dimensions - it will silently accept mismatched vectors. This can lead to:
- Corrupted similarity scores
- Silent search quality degradation
- Difficult-to-debug issues

**Mitigation:** Explicit dimension validation before any vector operation.

### 2. Ollama Connection at Startup
If Ollama is configured but not running, `health_check()` fails. Current behavior:
- Logs warning
- Server continues
- First indexing operation fails with `OllamaConnectionError`

**Recommendation:** Add optional startup health check for local providers.

### 3. Mixed Provider Index
If a user indexed with OpenAI, then switches to Cohere (both 1024d for some models), embeddings are semantically incompatible even if dimensions match.

**Recommendation:** Track provider name + model, not just dimensions.

### 4. Config File Discovery Race
Multiple config search paths could lead to unexpected behavior if user has both project and home configs.

**Currently:** First match wins. Logged at DEBUG level.
**Recommendation:** Add `agent-brain config show` command to display active config source.

---

## Test Coverage Analysis

### Existing Tests

| Test File | Coverage |
|-----------|----------|
| `tests/unit/providers/test_config.py` | YAML loading, validation, defaults |
| `tests/unit/providers/test_factory.py` | Registry, caching, error handling |
| `tests/unit/providers/test_openai_embedding.py` | Dimensions, batch embedding, errors |
| `tests/unit/providers/test_ollama_embedding.py` | Dimensions, connection errors |
| `tests/unit/providers/test_anthropic_summarization.py` | Summarization flow |

### Missing Tests

| Gap | Priority |
|-----|----------|
| E2E test for provider switching | HIGH |
| E2E test for Ollama offline mode | HIGH |
| Integration test for dimension mismatch prevention | HIGH |
| E2E test for Cohere provider | MEDIUM |
| E2E test for Gemini/Grok providers | LOW |

---

## Recommendations for Plans Needed

### Plan 1: Dimension Mismatch Prevention (PROV-07)
**Priority:** HIGH
**Effort:** 3-4 hours

Implement:
1. Store embedding metadata in ChromaDB collection metadata
2. Validate on startup if collection exists
3. Validate on index operations
4. Add `--force` flag to bypass and re-index

### Plan 2: Strict Startup Validation (PROV-06 Enhancement)
**Priority:** MEDIUM
**Effort:** 2 hours

Implement:
1. Add validation severity levels (ERROR vs WARNING)
2. Add `--strict` flag to CLI start command
3. Add `/health/providers` endpoint

### Plan 3: Provider Switching E2E Test (PROV-03 Verification)
**Priority:** MEDIUM
**Effort:** 2 hours

Implement:
1. E2E test that changes config and verifies behavior
2. CLI command `agent-brain config show` for debugging

### Plan 4: Ollama Offline E2E Test (PROV-04 Verification)
**Priority:** LOW
**Effort:** 1 hour

Implement:
1. E2E test running with Ollama-only config
2. Verify no external API calls made

---

## Summary

| Item | Count |
|------|-------|
| Requirements Done | 4 (PROV-01, PROV-02, PROV-04, PROV-05) |
| Requirements Partial | 2 (PROV-03, PROV-06) |
| Requirements Missing | 1 (PROV-07) |
| Plans Recommended | 4 |
| Estimated Total Effort | 8-9 hours |

The provider infrastructure is solid. The main work is adding dimension validation (PROV-07) and improving startup validation robustness (PROV-06). Testing gaps should be addressed in Phase 4 (Provider Integration Testing) rather than here.

---

*Research completed: 2026-02-08*
