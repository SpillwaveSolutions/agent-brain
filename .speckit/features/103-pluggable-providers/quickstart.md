# Quickstart: Pluggable Model Providers

**Feature**: 103-pluggable-providers
**Date**: 2026-02-01

## Overview

Agent Brain supports pluggable model providers for both embeddings and summarization. This guide shows how to configure different providers without code changes.

## Configuration File

Create a `config.yaml` file in your project root (where `.claude/doc-serve/` is located):

```yaml
# config.yaml
embedding:
  provider: openai          # openai | ollama | cohere
  model: text-embedding-3-large
  api_key_env: OPENAI_API_KEY

summarization:
  provider: anthropic       # anthropic | openai | gemini | grok | ollama
  model: claude-haiku-4-5-20251001
  api_key_env: ANTHROPIC_API_KEY
```

## Quick Setup by Provider

### Default Configuration (OpenAI + Anthropic)

No `config.yaml` needed - this is the default behavior.

**Required Environment Variables:**
```bash
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
```

---

### Fully Local with Ollama

Run completely offline using Ollama for both embeddings and summarization.

**Prerequisites:**
```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull required models
ollama pull nomic-embed-text
ollama pull llama4:scout
```

**config.yaml:**
```yaml
embedding:
  provider: ollama
  model: nomic-embed-text
  base_url: http://localhost:11434/v1

summarization:
  provider: ollama
  model: llama4:scout
  base_url: http://localhost:11434/v1
  params:
    max_tokens: 500
    temperature: 0.1
```

**No API keys needed** - Ollama runs locally.

---

### OpenAI for Everything

Use OpenAI for both embeddings and summarization.

**config.yaml:**
```yaml
embedding:
  provider: openai
  model: text-embedding-3-large
  api_key_env: OPENAI_API_KEY
  params:
    batch_size: 100

summarization:
  provider: openai
  model: gpt-5-mini
  api_key_env: OPENAI_API_KEY
  params:
    max_tokens: 300
    temperature: 0.1
```

**Required Environment Variables:**
```bash
export OPENAI_API_KEY=sk-...
```

---

### Cohere Embeddings + Claude Summarization

Use Cohere for cost-effective embeddings with Claude for high-quality summaries.

**config.yaml:**
```yaml
embedding:
  provider: cohere
  model: embed-english-v3.0
  api_key_env: COHERE_API_KEY
  params:
    input_type: search_document

summarization:
  provider: anthropic
  model: claude-haiku-4-5-20251001
  api_key_env: ANTHROPIC_API_KEY
```

**Required Environment Variables:**
```bash
export COHERE_API_KEY=...
export ANTHROPIC_API_KEY=sk-ant-...
```

---

### Gemini for Summarization

Use Google Gemini for summarization (Gemini doesn't provide embeddings).

**config.yaml:**
```yaml
embedding:
  provider: openai
  model: text-embedding-3-small
  api_key_env: OPENAI_API_KEY

summarization:
  provider: gemini
  model: gemini-3-flash
  api_key_env: GOOGLE_API_KEY
  params:
    max_output_tokens: 300
    temperature: 0.1
```

**Required Environment Variables:**
```bash
export OPENAI_API_KEY=sk-...
export GOOGLE_API_KEY=...
```

---

### Grok for Summarization

Use xAI's Grok for summarization.

**config.yaml:**
```yaml
embedding:
  provider: openai
  model: text-embedding-3-large
  api_key_env: OPENAI_API_KEY

summarization:
  provider: grok
  model: grok-4
  api_key_env: XAI_API_KEY
  base_url: https://api.x.ai/v1
```

**Required Environment Variables:**
```bash
export OPENAI_API_KEY=sk-...
export GROK_API_KEY=...
```

---

## Provider Reference

### Embedding Providers

| Provider | Models | Default Model | Dimensions |
|----------|--------|---------------|------------|
| `openai` | text-embedding-3-large, text-embedding-3-small, text-embedding-ada-002 | text-embedding-3-large | 3072 |
| `ollama` | nomic-embed-text, mxbai-embed-large, bge-base-en | nomic-embed-text | 768 |
| `cohere` | embed-english-v3.0, embed-multilingual-v3.0 | embed-english-v3.0 | 1024 |

### Summarization Providers

| Provider | Models | Default Model |
|----------|--------|---------------|
| `anthropic` | claude-haiku-4-5-20251001, claude-sonnet-4-5-20250514, claude-opus-4-5-20251101 | claude-haiku-4-5-20251001 |
| `openai` | gpt-5, gpt-5-mini | gpt-5-mini |
| `gemini` | gemini-3-flash, gemini-3-pro | gemini-3-flash |
| `grok` | grok-4, grok-4-fast | grok-4 |
| `ollama` | llama4:scout, mistral-small3.2, qwen3-coder, gemma3 | llama4:scout |

---

## Configuration Precedence

Configuration is loaded in this order (later overrides earlier):

1. **Built-in defaults** (OpenAI + Anthropic)
2. **config.yaml** in project root
3. **Environment variable** `DOC_SERVE_CONFIG` pointing to alternate config path
4. **Direct environment variables** (e.g., `EMBEDDING_PROVIDER=ollama`)

---

## Switching Providers with Existing Index

**Important:** Changing embedding providers requires re-indexing because different providers produce embeddings with different dimensions.

If you change providers after indexing, you'll see:

```
ProviderMismatchError: index was created with openai/text-embedding-3-large,
but current config uses ollama/nomic-embed-text. Re-index with --force to update.
```

**To re-index:**
```bash
# Clear existing index and re-index
agent-brain reset --yes
agent-brain index /path/to/docs
```

---

## Verifying Configuration

On startup, Agent Brain logs the active providers:

```
INFO: Embedding provider: openai (text-embedding-3-large, 3072 dims)
INFO: Summarization provider: anthropic (claude-haiku-4-5-20251001)
```

Check server status to verify:
```bash
agent-brain status
```

Output:
```
Agent Brain Status
==================
Server: Running (http://127.0.0.1:8000)
Embedding Provider: openai (text-embedding-3-large)
Summarization Provider: anthropic (claude-haiku-4-5-20251001)
Documents Indexed: 42
```

---

## Troubleshooting

### "API key not found" Error

```
ConfigurationError: [openai] API key not found in environment variable OPENAI_API_KEY
```

**Solution:** Set the environment variable specified in `api_key_env`:
```bash
export OPENAI_API_KEY=sk-...
```

### "Ollama connection refused" Error

```
ProviderError: [ollama] Connection refused to http://localhost:11434
```

**Solution:** Start Ollama:
```bash
ollama serve
```

### "Model not found" Error

```
ModelNotFoundError: [ollama] Model 'nomic-embed-text' not found
```

**Solution:** Pull the model:
```bash
ollama pull nomic-embed-text
```

### Provider Mismatch Error

```
ProviderMismatchError: index was created with openai/text-embedding-3-large...
```

**Solution:** Re-index with the new provider:
```bash
agent-brain reset --yes
agent-brain index /path/to/docs
```

---

## Environment Variable Quick Reference

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `COHERE_API_KEY` | Cohere API key |
| `GOOGLE_API_KEY` | Google/Gemini API key |
| `GROK_API_KEY` | xAI/Grok API key |
| `DOC_SERVE_CONFIG` | Path to alternate config.yaml |
| `EMBEDDING_PROVIDER` | Override embedding provider |
| `SUMMARIZATION_PROVIDER` | Override summarization provider |
