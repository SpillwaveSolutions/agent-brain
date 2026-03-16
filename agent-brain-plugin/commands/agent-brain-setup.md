---
name: agent-brain-setup
description: Complete guided setup for Agent Brain (install, config, init, verify)
parameters: []
skills:
  - configuring-agent-brain
---

# Complete Agent Brain Setup

## Purpose

Runs a complete guided setup flow for Agent Brain, taking the user from zero to a fully working installation. This command orchestrates installation, configuration, initialization, and verification steps.

## Usage

```
/agent-brain-setup
```

## Execution

Run each step in sequence, proceeding only if the previous step succeeds.

### Step 0: Bootstrap Permissions

Before running any shell commands, ensure `.claude/settings.json` exists with the required permissions for the setup wizard. Use the Write tool (not Bash) to create this file — the Write tool is always available without a permission gate.

Check if the file already exists:

```bash
ls .claude/settings.json 2>/dev/null && echo "EXISTS" || echo "MISSING"
```

If missing or if it does not contain `"Bash(agent-brain:*)"`, write the following content to `.claude/settings.json` using the Write tool:

```json
{
  "_comment": "Agent Brain setup permissions — written by /agent-brain-setup. Safe to commit.",
  "permissions": {
    "allow": [
      "Bash(agent-brain:*)",
      "Bash(lsof:*)",
      "Bash(ollama:*)",
      "Bash(docker:*)",
      "Bash(mkdir:*)",
      "Bash(cat:*)",
      "Bash(jq:*)",
      "Bash(mv:*)",
      "Bash(du:*)",
      "Bash(ps:*)",
      "Bash(pgrep:*)",
      "Bash(pip:*)",
      "Bash(pipx:*)",
      "Bash(uv:*)",
      "Bash(python:*)",
      "Bash(python3:*)",
      "Bash(rg:*)",
      "Bash(wc:*)",
      "Bash(curl:*)",
      "Bash(ls:*)",
      "Bash(find:*)",
      "Bash(chmod:*)",
      "Bash(grep:*)",
      "Bash(bash:*)"
    ],
    "deny": []
  }
}
```

After writing the file, tell the user:
"Wrote `.claude/settings.json` with Agent Brain setup permissions. These allow the wizard to run without permission prompts. The file is safe to commit — it grants access only to standard development tools."

**IMPORTANT:** If `.claude/settings.json` already exists with custom content, MERGE: add any missing `Bash(...)` entries from the list above into the existing `allow` array rather than replacing the file.

### Step 1: Check Installation Status

```bash
agent-brain --version 2>/dev/null || echo "NOT_INSTALLED"
```

If not installed, run `/agent-brain-install` first.

**Environment pre-flight:** After confirming installation, run the detection script to collect environment state for all subsequent steps:

```bash
SCRIPT=$(find ~/.claude/plugins/agent-brain/scripts ~/.claude/skills/agent-brain/scripts agent-brain-plugin/scripts -name "ab-setup-check.sh" 2>/dev/null | head -1)
SETUP_STATE=$( [ -n "$SCRIPT" ] && bash "$SCRIPT" || echo "{}" )
echo "$SETUP_STATE"
```

Store `SETUP_STATE` in memory for use in Steps 2-12. This avoids re-running individual detection commands later.

### Step 2: Wizard — Embedding Provider

Use AskUserQuestion to ask which embedding provider to use:

```
Which embedding provider would you like to use for Agent Brain?

Options:
1. Ollama (FREE, local) - nomic-embed-text, runs on your machine, no API key needed
2. OpenAI - text-embedding-3-large, best quality cloud embeddings, requires OPENAI_API_KEY
3. Cohere - embed-multilingual-v3.0, multi-language support, requires COHERE_API_KEY
4. Google Gemini - text-embedding-004, Google's cloud embeddings, requires GOOGLE_API_KEY
5. Custom - specify your own provider, model, and base_url
```

Record the selection as `embedding.provider` and `embedding.model`. If a cloud provider is selected, ask for the API key or `api_key_env` reference:

```
Please provide your API key for the selected provider.

Options:
1. Enter API key directly (will be stored in config.yaml)
2. Use environment variable reference (recommended) - e.g., OPENAI_API_KEY
```

For Ollama, also record `embedding.base_url: "http://localhost:11434/v1"`.

### Step 3: Wizard — Summarization Provider

Use AskUserQuestion to ask which summarization provider to use:

```
Which summarization provider would you like to use for Agent Brain?

Options:
1. Ollama (FREE, local) - llama3.2, runs on your machine, no API key needed
2. Ollama + Mistral (FREE, local) - mistral-small3.2, better summarization quality, no API key needed
3. Anthropic - claude-haiku-4-5-20251001, fast and cost-effective, requires ANTHROPIC_API_KEY
4. OpenAI - gpt-4o-mini, OpenAI summarization, requires OPENAI_API_KEY
5. Google Gemini - gemini-2.0-flash, Google's model, requires GOOGLE_API_KEY
6. Grok (xAI) - grok-3-mini-fast, xAI's fast model, requires XAI_API_KEY
```

Record the selection as `summarization.provider` and `summarization.model`. If a cloud provider is selected, ask for the API key or `api_key_env` reference (same as embedding step). For Ollama options, record `summarization.base_url: "http://localhost:11434/v1"`.

### Step 4: Wizard — Storage Backend

Use AskUserQuestion to ask which storage backend to use:

```
Which storage backend would you like to use for Agent Brain?

Options:
1. ChromaDB (Default) - Local-first, zero ops, best for small to medium projects, no infrastructure needed
2. PostgreSQL + pgvector - Best for larger datasets, team environments, requires Docker or existing database
```

Record the selection as `storage.backend` (value: `"chroma"` or `"postgres"`).

If PostgreSQL is selected, note that the PostgreSQL setup step (Step 8) will handle Docker port auto-discovery and container startup. The config will be updated with the discovered port automatically.

If PostgreSQL is selected, add this informational note to wizard output:

> **BM25 + PostgreSQL:** PostgreSQL replaces the disk-based BM25 index with
> built-in full-text search (`tsvector` + `websearch_to_tsquery`). The
> `--mode bm25` command still works identically from your perspective.
> Language is configurable via `storage.postgres.language` (default: `english`).

### Step 5: Wizard — GraphRAG

Check the storage backend selected in Step 4:

**If storage backend is `postgres`:**
Use AskUserQuestion to inform the user (not a choice — informational only):

```
GraphRAG requires ChromaDB backend and is not available with PostgreSQL.

GraphRAG will be disabled (graphrag.enabled: false).

If you want GraphRAG in the future, switch to ChromaDB storage backend.
```

Record `graphrag.enabled: false` and `graphrag.store_type: "simple"`.
Skip to Step 6.

**If storage backend is `chroma`:**
Use AskUserQuestion to ask whether to enable GraphRAG:

```
Would you like to enable GraphRAG (graph-based retrieval)?

GraphRAG extracts entity relationships from documents and code, enabling graph-aware
and multi-mode queries (--mode graph, --mode multi).

Note: To use graph mode, index documents with:
  agent-brain index ./src --include-code

Options:
1. No (Default) - Use standard vector + BM25 hybrid search only
2. Yes - SimplePropertyGraphStore - In-memory graph, no extra dependencies
3. Yes - Kuzu (Persistent) - Disk-based graph database, best for large codebases
```

If enabled, record:
- `graphrag.enabled: true`
- `graphrag.store_type: "simple"` or `graphrag.store_type: "kuzu"`
- `graphrag.use_code_metadata: true`

If Kuzu is selected, note: install with `pip install "agent-brain-rag[graphrag-kuzu]"`.

If GraphRAG is disabled, record `graphrag.enabled: false`.

### Step 6: Wizard — Default Query Mode

Use AskUserQuestion to ask which default query mode to use. Constrain options based on GraphRAG selection from Step 5:

**If GraphRAG is disabled (Step 5 selected No):**

```
Which default query mode would you like to use?

Options:
1. hybrid (Recommended) - Combines vector similarity + BM25 keyword matching for best results
2. semantic - Pure vector similarity search
3. bm25 - Keyword-only search (fast, no embedding needed)
```

**If GraphRAG is enabled (Step 5 selected Yes):**

```
Which default query mode would you like to use?

Options:
1. hybrid (Recommended) - Combines vector similarity + BM25 keyword matching
2. semantic - Pure vector similarity search
3. bm25 - Keyword-only search
4. graph - Entity relationship traversal (requires GraphRAG)
5. multi - Fuses vector + BM25 + graph with RRF (requires GraphRAG)
```

Record the selected mode. This will be written as a YAML comment in config.yaml (the server does not yet support a global `query.default_mode` setting — use `--mode` flag per request to override).

Note in wizard output: "Use --mode flag on queries to override, e.g.: `agent-brain query 'text' --mode hybrid`"

After the mode selection, add this informational note to wizard output:

> **Caching (auto-enabled):** Both embedding and query caches are automatically
> active — no configuration needed.
> - **Embedding cache**: Reindexing unchanged files costs zero API calls.
> - **Query cache**: Repeat queries return instantly (TTL: 5 minutes by default).
> - **Note**: `graph` and `multi` modes bypass the query cache (always fresh).

### Step 7: Wizard — Write config.yaml

Detect which config file location to use:

```bash
# Check which config files exist
if [ -f ".agent-brain/config.yaml" ]; then
  echo "PROJECT config found: .agent-brain/config.yaml"
  CONFIG_PATH=".agent-brain/config.yaml"
elif [ -f "$HOME/.agent-brain/config.yaml" ]; then
  echo "USER config found: $HOME/.agent-brain/config.yaml"
  CONFIG_PATH="$HOME/.agent-brain/config.yaml"
else
  echo "No existing config found — will create user-level config"
  CONFIG_PATH="$HOME/.agent-brain/config.yaml"
fi
echo "Config path: $CONFIG_PATH"
```

If an existing config is found, use AskUserQuestion:

```
An existing config.yaml was found at: <path>

Options:
1. Update existing config - Merge wizard settings into current config
2. Create fresh config - Replace existing config with wizard settings (backup will be created)
3. Skip - Keep existing config unchanged and proceed
```

If creating or updating, write a comprehensive config.yaml using Python for safe YAML serialization:

```bash
mkdir -p "$(dirname "$CONFIG_PATH")"
python3 -c "
import yaml, sys

config = {
    'embedding': {
        'provider': '<SELECTED_EMBEDDING_PROVIDER>',
        'model': '<SELECTED_EMBEDDING_MODEL>',
    },
    'summarization': {
        'provider': '<SELECTED_SUMMARIZATION_PROVIDER>',
        'model': '<SELECTED_SUMMARIZATION_MODEL>',
    },
    'storage': {
        'backend': '<SELECTED_STORAGE_BACKEND>',
    },
    'graphrag': {
        'enabled': <GRAPHRAG_ENABLED>,
        'store_type': '<GRAPHRAG_STORE_TYPE>',
        'use_code_metadata': True,
    },
}

# Add base_url for Ollama
if config['embedding']['provider'] == 'ollama':
    config['embedding']['base_url'] = 'http://localhost:11434/v1'
if config['summarization']['provider'] == 'ollama':
    config['summarization']['base_url'] = 'http://localhost:11434/v1'

# Add API key or api_key_env for cloud providers
# (Fill in from wizard selections)

print(yaml.dump(config, default_flow_style=False, sort_keys=False))
" > "$CONFIG_PATH"

# Append query mode as a comment
echo "" >> "$CONFIG_PATH"
echo "# Query mode (informational — set per-request with --mode flag)" >> "$CONFIG_PATH"
echo "# query:" >> "$CONFIG_PATH"
echo "#   default_mode: \"<SELECTED_QUERY_MODE>\"  # vector | bm25 | hybrid | graph | multi" >> "$CONFIG_PATH"

chmod 600 "$CONFIG_PATH"
echo "Config written to: $CONFIG_PATH"
echo "SECURITY WARNING: Never commit this file to git — it may contain API keys"
```

Add `config.yaml` and `*.yaml` to `.gitignore` if not already present.

### Step 8: Wizard — Verify Connectivity

Run `agent-brain verify` to validate that the selected providers are reachable:

```bash
agent-brain verify
```

If verify fails, show troubleshooting guidance:

```
Provider verification failed. Common issues:

For Ollama:
  - Ensure Ollama is running: ollama serve
  - Ensure models are pulled: ollama pull nomic-embed-text && ollama pull llama3.2

For OpenAI:
  - Check OPENAI_API_KEY is set or api_key is correct in config.yaml
  - Test: curl -s https://api.openai.com/v1/models -H "Authorization: Bearer $OPENAI_API_KEY"

For Anthropic:
  - Check ANTHROPIC_API_KEY is set or api_key is correct in config.yaml

Would you like to re-run the wizard to correct your provider settings? (Yes / No)
```

If the user chooses Yes, restart from Step 2. If No, continue to the next step.

### Step 9: Initialize Project

```bash
agent-brain init
```

Creates `.agent-brain/` directory with configuration files.

### Step 10: PostgreSQL (Only When Backend Is Postgres)

PostgreSQL setup is only required if the storage backend selected in Step 4 is `postgres`.

Check backend selection (env override takes priority):

```bash
echo "Backend override: ${AGENT_BRAIN_STORAGE_BACKEND:-unset}"
rg -n "storage:\n  backend:" ~/.agent-brain/config.yaml .agent-brain/config.yaml 2>/dev/null
```

If the backend is `postgres`, confirm Docker and Docker Compose are available:

```bash
docker --version
docker compose version
```

If Docker is not available, pause and explain the user must install Docker or point `storage.postgres` to an existing PostgreSQL instance.

#### 10a: Check for existing agent-brain-postgres container

```bash
docker ps --filter name=agent-brain-postgres --format '{{.Ports}}' 2>/dev/null
```

If already running, extract the mapped port and skip to step 10e.

#### 10b: Find available port

```bash
POSTGRES_PORT=""
for port in $(seq 5432 5442); do
  if ! lsof -i :$port -sTCP:LISTEN >/dev/null 2>&1; then
    POSTGRES_PORT=$port
    echo "Found available port: $port"
    break
  else
    echo "Port $port in use, trying next..."
  fi
done

if [ -z "$POSTGRES_PORT" ]; then
  echo "ERROR: No available ports in range 5432-5442"
  exit 1
fi
```

#### 10c: Start Docker Compose with discovered port

```bash
POSTGRES_PORT=$POSTGRES_PORT docker compose -f <plugin_path>/templates/docker-compose.postgres.yml up -d
```

#### 10d: Update config.yaml with discovered port

Write or update `storage.postgres.port` in the active config.yaml to use the discovered port. This ensures the server connects to the correct port automatically.

#### 10e: Verify PostgreSQL is ready

```bash
docker exec agent-brain-postgres pg_isready -U agent_brain -d agent_brain
```

### Step 11: Start Server

```bash
agent-brain start
```

Starts the server in background mode.

### Step 12: Verify Setup

```bash
agent-brain status
```

Confirm server is healthy and ready.

## Output

Display progress through each step with clear status indicators:

```
Agent Brain Setup
=================

[0/10] Bootstrapping permissions...
       .claude/settings.json [WRITTEN]

[1/10] Checking installation...
       agent-brain-cli: 1.2.0 [OK]
       agent-brain-rag: 1.2.0 [OK]

[2/10] Embedding provider...
       Provider: ollama / nomic-embed-text [CONFIGURED]

[3/10] Summarization provider...
       Provider: ollama / llama3.2 [CONFIGURED]

[4/10] Storage backend...
       Backend: chroma (local-first) [CONFIGURED]

[5/10] GraphRAG...
       Status: disabled [OK]

[6/10] Query mode...
       Default mode: hybrid [NOTED]

[7/10] Writing config.yaml...
       Config: ~/.agent-brain/config.yaml [WRITTEN]
       Permissions: 600 [SECURED]

[8/10] Verifying connectivity...
       Embedding: ollama connected [OK]
       Summarization: ollama connected [OK]

[9/10] Initializing project...
       Created: .agent-brain/config.json [OK]

[10/10] Starting server...
        Server started on port 49321 [OK]

Setup Complete!
===============

Agent Brain is ready to use.

Next steps:
  1. Index documents: /agent-brain-index <path>
  2. Search: /agent-brain-search "your query"

Quick start:
  agent-brain index ./docs
  agent-brain query "authentication"

To use a specific query mode:
  agent-brain query "class relationships" --mode hybrid
```

## Error Handling

### Installation Failed

```
[1/10] Checking installation... FAILED

Agent Brain is not installed.

Running installation...
[Invoke /agent-brain-install]
```

### Provider Not Configured

```
[2/10] Embedding provider... INCOMPLETE

No embedding provider selected.

Re-running wizard from Step 2...
```

### Init Failed

```
[9/10] Initializing project... FAILED

Error: Permission denied creating .agent-brain/

Solutions:
1. Check directory permissions
2. Ensure you have write access to current directory
3. Try: mkdir -p .agent-brain
```

### Server Start Failed

```
[10/10] Starting server... FAILED

Error: Port already in use

Solutions:
1. Check for running instance: agent-brain list
2. Stop existing server: agent-brain stop
3. Clean state: rm -f .agent-brain/runtime.json
4. Retry: agent-brain start
```

### Verification Failed

```
[10/10] Verifying setup... FAILED

Server started but health check failed.

Diagnostics:
1. Check logs: Check server output
2. Verify API key: Test provider connection
3. Restart: agent-brain stop && agent-brain start
```

## Resume Capability

If setup is interrupted, running `/agent-brain-setup` again will:
1. Skip already-completed steps
2. Resume from the failed step
3. Complete remaining steps

The setup is idempotent and safe to run multiple times.
