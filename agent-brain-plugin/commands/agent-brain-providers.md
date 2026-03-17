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
/agent-brain:agent-brain-providers [action]
```

### Actions

| Action | Description |
|--------|-------------|
| `list` | List all available providers (default) |
| `show` | Show current provider configuration |
| `switch` | Interactive provider switching |

## Execution

### List Available Providers

Show all supported embedding and summarization providers. This is a plugin-level informational command. To view the active provider configuration from the CLI, use:

```bash
agent-brain config show
```

Or for JSON output:

```bash
agent-brain config show --json
```

To find which config file is active:

```bash
agent-brain config path
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
1. Ollama (nomic-embed-text) - FREE, local, no API key required
2. OpenAI (text-embedding-3-large) - High quality, cloud-based
3. Cohere (embed-english-v3.0) - Multi-language support
```

**Step 3: For summarization, choose provider**
```
Which summarization provider would you like to use?

Options:
1. Ollama (llama3.2) - FREE, local, no API key required
2. Anthropic (claude-haiku-4-5-20251001) - High quality
3. OpenAI (gpt-5-mini) - Fast, cost-effective
4. Gemini (gemini-3-flash) - Google's model
5. Grok (grok-4) - xAI's model
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

## CLI Commands

Provider configuration is managed through the config file (`config.yaml`) and the CLI:

```bash
agent-brain config show           # Display active provider configuration
agent-brain config show --json    # JSON output for scripting
agent-brain config path           # Show config file location
```

## Related Commands

- `/agent-brain:agent-brain-summarizer` - Configure summarization provider specifically
- `/agent-brain:agent-brain-embeddings` - Configure embedding provider specifically
- `/agent-brain:agent-brain-verify` - Verify provider configuration works
- `/agent-brain:agent-brain-setup` - Full guided setup including provider selection
