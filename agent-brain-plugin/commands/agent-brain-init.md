---
name: agent-brain-init
description: Initialize Agent Brain for the current project
parameters:
  - name: path
    description: "Project path (default: auto-detect project root)"
    required: false
  - name: host
    description: "Server bind host (default: 127.0.0.1)"
    required: false
  - name: port
    description: "Preferred server port (default: auto-select from range)"
    required: false
  - name: force
    description: Overwrite existing configuration
    required: false
    default: false
  - name: state-dir
    description: Custom state directory for index data
    required: false
  - name: json
    description: Output as JSON
    required: false
    default: false
context: fork
agent: setup-assistant
skills:
  - configuring-agent-brain
last_validated: 2026-03-16
---

# Initialize Agent Brain Project

## Purpose

Initializes the current project for Agent Brain by creating the necessary configuration directory and files. This sets up per-project isolation, allowing each project to have its own Agent Brain instance with separate configuration and data.

## Usage

```
/agent-brain:agent-brain-init [--path <path>] [--host <host>] [--port <port>] [--force] [--state-dir <dir>] [--json]
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| --path / -p | No | Auto-detect | Project path (auto-detects git root or project markers) |
| --host | No | 127.0.0.1 | Server bind host |
| --port | No | Auto-select | Preferred server port (disables auto-port if set) |
| --force / -f | No | false | Overwrite existing configuration |
| --state-dir / -s | No | .agent-brain | Custom state directory for index data |
| --json | No | false | Output as JSON |

### Examples

```
/agent-brain:agent-brain-init
/agent-brain:agent-brain-init --path /my/project
/agent-brain:agent-brain-init --port 8080
/agent-brain:agent-brain-init --state-dir /custom/path
/agent-brain:agent-brain-init --force
```

## Execution

### Run Initialization

```bash
agent-brain init
agent-brain init --path /my/project
agent-brain init --port 8080
agent-brain init --state-dir /custom/path
agent-brain init --force
```

This creates the `.agent-brain/` directory structure in the project root.

### Verify Initialization

```bash
ls -la .agent-brain/
```

## Output

```
Agent Brain Initialization
==========================

Initializing Agent Brain for current project...

Running: agent-brain init

Created directory structure:
  .agent-brain/
    config.json      - Project configuration
    chroma_db/       - Vector store (created on first index)
    bm25_index/      - Keyword index (created on first index)

Project initialized successfully!

Configuration file: .agent-brain/config.json
{
  "project_name": "my-project",
  "created_at": "2025-01-31T12:00:00Z",
  "mode": "project"
}

Next steps:
  1. Start server: /agent-brain:agent-brain-start
  2. Index documents: /agent-brain:agent-brain-index ./docs
  3. Search: /agent-brain:agent-brain-search "your query"
```

## What Gets Created

The initialization creates the following structure:

```
.agent-brain/
  config.json          # Project configuration (bind_host, port, chunk settings, exclude patterns)
  data/
    chroma_db/         # ChromaDB vector store (created on index)
    bm25_index/        # BM25 keyword index (created on index)
    llamaindex/        # LlamaIndex persistence (created on index)
  logs/                # Server logs
```

### config.json

Contains project-specific settings:

```json
{
  "bind_host": "127.0.0.1",
  "port_range_start": 8000,
  "port_range_end": 8100,
  "auto_port": true,
  "chunk_size": 512,
  "chunk_overlap": 50,
  "exclude_patterns": [
    "**/node_modules/**",
    "**/__pycache__/**",
    "**/.venv/**",
    "**/venv/**",
    "**/.git/**",
    "**/dist/**",
    "**/build/**",
    "**/target/**"
  ],
  "project_root": "/path/to/project"
}
```

### config.yaml (Optional)

Create a `config.yaml` in the project's `.agent-brain/` directory for project-specific provider settings:

```yaml
# .agent-brain/config.yaml
project:
  state_dir: null  # Use default

embedding:
  provider: "openai"
  api_key: "sk-proj-..."  # Or use api_key_env: "OPENAI_API_KEY"

summarization:
  provider: "anthropic"
  api_key: "sk-ant-..."
```

**Note**: Agent Brain searches for config.yaml in multiple locations. Project-level config takes precedence over user-level (`~/.agent-brain/config.yaml`).

### runtime.json

Created when server starts, contains:

```json
{
  "port": 49321,
  "pid": 12345,
  "started_at": "2025-01-31T12:00:00Z",
  "state_dir": ".agent-brain"
}
```

## Error Handling

### Already Initialized

```
Project already initialized.

Existing configuration found at: .agent-brain/config.json

Options:
  - Continue using existing configuration
  - Reset with: rm -rf .agent-brain && agent-brain init
  - Check status: agent-brain status
```

### Permission Denied

```
Error: Cannot create directory .agent-brain/

Permission denied.

Solutions:
1. Check directory permissions: ls -la .
2. Ensure write access to current directory
3. Create manually: mkdir -p .agent-brain
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
rm -rf .agent-brain

# Re-initialize
agent-brain init
```

**Warning**: This deletes all indexed documents. You will need to re-index after re-initialization.

## Multiple Projects

Each project should be initialized separately. Agent Brain uses the `.agent-brain/` directory to isolate:

- Configuration settings
- Vector store data
- BM25 index data
- Server runtime state

This allows running multiple Agent Brain instances for different projects simultaneously, each on its own port.
