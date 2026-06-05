# Phase 38: Server Reliability & Provider Fixes - Context

**Gathered:** 2026-03-19
**Status:** Ready for planning
**Source:** PRD Express Path (docs/superpowers/specs/2026-03-19-ollama-batch-retry-design.md)

<domain>
## Phase Boundary

Phase 38 resolves all known server-side bugs and provider deprecation issues:

1. **CWD Bug** — `chroma_db/` and `cache/` must be created inside `AGENT_BRAIN_STATE_DIR`, not relative to CWD
2. **Ollama Broken Pipe** — `OllamaEmbeddingProvider` fails at ~50% due to large batch payloads; add retry + smaller default batch size + inter-batch delay
3. **Sentence-Transformers Timeout** — `agent-brain start` with sentence-transformers reranker times out on first init
4. **ChromaDB Telemetry Noise** — PostHog telemetry errors logged at startup; suppress them
5. **Gemini Deprecation** — Gemini summarization provider uses deprecated package; migrate to `google-genai`
6. **Object Pascal PR #115** — Review and merge or apply equivalent changes for Object Pascal file indexing support

The PRD specifies the complete design for item 2 (Ollama fix). Items 1, 3, 4, 5, 6 are delegated to Claude's discretion following existing codebase patterns.

</domain>

<decisions>
## Implementation Decisions

### Ollama Batch Size (LOCKED — from PRD)
- Default `batch_size` for `OllamaEmbeddingProvider` is **10** (was 100)
- Applied as: `batch_size = config.params.get("batch_size", 10)`
- Existing configs with explicit `batch_size` are unaffected
- Users relying on batch=100 must add `batch_size: 100` explicitly to `config.yaml`

### Ollama Inter-Batch Delay (LOCKED — from PRD)
- New param `request_delay_ms` (default: 0)
- Cast to `int` at provider construction; raises `ValueError` if not convertible (e.g., `"200ms"`)
- Delay fires at **end of `_embed_batch`** (after embeddings returned), not between chunks of the base loop
- `asyncio.sleep(self._request_delay_ms / 1000)` — only if `> 0`

### Ollama Retry Logic (LOCKED — from PRD)
- New param `max_retries` (default: 3); cast to `int` at construction
- `max_retries: 0` means "no retry — fail immediately on first error" (not falsy, explicit opt-out)
- `max_retries` is NOT exposed in the config wizard; advanced users hand-edit `config.yaml`
- Both `_embed_batch` and `embed_text` get retry logic (same HTTP path)
- Shared private helper `_is_retryable_error(exc)` classifies errors

### Retry Error Classification (LOCKED — from PRD)
**Retryable (transient — retry with backoff):**
- `BrokenPipeError`
- `ConnectionResetError`
- `httpx.ReadTimeout`
- `httpx.RemoteProtocolError`
- `httpx.ConnectError` — **only when error message does NOT contain "refused"**

**Non-retryable (raise immediately, no retry):**
- `ConnectionRefusedError` → raise `OllamaConnectionError` immediately
- `httpx.ConnectError` with "refused" in message → raise `OllamaConnectionError` immediately
- Error message containing "model not found" → raise `ProviderError` immediately
- Any other `Exception` not in retryable list → raise immediately

**Disambiguation rule:** Use explicit `isinstance` type checks + message inspection (never bare `except ConnectionError`) to ensure `ConnectionRefusedError` vs retryable `ConnectionError` remain mutually exclusive.

### Retry Backoff (LOCKED — from PRD)
- Exponential backoff: `1s → 2s → 4s` (base-2)
- No jitter (Ollama is single-process local server, no thundering-herd concern)
- 30s cap present for correctness if `max_retries` hand-edited above 5 (unreachable at default 3)
- After `max_retries` exhausted: raise `ProviderError` with original cause; job marked FAILED

### Config YAML Schema (LOCKED — from PRD)
New optional params under Ollama embedding block — no schema changes required (use existing `EmbeddingConfig.params: dict[str, Any]`):
```yaml
embedding:
  provider: ollama
  model: nomic-embed-text
  params:
    batch_size: 10        # choices: 1, 5, 10, 20, 50, 100  (default: 10)
    request_delay_ms: 0   # ms between batches, 0 = none     (default: 0)
    max_retries: 3        # retry attempts per batch/text     (default: 3)
```

### Config Wizard (LOCKED — from PRD)
- New sub-command `agent-brain config wizard` under existing `config` group in `agent_brain_cli/commands/config.py`
- When `provider == ollama`, add two follow-up prompts after model selection:
  - `batch_size`: choices `[1, 5, 10, 20, 50, 100]`, default `10`
  - `request_delay_ms`: integer ≥ 0, recommended 50–200 on low-memory hardware, default `0`
- `max_retries` is NOT exposed in wizard
- Prompts skipped entirely for `openai` and `cohere` providers
- Wizard generates/updates `config.yaml` in `.agent-brain/` directory

### Test Requirements (LOCKED — from PRD)
**Unit tests** — new file `agent-brain-server/tests/providers/test_ollama_embedding.py`:
- `_embed_batch` retries on `BrokenPipeError` and succeeds on 2nd attempt
- `_embed_batch` raises `ProviderError` after `max_retries` exhausted
- `ConnectionRefusedError` raises `OllamaConnectionError` immediately without retrying
- `httpx.ConnectError("Connection refused")` raises `OllamaConnectionError` immediately
- Non-retryable errors (model not found) are not retried
- Sleep durations follow `1s, 2s, 4s` sequence (mock `asyncio.sleep`, verify call args)
- `request_delay_ms > 0` calls `asyncio.sleep` after each batch
- `request_delay_ms: "200ms"` (invalid string) raises `ValueError` at construction
- Default `batch_size` is 10 for Ollama (not 100)
- `max_retries: 0` causes immediate failure with no sleep calls
- `embed_text` (single-text path) also retries on transient errors
- `embed_text` raises `OllamaConnectionError` immediately on refused connection

**Integration tests** — new file `agent-brain-cli/tests/commands/test_config_wizard.py`:
- Wizard shows `batch_size` and `request_delay_ms` prompts when provider is `ollama`
- Wizard skips those prompts for `openai` and `cohere`
- Wizard rejects invalid `batch_size` choices (e.g., `7`)
- Wizard rejects negative `request_delay_ms`

### Claude's Discretion
The following items from the phase roadmap are not specified in the PRD — implement following existing codebase patterns:

1. **CWD Bug Fix** — Find where `chroma_db/` and `cache/` paths are constructed; route them through `AGENT_BRAIN_STATE_DIR` instead of relative CWD. Read `config/settings.py` and `storage/` to find the construction sites.

2. **Sentence-Transformers Reranker Timeout** — Investigate `agent-brain start` timeout on first init with sentence-transformers reranker. Likely a model download blocking the startup health check. Apply appropriate fix (async init, background loading, or increased timeout).

3. **ChromaDB Telemetry Suppression** — Find where ChromaDB PostHog telemetry errors appear in logs and suppress them (environment variable, telemetry config, or exception catch at startup).

4. **Gemini Provider Migration** — Migrate `providers/summarization/` Gemini provider from deprecated package to `google-genai`. Follow the same pattern as other provider implementations.

5. **Object Pascal PR #115** — Review the PR changes and either merge or apply equivalent changes for Object Pascal (`.pas`, `.pp` file extensions) indexing support. Check `indexing/` for language detection.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Ollama Provider (primary target)
- `agent-brain-server/agent_brain_server/providers/embedding/ollama.py` — Current OllamaEmbeddingProvider implementation to be modified
- `agent-brain-server/agent_brain_server/providers/base.py` — Base provider classes; `_embed_batch` and `embed_text` signatures
- `agent-brain-server/agent_brain_server/providers/exceptions.py` — `OllamaConnectionError`, `ProviderError` definitions
- `agent-brain-server/agent_brain_server/providers/embedding/openai.py` — Reference implementation for comparison

### Config
- `agent-brain-server/agent_brain_server/config/settings.py` — `EmbeddingConfig.params` definition; state directory configuration
- `agent-brain-cli/agent_brain_cli/commands/config.py` — Existing `config` group where `wizard` sub-command goes

### Storage (for CWD bug)
- `agent-brain-server/agent_brain_server/storage/` — ChromaDB storage initialization; where paths are constructed

### Providers (for other fixes)
- `agent-brain-server/agent_brain_server/providers/reranker/` — Sentence-transformers reranker; startup timeout
- `agent-brain-server/agent_brain_server/providers/summarization/` — Gemini provider to migrate

### PRD
- `docs/superpowers/specs/2026-03-19-ollama-batch-retry-design.md` — Full Ollama batch/retry design spec (source of locked decisions above)

</canonical_refs>

<specifics>
## Specific Ideas

### From PRD — Exact Code Patterns

**Provider construction validation:**
```python
self._request_delay_ms: int = int(config.params.get("request_delay_ms", 0))
self._max_retries: int = int(config.params.get("max_retries", 3))
batch_size = config.params.get("batch_size", 10)  # was 100
```

**Delay insertion point:**
```python
async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
    result = ...  # existing HTTP call with retry
    if self._request_delay_ms > 0:
        await asyncio.sleep(self._request_delay_ms / 1000)
    return result
```

**Backoff sequence:** 1s → 2s → 4s (base-2 exponential, no jitter)

**Error helper signature:** `_is_retryable_error(exc) -> bool` — private method, keeps classification in one place

</specifics>

<deferred>
## Deferred Ideas

- Retry logic for OpenAI/Cohere (those SDKs already retry internally — non-goal per PRD)
- Changing job-level concurrency (already 1 job at a time — non-goal per PRD)
- Exposing `max_retries` in config wizard (hand-edit only — non-goal per PRD)

</deferred>

---

*Phase: 38-server-reliability-and-provider-fixes*
*Context gathered: 2026-03-19 via PRD Express Path*
