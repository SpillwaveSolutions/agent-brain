# Ollama Batch Size & Retry Resilience

**Date:** 2026-03-19
**Status:** Approved

## Problem

When using Ollama as the embedding provider, indexing jobs fail with `[Errno 32] Broken pipe` at
roughly the 50% mark. The root cause is `OllamaEmbeddingProvider._embed_batch` sending 100 texts
in a single HTTP request. Ollama is a local model server, not designed for large batch payloads;
it drops the connection mid-stream under that load. Jobs currently have no retry logic, so one
dropped connection fails the entire job.

## Goals

- Reduce the default Ollama batch size from 100 → 10 to keep individual requests small
- Add retry with exponential backoff so transient Ollama connection drops recover automatically
- Add an optional inter-batch delay for low-memory hardware where even small batches need
  breathing room
- Expose batch size and delay in the config wizard when provider is Ollama

## Non-Goals

- Retry logic for OpenAI/Cohere (those SDKs already retry internally)
- Changing job-level concurrency (already 1 job at a time)

---

## Design

### 1. `OllamaEmbeddingProvider` changes (`providers/embedding/ollama.py`)

#### 1a. Lower default batch size

```python
batch_size = config.params.get("batch_size", 10)  # was 100
```

Existing configs with an explicit `batch_size` are unaffected. Existing Ollama configs
**without** an explicit `batch_size` will silently drop from 100 → 10, reducing per-request
payload. Users who have tuned their setup around batch=100 should add `batch_size: 100`
explicitly to `config.yaml` to preserve the old behaviour.

#### 1b. Add `request_delay_ms`

```python
self._request_delay_ms: int = int(config.params.get("request_delay_ms", 0))
```

`request_delay_ms` is cast to `int` on construction. If the value is not convertible to `int`
(e.g., `"200ms"` from a hand-edited config), a `ValueError` is raised at startup with a clear
message. This validates the param regardless of whether it was set via wizard or hand-edit.

The delay is inserted at the **end of `_embed_batch`** (after embeddings are returned), so the
base class `embed_texts` loop requires no changes:

```python
async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
    result = ...  # existing HTTP call with retry
    if self._request_delay_ms > 0:
        await asyncio.sleep(self._request_delay_ms / 1000)
    return result
```

This means the delay fires after every batch including the last one, which is acceptable (adds
at most one extra `request_delay_ms` per job).

#### 1c. Retry with exponential backoff in `_embed_batch` and `embed_text`

Both `_embed_batch` and `embed_text` use the same HTTP call path and are subject to the same
connection failures. Both methods get retry logic. A shared private helper
`_is_retryable_error(exc)` keeps the classification in one place.

```python
self._max_retries: int = int(config.params.get("max_retries", 3))
```

- `max_retries: 0` means "no retry — fail immediately on first error." Zero is not treated as
  falsy; it means the user has explicitly disabled retries (useful for debugging).
- `max_retries` is not exposed in the config wizard. Advanced users may hand-edit `config.yaml`.

**Retryable errors** (transient, worth retrying):
- `BrokenPipeError`
- `ConnectionResetError`
- `httpx.ReadTimeout`
- `httpx.RemoteProtocolError`
- `httpx.ConnectError` — **only when the error message does not contain "refused"**
  (a refused connection means Ollama is not running, which is not a transient error)

**Non-retryable errors** (raised immediately, no retry):
- `ConnectionRefusedError` — Ollama is not running; raise `OllamaConnectionError` immediately
- `httpx.ConnectError` with "refused" in the message — same as above
- Any error message containing "model not found" — configuration problem
- Any other `Exception` not in the retryable list

**Disambiguation of `ConnectionError` vs `ConnectionRefusedError`:** `ConnectionRefusedError`
is a subclass of `ConnectionError`. The retry check uses explicit `isinstance` type checks plus
message inspection — never a bare `except ConnectionError` catch — to ensure the two cases
remain mutually exclusive.

**Backoff:** `1s → 2s → 4s` (base-2 exponential). No jitter is added. Ollama is a single-process
local server with no thundering-herd concern; all retries within a job are sequential.
The 30s cap is present for correctness if `max_retries` is set above 5 via hand-edit, but is
unreachable at the default of 3.

After `max_retries` attempts are exhausted, raise `ProviderError` with the original cause so
the job is marked FAILED with a clear error message.

### 2. Config YAML

New optional params under the Ollama embedding block:

```yaml
embedding:
  provider: ollama
  model: nomic-embed-text
  params:
    batch_size: 10        # choices: 1, 5, 10, 20, 50, 100  (default: 10)
    request_delay_ms: 0   # ms between batches, 0 = none     (default: 0)
    max_retries: 3        # retry attempts per batch/text     (default: 3)
```

These live in the existing `EmbeddingConfig.params: dict[str, Any]` — no schema changes
required. All three values are validated (cast to `int`) on provider construction.

### 3. Config Wizard

The config wizard is implemented as a new command `agent-brain config wizard` added to the
existing `agent-brain-cli/agent_brain_cli/commands/config.py`. It is a new sub-command under
the existing `config` group, not a standalone command. The wizard generates or updates
`config.yaml` in the project's `.agent-brain/` directory.

When `provider == ollama`, the wizard adds two follow-up prompts after the model selection step:

| Prompt | Choices / Validation | Default |
|---|---|---|
| Batch size (`batch_size`) | `[1, 5, 10, 20, 50, 100]` | `10` |
| Inter-batch delay (`request_delay_ms`) | Integer ≥ 0, recommended 50–200 on low-memory hardware | `0` |

`max_retries` is **not** exposed in the wizard — the default of 3 is appropriate for all users.
Advanced users may hand-edit `config.yaml`.

These prompts are skipped entirely for OpenAI and Cohere providers.

---

## Error Handling

| Error type | Behaviour |
|---|---|
| `BrokenPipeError`, `ConnectionResetError` | Retry up to `max_retries` with exponential backoff |
| `httpx.ReadTimeout`, `httpx.RemoteProtocolError` | Retry up to `max_retries` with exponential backoff |
| `httpx.ConnectError` (not refused) | Retry up to `max_retries` with exponential backoff |
| `ConnectionRefusedError` or `httpx.ConnectError` with "refused" | Raise `OllamaConnectionError` immediately — Ollama is not running |
| Model not found | Raise `ProviderError` immediately |
| Retries exhausted | Raise `ProviderError` with original cause; job marked FAILED |
| `request_delay_ms` not convertible to `int` | Raise `ValueError` at provider construction (startup) |

---

## Testing

Unit tests in `agent-brain-server/tests/providers/test_ollama_embedding.py` (new file):

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

Integration tests in `agent-brain-cli/tests/commands/test_config_wizard.py` (new file):

- Wizard shows `batch_size` and `request_delay_ms` prompts when provider is `ollama`
- Wizard skips those prompts for `openai` and `cohere`
- Wizard rejects invalid `batch_size` choices (e.g., `7`)
- Wizard rejects negative `request_delay_ms`

---

## Files Changed

| File | Change |
|---|---|
| `agent-brain-server/agent_brain_server/providers/embedding/ollama.py` | Retry logic, smaller default batch size, inter-batch delay, `max_retries`, type validation |
| `agent-brain-cli/agent_brain_cli/commands/config.py` | New `wizard` sub-command under `config` group |
| `agent-brain-server/tests/providers/test_ollama_embedding.py` | New — unit tests for retry, delay, and error classification |
| `agent-brain-cli/tests/commands/test_config_wizard.py` | New — integration tests for wizard prompt logic |
