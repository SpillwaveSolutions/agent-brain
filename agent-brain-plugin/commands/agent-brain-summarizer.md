---
name: agent-brain-summarizer
description: Configure the summarization provider for code summaries
parameters:
  - name: provider
    description: Summarization provider (anthropic, openai, gemini, grok, ollama)
    required: false
  - name: model
    description: Model name for the provider
    required: false
skills:
  - using-agent-brain
---

# Agent Brain Summarizer Configuration

## Purpose

Configures the summarization provider used during document indexing. Summarization generates concise descriptions of code and documents to improve search relevance.

## Usage

```
/agent-brain-summarizer [provider] [--model <model>]
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| provider | No | - | Provider: anthropic, openai, gemini, grok, ollama |
| --model | No | Provider default | Specific model to use |

## Available Providers

### Anthropic

High-quality code-aware summarization.

| Model | Speed | Use Case |
|-------|-------|----------|
| claude-haiku-4-5-20251001 | Fast | Cost-effective, good quality |
| claude-sonnet-4-5-20250514 | Medium | Balanced quality/speed |
| claude-opus-4-5-20251101 | Slower | Highest quality |

**Configuration:**
```bash
export SUMMARIZATION_PROVIDER=anthropic
export SUMMARIZATION_MODEL=claude-haiku-4-5-20251001
export ANTHROPIC_API_KEY=sk-ant-...
```

### OpenAI

Versatile summarization with good code understanding.

| Model | Speed | Use Case |
|-------|-------|----------|
| gpt-5-mini | Fast | Cost-effective |
| gpt-5 | Medium | High quality |

**Configuration:**
```bash
export SUMMARIZATION_PROVIDER=openai
export SUMMARIZATION_MODEL=gpt-5-mini
export OPENAI_API_KEY=sk-proj-...
```

### Gemini

Google's models with large context windows.

| Model | Speed | Use Case |
|-------|-------|----------|
| gemini-3-flash | Fast | Cost-effective |
| gemini-3-pro | Medium | Higher quality |

**Configuration:**
```bash
export SUMMARIZATION_PROVIDER=gemini
export SUMMARIZATION_MODEL=gemini-3-flash
export GOOGLE_API_KEY=...
```

### Grok

xAI's conversational model.

| Model | Speed | Use Case |
|-------|-------|----------|
| grok-4 | Medium | General use |

**Configuration:**
```bash
export SUMMARIZATION_PROVIDER=grok
export SUMMARIZATION_MODEL=grok-4
export XAI_API_KEY=...
```

### Ollama (Local)

Privacy-first local summarization.

| Model | Speed | Use Case |
|-------|-------|----------|
| llama4:scout | Fast | General purpose, lightweight |
| mistral-small3.2 | Fast | Balanced |
| qwen3-coder | Medium | Code-focused |
| gemma3 | Fast | Efficient |
| deepseek-coder-v3 | Medium | Code-optimized |

**Configuration:**
```bash
export SUMMARIZATION_PROVIDER=ollama
export SUMMARIZATION_MODEL=llama4:scout
export OLLAMA_BASE_URL=http://localhost:11434
```

**Setup:**
```bash
# Pull the model first
ollama pull llama4:scout
```

## Execution

### Interactive Configuration

If no provider is specified, use AskUserQuestion:

```
Which summarization provider would you like to use?

Options:
1. Anthropic (claude-haiku-4-5-20251001) - High quality, code-aware (Recommended)
2. OpenAI (gpt-5-mini) - Fast, cost-effective
3. Gemini (gemini-3-flash) - Large context support
4. Grok (grok-4) - xAI's model
5. Ollama (llama4:scout) - Local, no API key required
```

### Direct Configuration

```bash
# Set to Anthropic
/agent-brain-summarizer anthropic --model claude-haiku-4-5-20251001

# Set to OpenAI
/agent-brain-summarizer openai --model gpt-5-mini

# Set to Ollama
/agent-brain-summarizer ollama --model llama4:scout
```

### Apply Configuration

Generate the export commands:

```bash
# Add to your shell profile or .env file:
export SUMMARIZATION_PROVIDER=anthropic
export SUMMARIZATION_MODEL=claude-haiku-4-5-20251001
```

Or update the project configuration:

```bash
agent-brain config set summarization_provider anthropic
agent-brain config set summarization_model claude-haiku-4-5-20251001
```

## Post-Configuration

After changing summarization providers, you may want to re-index to use the new summarizer:

```bash
# Re-index to apply new summarization
agent-brain reset --yes
agent-brain index /path/to/docs
```

**Note:** Changing summarization provider doesn't require re-indexing for existing searches to work, but new summaries won't be generated until re-indexing.

## Verification

```bash
# Verify summarization provider is working
agent-brain verify

# Test summarization
agent-brain test-summarize "def hello_world():\n    print('Hello, World!')"
```

## Output

### Configuration Applied

```
Summarization Provider Configuration
====================================
Provider: anthropic
Model: claude-haiku-4-5-20251001
API Key: ANTHROPIC_API_KEY (configured)

Configuration saved. Re-index recommended for new summaries.
```

### Provider Comparison

```
Summarization Provider Comparison
=================================
                  | Anthropic     | OpenAI        | Gemini        | Ollama
------------------|---------------|---------------|---------------|-------------
Quality           | Excellent     | Very Good     | Good          | Good
Code Awareness    | Excellent     | Very Good     | Good          | Varies
Speed             | Fast          | Fast          | Fast          | Varies
Cost (1M tokens)  | $0.80 input   | $0.50 input   | $0.10 input   | Free
Privacy           | Cloud         | Cloud         | Cloud         | Local
```

## Error Handling

### Invalid Provider

```
Error: Unknown provider 'xyz'.
Valid options: anthropic, openai, gemini, grok, ollama
```

### Model Not Available

```
Error: Model 'invalid-model' not available for provider 'anthropic'.
Available models: claude-haiku-4-5-20251001, claude-sonnet-4-5-20250514, claude-opus-4-5-20251101
```

### Ollama Not Running

```
Error: Cannot connect to Ollama at http://localhost:11434
Resolution: Start Ollama with 'ollama serve' or check OLLAMA_BASE_URL
```

### Missing API Key

```
Error: ANTHROPIC_API_KEY not set for Anthropic provider.
Resolution: export ANTHROPIC_API_KEY="sk-ant-..."
```

## Related Commands

- `/agent-brain-providers` - List all available providers
- `/agent-brain-embeddings` - Configure embedding provider
- `/agent-brain-verify` - Verify configuration
