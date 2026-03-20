---
phase: 38-server-reliability-and-provider-fixes
verified: 2026-03-20T01:14:40Z
status: human_needed
score: 3/6 must-haves verified
human_verification:
  - test: "Ollama indexing under sequential load"
    expected: "Indexing jobs complete without Broken pipe failures and with stable progress under repeated runs."
    why_human: "Unit tests verify retry/backoff logic, but do not execute real Ollama network behavior under load."
  - test: "First-run start with sentence-transformers reranker"
    expected: "`agent-brain start` succeeds on first init without timeout while reranker model downloads."
    why_human: "Code sets timeout to 120s, but real startup timing depends on model download, machine/network speed, and runtime conditions."
  - test: "Startup log noise check for Chroma telemetry"
    expected: "Server startup logs do not emit ChromaDB/PostHog telemetry errors."
    why_human: "Code suppresses telemetry and logger noise, but runtime confirmation requires observing actual startup logs."
---

# Phase 38: Server Reliability & Provider Fixes Verification Report

**Phase Goal:** All known server-side bugs and provider deprecation issues are resolved so that Agent Brain runs stably under concurrent indexing load, resolves state directories correctly, starts without noise, and supports current provider APIs.
**Verified:** 2026-03-20T01:14:40Z
**Status:** human_needed
**Re-verification:** No - initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | `chroma_db/` and `cache/` directories are created inside `AGENT_BRAIN_STATE_DIR`, not CWD | ✓ VERIFIED | `agent-brain-server/agent_brain_server/api/main.py:291`-`agent-brain-server/agent_brain_server/api/main.py:343` uses `storage_paths`/`state_dir` paths; regression tests pass in `agent-brain-server/tests/unit/test_storage_paths.py:99` and `agent-brain-server/tests/unit/test_storage_paths.py:112` |
| 2 | Indexing jobs with Ollama complete without Broken pipe errors under sequential load | ? UNCERTAIN | Retry/backoff implementation and tests exist (`agent-brain-server/agent_brain_server/providers/embedding/ollama.py:86`, `agent-brain-server/tests/unit/providers/test_ollama_embedding.py:156`), but no real sequential-load integration run against Ollama was executed in this verification |
| 3 | `agent-brain start` succeeds with sentence-transformers reranker without timeout on first init | ? UNCERTAIN | Timeout default raised to 120s in `agent-brain-cli/agent_brain_cli/commands/start.py:199`, but first-run model-download startup path was not exercised end-to-end here |
| 4 | Server starts without ChromaDB PostHog telemetry errors in logs | ? UNCERTAIN | Telemetry suppression is present (`agent-brain-server/agent_brain_server/api/main.py:166`-`agent-brain-server/agent_brain_server/api/main.py:168`), but runtime log observation was not performed |
| 5 | Gemini summarization provider uses `google-genai` package (no deprecation warnings) | ✓ VERIFIED | Provider migrated in `agent-brain-server/agent_brain_server/providers/summarization/gemini.py:6` and `agent-brain-server/agent_brain_server/providers/summarization/gemini.py:49`; dependency switched in `agent-brain-server/pyproject.toml:47` |
| 6 | Object Pascal files are indexed correctly | ✓ VERIFIED | Pascal detection/chunking/presets wired across `agent-brain-server/agent_brain_server/indexing/document_loader.py:80`, `agent-brain-server/agent_brain_server/indexing/chunking.py:505`, `agent-brain-server/agent_brain_server/services/file_type_presets.py:20`, `agent-brain-cli/agent_brain_cli/commands/types.py:27`; Pascal tests passed |

**Score:** 3/6 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `agent-brain-server/agent_brain_server/api/main.py` | State-dir fallback + telemetry suppression | ✓ VERIFIED | Substantive logic in lifespan; wired via imports/calls to `resolve_state_dir`/`resolve_storage_paths` |
| `agent-brain-server/tests/unit/test_storage_paths.py` | CWD regression coverage | ✓ VERIFIED | Contains new absolute/state-dir tests; test suite passes |
| `agent-brain-server/agent_brain_server/providers/embedding/ollama.py` | Retry classification, backoff, safer defaults | ✓ VERIFIED | `_is_retryable_error`, retries, default batch size 10, delay/max_retries present |
| `agent-brain-server/tests/unit/providers/test_ollama_embedding.py` | Retry/load-failure test coverage | ✓ VERIFIED | `TestOllamaRetryLogic` with 12 targeted tests present and passing |
| `agent-brain-cli/agent_brain_cli/commands/start.py` | Increased startup timeout | ✓ VERIFIED | `--timeout` default/help changed to 120 |
| `agent-brain-server/agent_brain_server/providers/summarization/gemini.py` | New Gemini SDK usage | ✓ VERIFIED | Uses `google.genai` client async API; old package import removed |
| `agent-brain-server/pyproject.toml` | Current Gemini dependency | ✓ VERIFIED | `google-genai` declared |
| `agent-brain-server/agent_brain_server/indexing/chunking.py` | Pascal AST symbol extraction | ✓ VERIFIED | Pascal grammar mapping and `_collect_pascal_symbols` implemented |
| `agent-brain-server/agent_brain_server/indexing/document_loader.py` | Pascal extension/content detection | ✓ VERIFIED | Pascal extensions + content patterns + metadata language flow |
| `agent-brain-server/agent_brain_server/services/file_type_presets.py` | Server Pascal preset | ✓ VERIFIED | Pascal preset and code union entries present |
| `agent-brain-cli/agent_brain_cli/commands/types.py` | CLI Pascal preset parity | ✓ VERIFIED | Pascal preset and code union entries present |
| `agent-brain-cli/agent_brain_cli/commands/config.py` | Wizard + YAML write link | ✓ VERIFIED | `wizard` command prompts/validates and writes `.agent-brain/config.yaml` via `yaml.safe_dump` |
| `agent-brain-cli/tests/commands/test_config_wizard.py` | Wizard behavior tests | ✓ VERIFIED | 4 integration tests present and passing |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `agent-brain-server/agent_brain_server/api/main.py` | `agent-brain-server/agent_brain_server/storage_paths.py` | `resolve_storage_paths(state_dir)` | ✓ WIRED | Import at `agent-brain-server/agent_brain_server/api/main.py:48`; calls at `agent-brain-server/agent_brain_server/api/main.py:245` and `agent-brain-server/agent_brain_server/api/main.py:252` |
| `agent-brain-server/agent_brain_server/providers/embedding/ollama.py` | `agent-brain-server/agent_brain_server/providers/exceptions.py` | `raise OllamaConnectionError/ProviderError` | ✓ WIRED | Exception imports and explicit raise paths in both embedding methods |
| `agent-brain-server/agent_brain_server/providers/base.py` | `agent-brain-server/agent_brain_server/providers/embedding/ollama.py` | `BaseEmbeddingProvider.embed_texts -> _embed_batch` | ✓ WIRED | Batch loop calls provider override at `agent-brain-server/agent_brain_server/providers/base.py:172` |
| `agent-brain-server/agent_brain_server/providers/summarization/gemini.py` | `google-genai` | `genai.Client + aio.models.generate_content` | ✓ WIRED | Client construction and async generation call present |
| `agent-brain-server/agent_brain_server/indexing/document_loader.py` | `agent-brain-server/agent_brain_server/services/indexing_service.py` | Language metadata -> `CodeChunker(language=lang)` | ✓ WIRED | Loader sets metadata language; indexing service groups by language and instantiates chunker |
| `agent-brain-cli/agent_brain_cli/commands/config.py` | `.agent-brain/config.yaml` | `wizard` + `yaml.safe_dump` | ✓ WIRED | Wizard resolves path, creates parent, writes YAML |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| *(none declared)* | `38-01/02/03/04-PLAN.md` | All four plans have `requirements: []` | ✓ SATISFIED | Frontmatter checked in each plan file |
| *(none mapped to phase 38)* | `.planning/REQUIREMENTS.md` | No Phase 38 requirement IDs in traceability table | ✓ SATISFIED | `.planning/REQUIREMENTS.md:63`-`.planning/REQUIREMENTS.md:82` contains phases 29-37 only |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| *(none in phase-modified files)* | - | TODO/FIXME/placeholder/stub scan | ✓ None | No blocker/warning anti-patterns found in verified phase files |

### Human Verification Required

### 1. Ollama Sequential Load Reliability

**Test:** Start server with Ollama embeddings, run multiple indexing jobs sequentially over medium/large input.
**Expected:** No Broken pipe failures; retries (if any) recover and jobs complete.
**Why human:** Requires real Ollama process/network behavior under load.

### 2. First-Run Reranker Startup

**Test:** Configure sentence-transformers reranker on a clean machine/cache and run `agent-brain start`.
**Expected:** Startup completes within new 120s default without false timeout.
**Why human:** Depends on real model download/init latency and environment.

### 3. Telemetry Noise Suppression

**Test:** Start server with Chroma backend and inspect startup logs.
**Expected:** No PostHog/Chroma telemetry error noise at startup.
**Why human:** Requires observing actual runtime logs rather than static code checks.

### Gaps Summary

Automated verification found no code gaps in declared phase artifacts or key links. Remaining uncertainty is runtime-behavior validation (Ollama sequential load, first-run reranker startup timing, and startup log cleanliness), so this phase is marked `human_needed` rather than fully passed.

---

_Verified: 2026-03-20T01:14:40Z_
_Verifier: Claude (gsd-verifier)_
