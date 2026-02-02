---
name: agent-brain-version
description: Show current version and manage Agent Brain versions
parameters:
  - name: action
    description: Action to perform (show, list, install, upgrade)
    required: false
    default: show
  - name: version
    description: Specific version for install action
    required: false
skills:
  - using-agent-brain
---

# Agent Brain Version Management

## Purpose

Shows current Agent Brain version and manages version installations. Use this command to check versions, list available releases, upgrade to latest, or install specific versions.

## Usage

```
/agent-brain-version [action] [--version <ver>]
```

### Actions

| Action | Description |
|--------|-------------|
| `show` | Show current installed version (default) |
| `list` | List all available versions |
| `install` | Install a specific version |
| `upgrade` | Upgrade to latest version |

### Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| action | No | Action to perform (default: show) |
| --version | For install | Version to install (e.g., 2.0.0, 1.4.0) |

## Execution

### Show Current Version (Default)

```bash
# CLI version
agent-brain --version

# Python package versions
pip show agent-brain-rag agent-brain-cli | grep -E "^(Name|Version)"
```

### List Available Versions

```bash
# List all available versions on PyPI
pip index versions agent-brain-rag 2>/dev/null | head -20

# Alternative
pip install agent-brain-rag== 2>&1 | grep -oP '\d+\.\d+\.\d+' | head -10
```

### Install Specific Version

```bash
# Install specific version
pip install agent-brain-rag==<version> agent-brain-cli==<version>

# Example: Install version 1.4.0
pip install agent-brain-rag==1.4.0 agent-brain-cli==1.4.0
```

### Upgrade to Latest

```bash
pip install --upgrade agent-brain-rag agent-brain-cli
```

## Output

### Version Show Output

```
Agent Brain Version Information
===============================

CLI Version: 2.0.0
Server Package: 2.0.0

Components:
- agent-brain-rag: 2.0.0
- agent-brain-cli: 2.0.0

Features:
- Hybrid Search: Enabled
- GraphRAG: Enabled (requires ENABLE_GRAPH_INDEX=true)
- Pluggable Providers: Yes

Python: 3.11.5
Platform: darwin (arm64)
```

### Version List Output

```
Available Agent Brain Versions
==============================

Latest: 2.0.0

Recent Versions:
- 2.0.0  (2024-12) - Pluggable providers, GraphRAG
- 1.4.0  (2024-11) - Graph search, multi-mode fusion
- 1.3.0  (2024-10) - AST-aware code ingestion
- 1.2.0  (2024-09) - Multi-instance architecture
- 1.1.0  (2024-08) - Hybrid search, BM25
- 1.0.0  (2024-07) - Initial release

To install a specific version:
pip install agent-brain-rag==<version> agent-brain-cli==<version>
```

### Install Output

```
Installing Agent Brain version 1.4.0...

pip install agent-brain-rag==1.4.0 agent-brain-cli==1.4.0

Successfully installed:
- agent-brain-rag 1.4.0
- agent-brain-cli 1.4.0

Note: You may need to re-index documents after version changes.
Run: agent-brain reset --yes && agent-brain index /path/to/docs
```

### Upgrade Output

```
Upgrading Agent Brain to latest version...

pip install --upgrade agent-brain-rag agent-brain-cli

Upgraded from 1.4.0 to 2.0.0

Changes in 2.0.0:
- Pluggable embedding providers (OpenAI, Cohere, Ollama)
- Pluggable summarization providers
- Fully local mode with Ollama
- Enhanced GraphRAG support

Migration steps:
1. Set provider environment variables
2. Re-index documents for new features
```

## Version Compatibility

### Package Alignment

Keep both packages on the same version:

| RAG Version | CLI Version | Compatible |
|-------------|-------------|------------|
| 2.0.0 | 2.0.0 | Yes |
| 2.0.0 | 1.4.0 | No - update CLI |
| 1.4.0 | 1.4.0 | Yes |

### Index Compatibility

| From | To | Index Action |
|------|-----|--------------|
| 1.x | 2.0 | Re-index required |
| 2.0.x | 2.0.y | Usually compatible |
| 2.0 | 1.x | Re-index required |

### Migration Between Major Versions

When upgrading from 1.x to 2.0:

```bash
# 1. Stop server
agent-brain stop

# 2. Upgrade
pip install --upgrade agent-brain-rag agent-brain-cli

# 3. Configure new provider settings
export EMBEDDING_PROVIDER=openai
export EMBEDDING_MODEL=text-embedding-3-large
export SUMMARIZATION_PROVIDER=anthropic
export SUMMARIZATION_MODEL=claude-haiku-4-5-20251001

# 4. Re-index
agent-brain reset --yes
agent-brain start --daemon
agent-brain index /path/to/docs
```

## Error Handling

### Version Not Found

```
Error: Version '9.9.9' not found
```

**Resolution:** Use `/agent-brain-version list` to see available versions

### Network Error

```
Error: Could not connect to PyPI
```

**Resolution:** Check internet connection and try again

### Permission Error

```
Error: Permission denied installing packages
```

**Resolution:**
```bash
# Use user installation
pip install --user agent-brain-rag agent-brain-cli

# Or use virtual environment
python -m venv venv
source venv/bin/activate
pip install agent-brain-rag agent-brain-cli
```

### Version Mismatch

```
Warning: Package version mismatch
- agent-brain-rag: 2.0.0
- agent-brain-cli: 1.4.0
```

**Resolution:**
```bash
pip install agent-brain-rag==2.0.0 agent-brain-cli==2.0.0
```

## Related Commands

- `/agent-brain-install` - Install Agent Brain packages
- `/agent-brain-verify` - Verify installation
- `/agent-brain-status` - Show server status
