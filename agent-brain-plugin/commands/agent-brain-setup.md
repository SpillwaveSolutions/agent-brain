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

### Step 2: Configure API Keys

Check for required environment variables:

```bash
echo "OpenAI: ${OPENAI_API_KEY:+SET}"
echo "Anthropic: ${ANTHROPIC_API_KEY:+SET}"
```

If OPENAI_API_KEY is not set, run `/agent-brain-config`.

### Step 3: Initialize Project

```bash
agent-brain init
```

Creates `.claude/agent-brain/` directory with configuration files.

### Step 4: Start Server

```bash
agent-brain start --daemon
```

Starts the server in background mode.

### Step 5: Verify Setup

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

[2/5] Checking API keys...
      OPENAI_API_KEY: SET [OK]
      ANTHROPIC_API_KEY: SET [OK]

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

### API Key Missing

```
[2/5] Checking API keys... INCOMPLETE

OPENAI_API_KEY is not set. This is required for search.

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
4. Retry: agent-brain start --daemon
```

### Verification Failed

```
[5/5] Verifying setup... FAILED

Server started but health check failed.

Diagnostics:
1. Check logs: Check server output
2. Verify API key: Test OpenAI connection
3. Restart: agent-brain stop && agent-brain start --daemon
```

## Resume Capability

If setup is interrupted, running `/agent-brain-setup` again will:
1. Skip already-completed steps
2. Resume from the failed step
3. Complete remaining steps

The setup is idempotent and safe to run multiple times.
