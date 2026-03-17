---
name: agent-brain-embeddings
description: Configure the embedding provider for vector search
parameters:
  - name: provider
    description: Embedding provider (openai, cohere, ollama, gemini, grok, sentence-transformers)
    required: false
  - name: model
    description: Model name for the provider
    required: false
skills:
  - using-agent-brain
---

# Agent Brain Embeddings Configuration

## Purpose

Configures the embedding provider used for vector/semantic search. Embeddings convert text into numerical vectors that enable semantic similarity search.

## Usage

```
/agent-brain:agent-brain-embeddings [provider] [--model <model>]
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| provider | No | - | Provider name: openai, cohere, ollama, gemini, grok, sentence-transformers |
| --model | No | Provider default | Specific model to use |

## Available Providers

### OpenAI

Industry-standard embeddings with high quality vectors.

| Model | Dimensions | Use Case |
|-------|------------|----------|
| text-embedding-3-large | 3072 | Highest quality, production |
| text-embedding-3-small | 1536 | Faster, cost-effective |
| text-embedding-ada-002 | 1536 | Legacy, widely compatible |

**Configuration:**
```bash
export EMBEDDING_PROVIDER=openai
export EMBEDDING_MODEL=text-embedding-3-large
export OPENAI_API_KEY=sk-proj-...
```

### Cohere

Multi-language support with good quality vectors.

| Model | Dimensions | Use Case |
|-------|------------|----------|
| embed-english-v3.0 | 1024 | English content |
| embed-multilingual-v3.0 | 1024 | International content |
| embed-english-light-v3.0 | 384 | Lightweight, fast |

**Configuration:**
```bash
export EMBEDDING_PROVIDER=cohere
export EMBEDDING_MODEL=embed-english-v3.0
export COHERE_API_KEY=...
```

### Ollama (Local)

Privacy-first local embeddings with no API costs.

| Model | Dimensions | Use Case |
|-------|------------|----------|
| nomic-embed-text | 768 | General purpose |
| mxbai-embed-large | 1024 | Higher quality |
| all-minilm | 384 | Lightweight, fast |

**Configuration:**
```bash
export EMBEDDING_PROVIDER=ollama
export EMBEDDING_MODEL=nomic-embed-text
export OLLAMA_BASE_URL=http://localhost:11434
```

**Setup:**
```bash
# Pull the model first
ollama pull nomic-embed-text
```

## Execution

### Interactive Configuration

If no provider is specified, use AskUserQuestion:

```
Which embedding provider would you like to use?

Options:
1. Ollama (nomic-embed-text) - FREE, local, no API key required
2. OpenAI (text-embedding-3-large) - High quality, cloud-based
3. Cohere (embed-english-v3.0) - Multi-language support
```

### Direct Configuration

```bash
# Set to OpenAI
/agent-brain:agent-brain-embeddings openai --model text-embedding-3-large

# Set to Cohere
/agent-brain:agent-brain-embeddings cohere --model embed-english-v3.0

# Set to Ollama
/agent-brain:agent-brain-embeddings ollama --model nomic-embed-text
```

### Apply Configuration

Generate the export commands:

```bash
# Add to your shell profile or .env file:
export EMBEDDING_PROVIDER=openai
export EMBEDDING_MODEL=text-embedding-3-large
```

Or update the project config.yaml file directly:

```yaml
# .agent-brain/config.yaml or ~/.config/agent-brain/config.yaml
embedding:
  provider: "openai"
  model: "text-embedding-3-large"
  api_key_env: "OPENAI_API_KEY"
```

Verify the active configuration with:

```bash
agent-brain config show
```

## Post-Configuration

After changing embedding providers, you typically need to re-index:

```bash
# If embedding dimensions changed, reset and re-index
agent-brain reset --yes
agent-brain index /path/to/docs
```

**Note:** Switching between providers with different dimensions (e.g., OpenAI 3072 to Cohere 1024) requires re-indexing. Switching models within the same dimension size may not.

## Verification

```bash
# Verify current embedding configuration
agent-brain config show

# Test with a simple query to confirm embeddings work
agent-brain query "test query" --mode vector
```

## Output

### Configuration Applied

```
Embedding Provider Configuration
================================
Provider: openai
Model: text-embedding-3-large
Dimensions: 3072
API Key: OPENAI_API_KEY (configured)

Configuration saved. Re-index required if dimensions changed.
```

### Provider Comparison

```
Embedding Provider Comparison
=============================
                  | OpenAI        | Cohere        | Ollama
------------------|---------------|---------------|-------------
Quality           | Highest       | High          | Good
Speed             | Fast          | Fast          | Varies
Cost              | $0.13/1M tok  | $0.10/1M tok  | Free
Privacy           | Cloud         | Cloud         | Local
Dimensions        | 1536-3072     | 384-1024      | 384-1024
Multi-language    | Limited       | Excellent     | Limited
```

## Error Handling

### Invalid Provider

```
Error: Unknown provider 'xyz'. Valid options: openai, cohere, ollama, gemini, grok, sentence-transformers
```

### Model Not Available

```
Error: Model 'invalid-model' not available for provider 'openai'.
Available models: text-embedding-3-large, text-embedding-3-small, text-embedding-ada-002
```

### Ollama Not Running

```
Error: Cannot connect to Ollama at http://localhost:11434
Resolution: Start Ollama with 'ollama serve' or check OLLAMA_BASE_URL
```

### Missing API Key

```
Error: OPENAI_API_KEY not set for OpenAI provider.
Resolution: export OPENAI_API_KEY="sk-proj-..."
```

## Related Commands

- `/agent-brain:agent-brain-config` - View active provider configuration
- `/agent-brain:agent-brain-cache` - Manage embedding cache (clear after provider change)
- `/agent-brain:agent-brain-index` - Re-index documents after provider change
