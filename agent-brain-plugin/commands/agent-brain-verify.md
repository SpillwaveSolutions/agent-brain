---
name: agent-brain-verify
description: Verify Agent Brain installation and configuration
parameters: []
skills:
  - configuring-agent-brain
---

# Verify Agent Brain Setup

## Purpose

Performs a comprehensive verification of the Agent Brain installation, checking that all components are properly installed, configured, and functioning. This command provides a quick health check and identifies any issues that need attention.

## Usage

```
/agent-brain-verify
```

## Execution

Run the following verification steps in sequence:

### Step 1: Check Package Installation

```bash
agent-brain --version
python -c "import agent_brain_cli; print(agent_brain_cli.__version__)" 2>/dev/null
python -c "import agent_brain_server; print(agent_brain_server.__version__)" 2>/dev/null
```

### Step 2: Check Python Version

```bash
python --version
```

### Step 3: Check API Keys

```bash
echo "OPENAI_API_KEY: ${OPENAI_API_KEY:+SET}"
echo "ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:+SET}"
```

### Step 4: Check Project Initialization

```bash
ls -la .claude/agent-brain/config.json 2>/dev/null
```

### Step 5: Check Server Status (if running)

```bash
agent-brain status
```

### Step 6: Run Health Check (if server running)

```bash
curl -s http://127.0.0.1:$(cat .claude/agent-brain/runtime.json 2>/dev/null | python -c "import sys,json; print(json.load(sys.stdin).get('port', 8000))")/health 2>/dev/null || echo "Server not running"
```

## Output

### All Checks Passing

```
Agent Brain Verification
========================

Installation
------------
[OK] agent-brain-cli: 1.2.0
[OK] agent-brain-rag: 1.2.0
[OK] Python: 3.11.4 (>= 3.10 required)

Configuration
-------------
[OK] OPENAI_API_KEY: Set
[OK] ANTHROPIC_API_KEY: Set (optional)

Project Setup
-------------
[OK] Project initialized: .claude/agent-brain/
[OK] Config file: .claude/agent-brain/config.json

Server Status
-------------
[OK] Server running on port 49321
[OK] Health: healthy
[OK] Documents indexed: 150
[OK] Chunks: 750

Verification Complete!
======================

All checks passed. Agent Brain is ready to use.

Quick commands:
  Search: agent-brain query "your query"
  Index:  agent-brain index /path/to/docs
  Status: agent-brain status
```

### Some Checks Failing

```
Agent Brain Verification
========================

Installation
------------
[OK] agent-brain-cli: 1.2.0
[OK] agent-brain-rag: 1.2.0
[OK] Python: 3.11.4

Configuration
-------------
[OK] OPENAI_API_KEY: Set
[--] ANTHROPIC_API_KEY: Not set (optional)

Project Setup
-------------
[!!] Project not initialized

Server Status
-------------
[!!] Server not running

Verification Summary
====================

Issues Found: 2

1. Project not initialized
   Fix: agent-brain init

2. Server not running
   Fix: agent-brain start --daemon

Run /agent-brain-setup to fix all issues automatically.
```

## Checklist Format

For quick reference, the verification can also output as a checklist:

```
Agent Brain Verification Checklist
===================================

Packages:
  [x] agent-brain-cli installed
  [x] agent-brain-rag installed
  [x] Python >= 3.10

API Keys:
  [x] OPENAI_API_KEY set
  [ ] ANTHROPIC_API_KEY set (optional)

Project:
  [x] .claude/agent-brain/ exists
  [x] config.json present

Server:
  [x] Server running
  [x] Health check passed
  [x] Documents indexed (150)

Status: Ready (5/6 checks passed)
```

## Error Handling

### Packages Not Installed

```
[!!] agent-brain-cli: NOT FOUND

The Agent Brain CLI is not installed.

Fix:
  pip install agent-brain-cli agent-brain-rag

Or run: /agent-brain-install
```

### Python Version Too Low

```
[!!] Python: 3.8.10 (requires >= 3.10)

Python 3.10 or higher is required.

Fix:
  1. Install Python 3.10+: https://python.org/downloads/
  2. Use pyenv: pyenv install 3.11
  3. Use conda: conda create -n agent-brain python=3.11
```

### API Key Not Set

```
[!!] OPENAI_API_KEY: NOT SET

The OpenAI API key is required for semantic search.

Fix:
  export OPENAI_API_KEY="sk-proj-..."

Or run: /agent-brain-config
```

### Project Not Initialized

```
[!!] Project not initialized

No .claude/agent-brain/ directory found.

Fix:
  agent-brain init

Or run: /agent-brain-init
```

### Server Not Running

```
[!!] Server not running

The Agent Brain server is not running.

Fix:
  agent-brain start --daemon

After starting, verify with:
  agent-brain status
```

### Server Unhealthy

```
[!!] Server unhealthy

Server is running but health check failed.

Diagnostics:
  1. Check server logs
  2. Verify API key is valid
  3. Restart: agent-brain stop && agent-brain start --daemon
```

### No Documents Indexed

```
[--] Documents indexed: 0

No documents have been indexed yet.

To index documents:
  agent-brain index /path/to/docs

This is not an error, but search will return no results
until documents are indexed.
```

## Quick Fix Mode

If verification fails, suggest the automated fix:

```
Verification found 3 issues.

Quick fix: Run /agent-brain-setup to resolve all issues automatically.

Or fix manually:
  1. pip install agent-brain-cli agent-brain-rag
  2. export OPENAI_API_KEY="your-key"
  3. agent-brain init
  4. agent-brain start --daemon
```
