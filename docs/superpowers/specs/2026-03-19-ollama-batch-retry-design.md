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

Existing configs with an explicit `batch_size` are unaffected.

#### 1b. Add `request_delay_ms`

```python
self._request_delay_ms: int = config.params.get("request_delay_ms", 0)
```

After each successful batch in `embed_texts` (via the base class loop), sleep
`request_delay_ms / 1000` seconds before the next batch. Zero means no delay — invisible unless
the user sets it.

The delay is injected by overriding `embed_texts` in `OllamaEmbeddingProvider` so the base class
loop remains unchanged.

#### 1c. Retry with exponential backoff in `_embed_batch`

```python
self._max_retries: int = config.params.get("max_retries", 3)
```

Retry policy:
- **Retryable errors:** `BrokenPipeError`, `ConnectionResetError`, `ConnectionError`,
  `httpx.ConnectError`, `httpx.ReadTimeout`, `httpx.RemoteProtocolError`
- **Non-retryable errors:** model-not-found, authentication errors (configuration problems,
  not transient failures)
- **Backoff:** `1s → 2s → 4s` (base-2 exponential, capped at 30s)
- **Hard fail** after `max_retries` exhausted — raise `ProviderError` with the original
  cause so the job is marked FAILED with a clear error message

The retry loop lives inside `_embed_batch`, so each 10-text batch gets its own retry budget.
A single dropped connection retries that batch only — it does not re-process already-completed
batches.

### 2. Config YAML

New optional params under the Ollama embedding block:

```yaml
embedding:
  provider: ollama
  model: nomic-embed-text
  params:
    batch_size: 10        # choices: 1, 5, 10, 20, 50, 100  (default: 10)
    request_delay_ms: 0   # ms between batches, 0 = none     (default: 0)
    max_retries: 3        # retry attempts per batch          (default: 3)
```

These live in the existing `EmbeddingConfig.params: dict[str, Any]` — no schema changes required.

### 3. Config Wizard

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
| Transient connection drop (broken pipe, reset, timeout) | Retry up to `max_retries` with backoff |
| Ollama not running (refused connection) | Raise `OllamaConnectionError` immediately (no retry — it's not transient) |
| Model not found | Raise `ProviderError` immediately |
| Retries exhausted | Raise `ProviderError` with original cause; job marked FAILED |

## Testing

- Unit test: `_embed_batch` retries on `BrokenPipeError` and succeeds on 2nd attempt
- Unit test: `_embed_batch` raises `ProviderError` after `max_retries` exhausted
- Unit test: Non-retryable errors are not retried
- Unit test: `request_delay_ms > 0` inserts sleep between batches
- Unit test: Default `batch_size` is 10 for Ollama
- Integration test: Wizard shows batch_size and delay prompts only when provider is ollama

## Files Changed

| File | Change |
|---|---|
| `agent-brain-server/agent_brain_server/providers/embedding/ollama.py` | Retry logic, smaller default batch size, inter-batch delay |
| `agent-brain-cli/agent_brain_cli/commands/config_wizard.py` (or equivalent) | Add batch_size + delay prompts for Ollama |
| `agent-brain-server/tests/providers/test_ollama_embedding.py` (new) | Unit tests for retry and delay behaviour |
