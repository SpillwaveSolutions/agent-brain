# Provider Configuration Reference

Complete reference for Agent Brain's pluggable provider system. This document covers all supported embedding, summarization, and reranking providers with configuration examples and troubleshooting guidance.

## Table of Contents

- [Overview](#overview)
- [Provider Matrix](#provider-matrix)
- [Configuration Examples](#configuration-examples)
- [Environment Variables](#environment-variables)
- [Validation](#validation)
- [Troubleshooting](#troubleshooting)
- [Testing Providers](#testing-providers)

## Overview

Agent Brain uses a pluggable provider architecture that allows you to mix and match different AI providers for embeddings, summarization, and reranking. This flexibility enables you to:

- Choose providers based on cost, performance, or privacy requirements
- Run fully offline with Ollama (no external API calls)
- Switch providers without rewriting code
- Test different provider combinations easily

### Configuration File Discovery

Agent Brain searches for `config.yaml` in the following locations (in order):

1. **AGENT_BRAIN_CONFIG environment variable** - Direct path override
2. **State directory** - `$AGENT_BRAIN_STATE_DIR/config.yaml` or `$DOC_SERVE_STATE_DIR/config.yaml`
3. **Current directory** - `./config.yaml`
4. **Project .claude directory** - Walk up from CWD looking for `.claude/agent-brain/config.yaml`
5. **User home** - `~/.agent-brain/config.yaml`
6. **XDG config** - `~/.config/agent-brain/config.yaml`

The first config file found is used. If no config file is found, Agent Brain uses default providers (OpenAI + Anthropic).

### Configuration Override

To use a specific config file for testing or development:

```bash
export AGENT_BRAIN_CONFIG=/path/to/config.yaml
agent-brain-serve
```

## Provider Matrix

| Provider | Embeddings | Summarization | Reranking | API Key Required |
|----------|-----------|---------------|-----------|------------------|
| **OpenAI** | text-embedding-3-large (3072d)<br>text-embedding-3-small (1536d)<br>text-embedding-ada-002 (1536d) | gpt-4o-mini<br>gpt-4 | - | OPENAI_API_KEY |
| **Anthropic** | - | claude-haiku-4-5-20251001<br>claude-sonnet-4-5-20250219<br>claude-opus-4-6 | - | ANTHROPIC_API_KEY |
| **Ollama** | nomic-embed-text (768d)<br>mxbai-embed-large (1024d)<br>all-minilm (384d) | llama3.2<br>mistral<br>codellama | llama3.2<br>mistral | (none - local) |
| **Cohere** | embed-english-v3.0 (1024d)<br>embed-multilingual-v3.0 (1024d)<br>embed-english-light-v3.0 (384d) | - | - | COHERE_API_KEY |
| **Gemini** | - | gemini-1.5-flash<br>gemini-1.5-pro | - | GOOGLE_API_KEY |
| **Grok** | - | grok-beta | - | XAI_API_KEY |
| **SentenceTransformers** | - | - | cross-encoder/ms-marco-MiniLM-L-6-v2<br>cross-encoder/ms-marco-MiniLM-L-12-v2 | (none - local) |

**Note:** Embedding dimension count (e.g., "3072d") indicates the size of the embedding vector. Different dimensions require separate ChromaDB collections - see [Dimension Mismatch](#dimension-mismatch) for details.

## Configuration Examples

### Default Configuration (OpenAI + Anthropic)

The most common setup - OpenAI embeddings with Anthropic summarization:

```yaml
# config.yaml
embedding:
  provider: openai
  model: text-embedding-3-large
  api_key_env: OPENAI_API_KEY

summarization:
  provider: anthropic
  model: claude-haiku-4-5-20251001
  api_key_env: ANTHROPIC_API_KEY
```

**Reference:** `e2e/fixtures/config_openai.yaml`

**Required environment variables:**
```bash
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
```

### Fully Offline (Ollama Only)

Run Agent Brain with no external API calls - all processing happens locally:

```yaml
# config.yaml
embedding:
  provider: ollama
  model: nomic-embed-text
  base_url: http://localhost:11434/v1
  params:
    batch_size: 64

summarization:
  provider: ollama
  model: llama3.2
  base_url: http://localhost:11434/v1
  params:
    max_tokens: 500
    temperature: 0.3

reranker:
  provider: ollama
  model: llama3.2
  base_url: http://localhost:11434
```

**Reference:** `e2e/fixtures/config_ollama_only.yaml`

**Prerequisites:**
1. Install Ollama: https://ollama.com/download
2. Start Ollama server: `ollama serve`
3. Pull required models:
   ```bash
   ollama pull nomic-embed-text
   ollama pull llama3.2
   ```

**No API keys required** - this configuration runs entirely offline.

### Cohere Embeddings + Anthropic Summarization

Use Cohere for embeddings (different dimensions than OpenAI):

```yaml
# config.yaml
embedding:
  provider: cohere
  model: embed-english-v3.0
  api_key_env: COHERE_API_KEY

summarization:
  provider: anthropic
  model: claude-haiku-4-5-20251001
  api_key_env: ANTHROPIC_API_KEY
```

**Reference:** `e2e/fixtures/config_cohere.yaml`

**Required environment variables:**
```bash
export COHERE_API_KEY=...
export ANTHROPIC_API_KEY=sk-ant-...
```

**Important:** Cohere's embed-english-v3.0 produces 1024-dimensional embeddings, while OpenAI's text-embedding-3-large produces 3072-dimensional embeddings. Switching between them requires clearing the index (see [Dimension Mismatch](#dimension-mismatch)).

### OpenAI with Reranking Enabled

Add reranking for improved search relevance:

```yaml
# config.yaml
embedding:
  provider: openai
  model: text-embedding-3-large
  api_key_env: OPENAI_API_KEY

summarization:
  provider: anthropic
  model: claude-haiku-4-5-20251001
  api_key_env: ANTHROPIC_API_KEY

reranker:
  provider: sentence-transformers
  model: cross-encoder/ms-marco-MiniLM-L-6-v2
```

**Required environment variables:**
```bash
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
export ENABLE_RERANKING=true
```

**Note:** Reranking is disabled by default. Set `ENABLE_RERANKING=true` to activate it.

### Anthropic-Only Configuration

Use Anthropic for summarization with OpenAI embeddings (testing Anthropic-specific features):

```yaml
# config.yaml
embedding:
  provider: openai
  model: text-embedding-3-large
  api_key_env: OPENAI_API_KEY

summarization:
  provider: anthropic
  model: claude-haiku-4-5-20251001
  api_key_env: ANTHROPIC_API_KEY
```

**Reference:** `e2e/fixtures/config_anthropic.yaml`

This is the same as the default configuration but explicitly tests Anthropic summarization provider instantiation and configuration.

## Environment Variables

### API Keys

| Variable | Description | Required For | Example Format |
|----------|-------------|--------------|----------------|
| `OPENAI_API_KEY` | OpenAI API key | OpenAI embeddings/summarization | `sk-proj-...` (64 chars) |
| `ANTHROPIC_API_KEY` | Anthropic Claude API key | Anthropic summarization | `sk-ant-...` (varies) |
| `COHERE_API_KEY` | Cohere API key | Cohere embeddings | Alphanumeric string |
| `GOOGLE_API_KEY` | Google Gemini API key | Gemini summarization | `AIza...` |
| `XAI_API_KEY` | xAI Grok API key | Grok summarization | Bearer token format |

### Configuration Control

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `AGENT_BRAIN_CONFIG` | Direct path to config.yaml file | (search locations) | `/path/to/config.yaml` |
| `AGENT_BRAIN_STATE_DIR` | State directory for data and config | `.claude/agent-brain/` | `/custom/state/dir` |
| `AGENT_BRAIN_STRICT_MODE` | Fail startup on validation warnings | `false` | `true` |

### Feature Flags

| Variable | Description | Default | Values |
|----------|-------------|---------|--------|
| `ENABLE_RERANKING` | Enable two-stage reranking | `false` | `true`, `false` |

### Legacy Variables

| Variable | Description | Status |
|----------|-------------|--------|
| `DOC_SERVE_STATE_DIR` | Legacy state directory variable | Deprecated (use AGENT_BRAIN_STATE_DIR) |
| `DOC_SERVE_URL` | Legacy CLI URL variable | Deprecated |

## Validation

Agent Brain uses a dual-layer validation system to catch configuration issues early while maintaining flexibility.

### Startup Validation

When the server starts, Agent Brain validates the configuration and logs warnings or errors:

**Validation Levels:**

1. **WARNING** - Logged but doesn't prevent startup
   - Missing API keys for configured providers (you can add them later)
   - Unknown/untested model names
   - Unusual configuration parameters

2. **CRITICAL** - Prevents startup in strict mode, warning in normal mode
   - Invalid provider names
   - Missing required config fields
   - Incompatible provider/model combinations

**Example validation output:**
```
INFO: Active embedding provider: openai (model: text-embedding-3-large)
INFO: Active summarization provider: anthropic (model: claude-haiku-4-5-20251001)
WARNING: OPENAI_API_KEY not set (required for OpenAI provider)
```

### Strict Mode

Enable strict mode to fail startup on any validation warnings:

```bash
# Via environment variable
export AGENT_BRAIN_STRICT_MODE=true
agent-brain-serve

# Via CLI flag
agent-brain-serve --strict
```

**Use strict mode for:**
- Production deployments
- CI/CD pipelines
- Environments where all API keys must be present

**Don't use strict mode for:**
- Local development (you may not have all API keys)
- Testing different provider combinations
- Environments where you'll add API keys later

### Health Endpoint

Check provider configuration and availability at runtime:

```bash
curl http://localhost:8000/health/providers
```

**Example response:**
```json
{
  "status": "healthy",
  "providers": {
    "embedding": {
      "provider": "openai",
      "model": "text-embedding-3-large",
      "available": true,
      "dimensions": 3072
    },
    "summarization": {
      "provider": "anthropic",
      "model": "claude-haiku-4-5-20251001",
      "available": true
    },
    "reranker": {
      "provider": "sentence-transformers",
      "model": "cross-encoder/ms-marco-MiniLM-L-6-v2",
      "available": true,
      "enabled": false
    }
  },
  "strict_mode": false
}
```

**Available field meanings:**
- `true` - Provider is configured and ready (API key present or not required)
- `false` - Provider is configured but not available (missing API key or service unavailable)

### CLI Configuration Commands

Debug configuration issues with the CLI:

```bash
# Show current configuration
agent-brain config show

# Show which config file is being used
agent-brain config path
```

**Example output:**
```bash
$ agent-brain config path
Using config file: /Users/dev/project/.claude/agent-brain/config.yaml

$ agent-brain config show
Embedding Provider: openai
  Model: text-embedding-3-large
  Dimensions: 3072
  API Key: Set (OPENAI_API_KEY)

Summarization Provider: anthropic
  Model: claude-haiku-4-5-20251001
  API Key: Set (ANTHROPIC_API_KEY)

Reranker Provider: sentence-transformers
  Model: cross-encoder/ms-marco-MiniLM-L-6-v2
  Enabled: false
```

## Troubleshooting

### Missing API Key

**Symptom:**
```
WARNING: OPENAI_API_KEY not set (required for OpenAI provider)
```

**Solution:**
1. Set the required environment variable:
   ```bash
   export OPENAI_API_KEY=sk-proj-...
   ```
2. Restart the Agent Brain server
3. Verify with: `agent-brain config show`

**Alternative:** Use a provider that doesn't require API keys (Ollama).

### Dimension Mismatch

**Symptom:**
```
ERROR: Dimension mismatch - existing collection has 3072 dimensions,
       but current provider produces 1024 dimensions
```

**Cause:** You switched embedding providers with different vector dimensions. ChromaDB collections are dimension-specific and cannot be reused.

**Solution:**
1. Clear the existing index:
   ```bash
   agent-brain reset --yes
   ```
2. Re-index your documents with the new provider:
   ```bash
   agent-brain index /path/to/docs
   ```

**Prevention:** Use `--force` flag when switching providers:
```bash
agent-brain index /path/to/docs --force
```

**Dimension reference:**
- OpenAI text-embedding-3-large: 3072
- OpenAI text-embedding-3-small: 1536
- Cohere embed-english-v3.0: 1024
- Ollama nomic-embed-text: 768

### Ollama Not Responding

**Symptom:**
```
ERROR: Failed to connect to Ollama at http://localhost:11434
```

**Checklist:**
1. **Is Ollama running?**
   ```bash
   ollama serve
   ```
2. **Is the model pulled?**
   ```bash
   ollama list
   ollama pull nomic-embed-text
   ollama pull llama3.2
   ```
3. **Is the base URL correct?**
   - Embedding/Summarization: `http://localhost:11434/v1` (OpenAI-compatible API)
   - Reranking: `http://localhost:11434` (Native Ollama API)
4. **Check connectivity:**
   ```bash
   curl http://localhost:11434/api/tags
   ```

**Custom Ollama URL:**
If Ollama is running on a different host/port, update the config:
```yaml
embedding:
  provider: ollama
  model: nomic-embed-text
  base_url: http://192.168.1.100:11434/v1
```

### Config File Not Found

**Symptom:**
```
INFO: No config file found, using default providers
```

**Diagnosis:**
```bash
agent-brain config path
```

**Solutions:**

1. **Create config in project directory:**
   ```bash
   mkdir -p .claude/agent-brain
   cp e2e/fixtures/config_openai.yaml .claude/agent-brain/config.yaml
   ```

2. **Use AGENT_BRAIN_CONFIG:**
   ```bash
   export AGENT_BRAIN_CONFIG=/path/to/config.yaml
   ```

3. **Check search locations:**
   Agent Brain searches these locations in order:
   - `$AGENT_BRAIN_CONFIG`
   - `$AGENT_BRAIN_STATE_DIR/config.yaml`
   - `./config.yaml`
   - `.claude/agent-brain/config.yaml` (walking up from CWD)
   - `~/.agent-brain/config.yaml`
   - `~/.config/agent-brain/config.yaml`

### Cohere Authentication Error

**Symptom:**
```
ERROR: cohere.errors.Unauthorized: invalid api key
```

**Cause:** Cohere provider requires API key at instantiation time (unlike Ollama which can be instantiated without credentials).

**Solution:**
1. Ensure COHERE_API_KEY is set before starting server:
   ```bash
   export COHERE_API_KEY=your_key_here
   agent-brain-serve
   ```
2. Verify with health endpoint:
   ```bash
   curl http://localhost:8000/health/providers
   ```

**Note:** You cannot test Cohere provider instantiation without a valid API key.

### Gemini/Grok Provider Issues

**Symptom:**
```
ERROR: Failed to initialize Gemini provider
```

**Common causes:**
1. **Missing API key:**
   ```bash
   export GOOGLE_API_KEY=AIza...  # For Gemini
   export XAI_API_KEY=...          # For Grok
   ```

2. **Incorrect base URL:**
   - Grok requires `base_url: https://api.x.ai/v1` in config
   - Gemini uses default Google AI endpoint (no base_url needed)

3. **API quota/billing:**
   - Check your Google Cloud Console (Gemini)
   - Check xAI console (Grok)

## Testing Providers

### Local Testing

Test provider configurations locally before deploying:

```bash
# Test all configuration-level tests (no API keys needed)
cd agent-brain-server
poetry run pytest \
  ../e2e/integration/test_provider_openai.py::TestOpenAIConfiguration \
  ../e2e/integration/test_provider_anthropic.py::TestAnthropicConfiguration \
  ../e2e/integration/test_provider_cohere.py::TestCohereConfiguration \
  ../e2e/integration/test_provider_ollama.py::TestOllamaRerankerConfig \
  -v

# Test specific provider E2E (requires API keys)
poetry run pytest ../e2e/integration/ -m openai -v      # OpenAI tests
poetry run pytest ../e2e/integration/ -m anthropic -v   # Anthropic tests
poetry run pytest ../e2e/integration/ -m cohere -v      # Cohere tests
poetry run pytest ../e2e/integration/ -m ollama -v      # Ollama tests

# Test with specific config file
AGENT_BRAIN_CONFIG=../e2e/fixtures/config_ollama_only.yaml \
  poetry run pytest ../e2e/integration/ -m ollama -v
```

### Pytest Markers

Provider tests use pytest markers for selective execution:

| Marker | Description | Requires |
|--------|-------------|----------|
| `openai` | OpenAI embedding provider tests | OPENAI_API_KEY, ANTHROPIC_API_KEY |
| `anthropic` | Anthropic summarization provider tests | OPENAI_API_KEY, ANTHROPIC_API_KEY |
| `cohere` | Cohere embedding provider tests | COHERE_API_KEY, ANTHROPIC_API_KEY |
| `ollama` | Ollama provider tests (offline) | Ollama server running with models pulled |

**Graceful skipping:** Tests automatically skip when required API keys or services are unavailable, with clear skip messages.

### CI Testing

Agent Brain uses GitHub Actions for automated provider testing. See `.github/workflows/provider-e2e.yml` for the full workflow.

**Workflow structure:**

1. **config-tests job** - Always runs, requires no API keys
   - Tests configuration loading for all providers
   - Validates config file parsing
   - Tests health endpoint with minimal FastAPI app

2. **provider-tests job** - Matrix of 4 providers
   - Tests OpenAI, Anthropic, Cohere, Ollama separately
   - Checks for required API keys before running
   - Skips gracefully when keys unavailable
   - Uses `fail-fast: false` to allow all providers to complete

3. **ollama-service-tests job** - Optional Ollama service tests
   - Marked `continue-on-error: true` (doesn't fail workflow)
   - Requires Ollama server (usually not available in CI)
   - Documents how to run tests locally

**Triggering CI tests:**

Provider E2E tests only run when:
- Pushing to `main` or `develop` branches
- PR has `test-providers` label

Add the label to your PR to test provider changes:
```bash
gh pr edit --add-label test-providers
```

**Secrets required in CI:**
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `COHERE_API_KEY`

**Note:** CI provider tests are expensive (API calls). Only trigger them when testing provider-related changes.

### Health Endpoint Testing

Test the `/health/providers` endpoint without full server startup:

```bash
cd agent-brain-server
poetry run pytest ../e2e/integration/test_health_providers.py -v
```

**Test coverage:**
- Provider status reporting (available/unavailable)
- Strict mode enforcement
- Multiple provider configurations
- Missing API key handling
- Dimension reporting for embedding providers

## Best Practices

1. **Use environment variables for API keys** - Never hardcode keys in config files
2. **Test configuration changes locally** - Run `agent-brain config show` before deploying
3. **Clear index when switching embedding providers** - Different dimensions require separate collections
4. **Use Ollama for development** - No API costs, fully offline, fast iteration
5. **Enable strict mode in production** - Catch configuration issues at startup
6. **Monitor provider health** - Use `/health/providers` endpoint for observability
7. **Version-control your config** - Track provider configurations in git (without API keys)
8. **Document provider decisions** - Record why you chose specific providers/models

## Additional Resources

- **Provider Implementation:** `agent-brain-server/agent_brain_server/providers/`
- **Configuration Models:** `agent-brain-server/agent_brain_server/config/provider_config.py`
- **E2E Test Fixtures:** `e2e/fixtures/config_*.yaml`
- **Provider E2E Tests:** `e2e/integration/test_provider_*.py`
- **CI Workflow:** `.github/workflows/provider-e2e.yml`

## Version History

- **v1.2.0** - Added Gemini, Grok, SentenceTransformers providers
- **v1.1.0** - Added Ollama reranking provider
- **v1.0.0** - Initial pluggable provider system (OpenAI, Anthropic, Ollama, Cohere)
