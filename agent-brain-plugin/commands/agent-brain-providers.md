---
name: agent-brain-providers
description: List and configure embedding and summarization providers
parameters:
  - name: action
    description: Action to perform (list, show, switch)
    required: false
    default: list
skills:
  - using-agent-brain
---

# Agent Brain Providers

## Purpose

Lists available providers and shows current configuration for embeddings and summarization. Use this command to understand what providers are available and which are currently active.

## Usage

```
/agent-brain-providers [action]
```

### Actions

| Action | Description |
|--------|-------------|
| `list` | List all available providers (default) |
| `show` | Show current provider configuration |
| `switch` | Interactive provider switching |

## Execution

### List Available Providers

Show all supported embedding and summarization providers:

```bash
# Display provider information
echo "=== Embedding Providers ==="
echo "1. OpenAI (text-embedding-3-large, text-embedding-3-small)"
echo "2. Cohere (embed-english-v3.0, embed-multilingual-v3.0)"
echo "3. Ollama (nomic-embed-text, mxbai-embed-large) - Local"
echo ""
echo "=== Summarization Providers ==="
echo "1. Anthropic (claude-haiku-4-5-20251001, claude-sonnet-4-5-20250514)"
echo "2. OpenAI (gpt-5, gpt-5-mini)"
echo "3. Gemini (gemini-3-flash, gemini-3-pro)"
echo "4. Grok (grok-4)"
echo "5. Ollama (llama4:scout, mistral-small3.2, qwen3-coder) - Local"
```

### Show Current Configuration

```bash
# Check environment variables
echo "Current Embedding Provider: ${EMBEDDING_PROVIDER:-openai}"
echo "Current Embedding Model: ${EMBEDDING_MODEL:-text-embedding-3-large}"
echo "Current Summarization Provider: ${SUMMARIZATION_PROVIDER:-anthropic}"
echo "Current Summarization Model: ${SUMMARIZATION_MODEL:-claude-haiku-4-5-20251001}"
```

### Interactive Provider Switch

When action is `switch`, use AskUserQuestion to guide the user:

**Step 1: Choose what to configure**
```
What would you like to configure?

Options:
1. Embedding Provider - For vector/semantic search
2. Summarization Provider - For code summaries during indexing
3. Both - Configure both providers
```

**Step 2: For embeddings, choose provider**
```
Which embedding provider would you like to use?

Options:
1. OpenAI (text-embedding-3-large) - High quality, cloud-based
2. Cohere (embed-english-v3.0) - Multi-language support
3. Ollama (nomic-embed-text) - Local, no API key required
```

**Step 3: For summarization, choose provider**
```
Which summarization provider would you like to use?

Options:
1. Anthropic (claude-haiku-4-5-20251001) - High quality
2. OpenAI (gpt-5-mini) - Fast, cost-effective
3. Gemini (gemini-3-flash) - Google's model
4. Grok (grok-4) - xAI's model
5. Ollama (llama4:scout) - Local, no API key required
```

**Step 4: Generate configuration**

Based on selections, output the configuration:

```bash
# Add to your .env file or export:
export EMBEDDING_PROVIDER=<selected>
export EMBEDDING_MODEL=<selected>
export SUMMARIZATION_PROVIDER=<selected>
export SUMMARIZATION_MODEL=<selected>
```

## Output

### Provider List Output

```
=== Embedding Providers ===

Provider    | Models                              | API Key Required
------------|-------------------------------------|------------------
OpenAI      | text-embedding-3-large/small        | OPENAI_API_KEY
Cohere      | embed-english-v3.0, multilingual    | COHERE_API_KEY
Ollama      | nomic-embed-text, mxbai-embed-large | None (local)

=== Summarization Providers ===

Provider    | Models                                       | API Key Required
------------|----------------------------------------------|------------------
Anthropic   | claude-haiku-4-5-20251001, claude-sonnet-4-5-20250514 | ANTHROPIC_API_KEY
OpenAI      | gpt-5, gpt-5-mini                            | OPENAI_API_KEY
Gemini      | gemini-3-flash, gemini-3-pro                 | GOOGLE_API_KEY
Grok        | grok-4                                       | XAI_API_KEY
Ollama      | llama4:scout, mistral-small3.2, qwen3-coder  | None (local)
```

### Current Configuration Output

```
=== Current Provider Configuration ===

Embedding:
  Provider: openai
  Model: text-embedding-3-large
  API Key: OPENAI_API_KEY (set)

Summarization:
  Provider: anthropic
  Model: claude-haiku-4-5-20251001
  API Key: ANTHROPIC_API_KEY (set)
```

## Error Handling

### Provider Not Available

```
Warning: Ollama provider selected but Ollama is not running.
Start Ollama with: ollama serve
```

### Missing API Key

```
Warning: OpenAI provider selected but OPENAI_API_KEY is not set.
Set it with: export OPENAI_API_KEY="sk-proj-..."
```

## Related Commands

- `/agent-brain-embeddings` - Configure embedding provider specifically
- `/agent-brain-summarizer` - Configure summarization provider specifically
- `/agent-brain-verify` - Verify provider configuration works
