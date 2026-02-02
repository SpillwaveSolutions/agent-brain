---
name: agent-brain-init
description: Initialize Agent Brain for the current project
parameters: []
skills:
  - configuring-agent-brain
---

# Initialize Agent Brain Project

## Purpose

Initializes the current project for Agent Brain by creating the necessary configuration directory and files. This sets up per-project isolation, allowing each project to have its own Agent Brain instance with separate configuration and data.

## Usage

```
/agent-brain-init
```

## Execution

### Run Initialization

```bash
agent-brain init
```

This creates the `.claude/agent-brain/` directory structure in the current project.

### Verify Initialization

```bash
ls -la .claude/agent-brain/
```

## Output

```
Agent Brain Initialization
==========================

Initializing Agent Brain for current project...

Running: agent-brain init

Created directory structure:
  .claude/agent-brain/
    config.json      - Project configuration
    chroma_db/       - Vector store (created on first index)
    bm25_index/      - Keyword index (created on first index)

Project initialized successfully!

Configuration file: .claude/agent-brain/config.json
{
  "project_name": "my-project",
  "created_at": "2025-01-31T12:00:00Z",
  "mode": "project"
}

Next steps:
  1. Start server: agent-brain start --daemon
  2. Index documents: agent-brain index ./docs
  3. Search: agent-brain query "your query"
```

## What Gets Created

The initialization creates the following structure:

```
.claude/
  agent-brain/
    config.json       # Project configuration
    runtime.json      # Server state (created on start)
    chroma_db/        # ChromaDB vector store (created on index)
    bm25_index/       # BM25 keyword index (created on index)
```

### config.json

Contains project-specific settings:

```json
{
  "project_name": "my-project",
  "created_at": "2025-01-31T12:00:00Z",
  "mode": "project",
  "settings": {
    "embedding_model": "text-embedding-3-large",
    "chunk_size": 512,
    "chunk_overlap": 50
  }
}
```

### runtime.json

Created when server starts, contains:

```json
{
  "port": 49321,
  "pid": 12345,
  "started_at": "2025-01-31T12:00:00Z",
  "state_dir": ".claude/agent-brain"
}
```

## Error Handling

### Already Initialized

```
Project already initialized.

Existing configuration found at: .claude/agent-brain/config.json

Options:
  - Continue using existing configuration
  - Reset with: rm -rf .claude/agent-brain && agent-brain init
  - Check status: agent-brain status
```

### Permission Denied

```
Error: Cannot create directory .claude/agent-brain/

Permission denied.

Solutions:
1. Check directory permissions: ls -la .
2. Ensure write access to current directory
3. Create manually: mkdir -p .claude/agent-brain
4. Check if .claude exists and is writable
```

### Not in a Project Directory

```
Warning: No git repository or project markers found.

Agent Brain will initialize here, but consider:
1. Navigate to your project root first
2. Initialize git: git init
3. Then run: agent-brain init
```

### Parent Directory Issues

```
Error: Cannot create .claude directory

The parent directory may not exist or is not writable.

Check:
1. Current directory exists: pwd
2. You have write permissions: ls -la .
3. Disk is not full: df -h .
```

## Re-initialization

To completely reset a project's Agent Brain configuration:

```bash
# Stop server if running
agent-brain stop

# Remove existing configuration
rm -rf .claude/agent-brain

# Re-initialize
agent-brain init
```

**Warning**: This deletes all indexed documents. You will need to re-index after re-initialization.

## Multiple Projects

Each project should be initialized separately. Agent Brain uses the `.claude/agent-brain/` directory to isolate:

- Configuration settings
- Vector store data
- BM25 index data
- Server runtime state

This allows running multiple Agent Brain instances for different projects simultaneously, each on its own port.
