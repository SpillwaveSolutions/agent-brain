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

### Step 1: Check Installation Status

```bash
agent-brain --version 2>/dev/null || echo "NOT_INSTALLED"
```

If not installed, run `/agent-brain-install` first.

### Step 2: Configure Provider

Check provider configuration (via config file or environment):

```bash
# Check for config file
ls ~/.agent-brain/config.yaml .claude/agent-brain/config.yaml 2>/dev/null

# Check environment variables
echo "Provider: ${EMBEDDING_PROVIDER:-openai}"
echo "OpenAI: ${OPENAI_API_KEY:+SET}"
echo "Anthropic: ${ANTHROPIC_API_KEY:+SET}"
```

If no provider is configured, run `/agent-brain-config` to choose:
- **Ollama** (FREE, local, no API keys)
- **OpenAI** (cloud, requires API key)
- **Other cloud providers**

Configuration can be stored in `~/.agent-brain/config.yaml` (recommended) or via environment variables.

### Step 3: Initialize Project

```bash
agent-brain init
```

Creates `.claude/agent-brain/` directory with configuration files.

### Step 4: PostgreSQL (Optional, Only When Backend Is Postgres)

PostgreSQL setup is only required if the storage backend is `postgres`.

Check backend selection (env override takes priority):

```bash
echo "Backend override: ${AGENT_BRAIN_STORAGE_BACKEND:-unset}"
rg -n "storage:\n  backend:" ~/.agent-brain/config.yaml .claude/agent-brain/config.yaml 2>/dev/null
```

If the backend is `postgres`, confirm Docker and Docker Compose are available:

```bash
docker --version
docker compose version
```

If Docker is available, offer to start the provided pgvector template:

```bash
docker compose -f agent-brain-plugin/templates/docker-compose.postgres.yml up -d
```

Verify PostgreSQL is ready:

```bash
docker compose -f agent-brain-plugin/templates/docker-compose.postgres.yml ps
docker compose -f agent-brain-plugin/templates/docker-compose.postgres.yml exec -T postgres pg_isready -U agent_brain
```

If Docker is not available, pause and explain the user must install Docker or point `storage.postgres` to an existing PostgreSQL instance.

### Step 5: Start Server

```bash
agent-brain start
```

Starts the server in background mode.

### Step 6: Verify Setup

```bash
agent-brain status
```

Confirm server is healthy and ready.

## Output

Display progress through each step with clear status indicators:

```
Agent Brain Setup
=================

[1/5] Checking installation...
      agent-brain-cli: 1.2.0 [OK]
      agent-brain-rag: 1.2.0 [OK]

[2/5] Checking provider configuration...
      Config file: ~/.agent-brain/config.yaml [FOUND]
      Embedding: openai/text-embedding-3-large [OK]
      Summarization: anthropic/claude-haiku-4-5-20251001 [OK]

[3/5] Initializing project...
      Created: .claude/agent-brain/config.json [OK]

[4/5] Starting server...
      Server started on port 49321 [OK]

[5/5] Verifying setup...
      Health: healthy [OK]
      Documents: 0 (ready to index)

Setup Complete!
===============

Agent Brain is ready to use.

Next steps:
  1. Index documents: /agent-brain-index <path>
  2. Search: /agent-brain-search "your query"

Quick start:
  agent-brain index ./docs
  agent-brain query "authentication"
```

## Error Handling

### Installation Failed

```
[1/5] Checking installation... FAILED

Agent Brain is not installed.

Running installation...
[Invoke /agent-brain-install]
```

### Provider Not Configured

```
[2/5] Checking provider... INCOMPLETE

No embedding provider configured.

Options:
1. Create config file: ~/.agent-brain/config.yaml (recommended)
2. Ollama (FREE, local) - No API keys needed
3. OpenAI (cloud) - Requires API key in config or OPENAI_API_KEY
4. Other cloud providers

Running configuration...
[Invoke /agent-brain-config]
```

### Init Failed

```
[3/5] Initializing project... FAILED

Error: Permission denied creating .claude/agent-brain/

Solutions:
1. Check directory permissions
2. Ensure you have write access to current directory
3. Try: mkdir -p .claude/agent-brain
```

### Server Start Failed

```
[4/5] Starting server... FAILED

Error: Port already in use

Solutions:
1. Check for running instance: agent-brain list
2. Stop existing server: agent-brain stop
3. Clean state: rm -f .claude/agent-brain/runtime.json
4. Retry: agent-brain start
```

### Verification Failed

```
[5/5] Verifying setup... FAILED

Server started but health check failed.

Diagnostics:
1. Check logs: Check server output
2. Verify API key: Test OpenAI connection
3. Restart: agent-brain stop && agent-brain start
```

## Resume Capability

If setup is interrupted, running `/agent-brain-setup` again will:
1. Skip already-completed steps
2. Resume from the failed step
3. Complete remaining steps

The setup is idempotent and safe to run multiple times.
