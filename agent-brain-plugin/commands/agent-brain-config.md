---
name: agent-brain-config
description: Configure providers and API keys for Agent Brain (OpenAI, Anthropic, Ollama, Gemini)
parameters: []
skills:
  - configuring-agent-brain
---

# Configure Agent Brain

## Purpose

Guides users through configuring providers for Agent Brain. Agent Brain supports multiple providers - use Ollama for local/free operation or cloud providers like OpenAI, Anthropic, Gemini, and Grok.

## Usage

```
/agent-brain-config
```

## Execution

### Step 1: Check Current Configuration

```bash
echo "=== Current Configuration ==="
echo ""
echo "Embedding Provider: ${EMBEDDING_PROVIDER:-openai}"
echo "Embedding Model: ${EMBEDDING_MODEL:-text-embedding-3-large}"
echo ""
echo "Summarization Provider: ${SUMMARIZATION_PROVIDER:-anthropic}"
echo "Summarization Model: ${SUMMARIZATION_MODEL:-claude-haiku-4-5-20251001}"
echo ""
echo "=== API Keys Status ==="
echo "OPENAI_API_KEY: ${OPENAI_API_KEY:+SET}"
echo "ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:+SET}"
echo "GOOGLE_API_KEY: ${GOOGLE_API_KEY:+SET}"
echo "XAI_API_KEY: ${XAI_API_KEY:+SET}"
echo "COHERE_API_KEY: ${COHERE_API_KEY:+SET}"
```

### Step 2: Use AskUserQuestion for Provider Selection

```
Which provider setup would you like?

Options:
1. Ollama (Local) - FREE, no API keys required, runs locally
2. OpenAI + Anthropic - Best quality, requires API keys
3. Google Gemini - Google's models, requires GOOGLE_API_KEY
4. Custom Mix - Choose different providers for embedding/summarization
```

### Step 3: Based on Selection

**For Ollama (Option 1):**

```
=== Ollama Setup (Local, Free) ===

Ollama runs locally - no API keys or cloud costs!

1. Install Ollama (if not installed):

   macOS:   brew install ollama
   Linux:   curl -fsSL https://ollama.com/install.sh | sh
   Windows: Download from https://ollama.com/download

2. Start Ollama server:
   ollama serve

3. Pull required models:
   ollama pull nomic-embed-text      # For embeddings
   ollama pull llama3.2              # For summarization

4. Configure environment:
   export EMBEDDING_PROVIDER=ollama
   export EMBEDDING_MODEL=nomic-embed-text
   export SUMMARIZATION_PROVIDER=ollama
   export SUMMARIZATION_MODEL=llama3.2

5. Start Agent Brain:
   /agent-brain-start

No API keys needed!
```

**For OpenAI + Anthropic (Option 2):**

```
=== Cloud Provider Setup ===

OpenAI (Embeddings):
1. Get key: https://platform.openai.com/account/api-keys
2. Set: export OPENAI_API_KEY="sk-proj-..."

Anthropic (Summarization):
1. Get key: https://console.anthropic.com/
2. Set: export ANTHROPIC_API_KEY="sk-ant-..."

Configuration:
export EMBEDDING_PROVIDER=openai
export EMBEDDING_MODEL=text-embedding-3-large
export SUMMARIZATION_PROVIDER=anthropic
export SUMMARIZATION_MODEL=claude-haiku-4-5-20251001
```

**For Gemini (Option 3):**

```
=== Google Gemini Setup ===

1. Get key: https://aistudio.google.com/apikey
2. Set: export GOOGLE_API_KEY="AIza..."

Configuration (Gemini for both):
export EMBEDDING_PROVIDER=gemini
export EMBEDDING_MODEL=text-embedding-004
export SUMMARIZATION_PROVIDER=gemini
export SUMMARIZATION_MODEL=gemini-2.0-flash
```

**For Custom Mix (Option 4):**

Redirect to: `/agent-brain-providers switch`

## Output

### Initial Status Display

```
Agent Brain Configuration
=========================

Current Configuration:
  Embedding:      ollama / nomic-embed-text
  Summarization:  ollama / llama3.2

Provider Options:
-----------------

1. OLLAMA (Local, Free)
   - No API keys required
   - Runs on your machine
   - Models: nomic-embed-text, llama3.2
   - Setup: ollama serve

2. OPENAI + ANTHROPIC (Cloud)
   - Best quality embeddings and summaries
   - Requires: OPENAI_API_KEY, ANTHROPIC_API_KEY
   - Models: text-embedding-3-large, claude-haiku

3. GOOGLE GEMINI (Cloud)
   - Google's models
   - Requires: GOOGLE_API_KEY
   - Models: text-embedding-004, gemini-2.0-flash

4. CUSTOM MIX
   - Choose different providers for each function
   - Run: /agent-brain-providers switch

Which setup would you like? (Enter 1-4)
```

### Ollama Setup Complete

```
Ollama Configuration Complete!
==============================

Environment Variables Set:
  EMBEDDING_PROVIDER=ollama
  EMBEDDING_MODEL=nomic-embed-text
  SUMMARIZATION_PROVIDER=ollama
  SUMMARIZATION_MODEL=llama3.2

To make permanent, add to ~/.zshrc or ~/.bashrc:

  export EMBEDDING_PROVIDER=ollama
  export EMBEDDING_MODEL=nomic-embed-text
  export SUMMARIZATION_PROVIDER=ollama
  export SUMMARIZATION_MODEL=llama3.2

Next steps:
1. Ensure Ollama is running: ollama serve
2. Initialize project: /agent-brain-init
3. Start server: /agent-brain-start
```

## Error Handling

### Ollama Not Installed

```
Ollama not found. Install with:

macOS:   brew install ollama
Linux:   curl -fsSL https://ollama.com/install.sh | sh
Windows: https://ollama.com/download
```

### Ollama Not Running

```
Ollama is installed but not running.

Start it with: ollama serve

Then pull models:
  ollama pull nomic-embed-text
  ollama pull llama3.2
```

### Missing API Key for Cloud Provider

```
Cloud provider selected but API key not set.

For OpenAI:    export OPENAI_API_KEY="sk-proj-..."
For Anthropic: export ANTHROPIC_API_KEY="sk-ant-..."
For Google:    export GOOGLE_API_KEY="AIza..."
For xAI:       export XAI_API_KEY="xai-..."
```

## Security Guidance

**For cloud providers:**
- Never commit API keys to version control
- Add `.env` files to `.gitignore`
- Use environment variables, not hardcoded values

**For Ollama:**
- Runs locally - no keys to manage
- Data stays on your machine

## Related Commands

- `/agent-brain-providers` - List all available providers
- `/agent-brain-providers switch` - Interactive provider switching
- `/agent-brain-embeddings` - Configure embedding provider only
- `/agent-brain-summarizer` - Configure summarization provider only
- `/agent-brain-verify` - Verify provider configuration works
