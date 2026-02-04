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
| --version | For install | Version to install (e.g., 3.0.0, 2.0.0) |

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
# Set desired version
VERSION="X.Y.Z"  # e.g., 3.0.0, 2.0.0

# Install specific version
pip install agent-brain-rag==$VERSION agent-brain-cli==$VERSION
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

CLI Version: $VERSION
Server Package: $VERSION

Components:
- agent-brain-rag: $VERSION
- agent-brain-cli: $VERSION

Features:
- Hybrid Search: Enabled
- GraphRAG: Enabled (requires ENABLE_GRAPH_INDEX=true)
- Pluggable Providers: Yes

Python: 3.11.x
Platform: darwin (arm64)
```

Note: Run version resolver to get current version:
```bash
VERSION=$(curl -sf https://pypi.org/pypi/agent-brain-rag/json | python3 -c "import sys,json; print(json.load(sys.stdin)['info']['version'])")
```

### Version List Output

```
Available Agent Brain Versions
==============================

Latest: $LATEST (resolved from PyPI)

Recent Versions:
- 3.0.0  (2025-02) - Job queue, async indexing
- 2.0.0  (2024-12) - Pluggable providers, GraphRAG
- 1.4.0  (2024-11) - Graph search, multi-mode fusion
- 1.3.0  (2024-10) - AST-aware code ingestion

To install a specific version:
VERSION=$(curl -sf https://pypi.org/pypi/agent-brain-rag/json | python3 -c "import sys,json; print(json.load(sys.stdin)['info']['version'])")
pip install agent-brain-rag==$VERSION agent-brain-cli==$VERSION
```

### Install Output

```
Installing Agent Brain version $VERSION...

pip install agent-brain-rag==$VERSION agent-brain-cli==$VERSION

Successfully installed:
- agent-brain-rag $VERSION
- agent-brain-cli $VERSION

Note: You may need to re-index documents after version changes.
Run: agent-brain reset --yes && agent-brain index /path/to/docs
```

### Upgrade Output

```
Upgrading Agent Brain to latest version...

pip install --upgrade agent-brain-rag agent-brain-cli

Upgraded from X.Y.Z to $LATEST

Check release notes for changes:
https://github.com/SpillwaveSolutions/agent-brain/releases

Migration steps:
1. Review breaking changes in release notes
2. Update provider environment variables if needed
3. Re-index documents for new features
```

## Version Compatibility

### Package Alignment

Keep both packages on the same version:

| RAG Version | CLI Version | Compatible |
|-------------|-------------|------------|
| X.Y.Z | X.Y.Z | Yes |
| X.Y.Z | A.B.C | No - versions must match |

### Index Compatibility

| From | To | Index Action |
|------|-----|--------------|
| N.x | N+1.0 | Re-index usually required |
| N.x.y | N.x.z | Usually compatible |

### Migration Between Major Versions

When upgrading between major versions:

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
agent-brain start
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
- agent-brain-rag: X.Y.Z
- agent-brain-cli: A.B.C
```

**Resolution:**
```bash
# Get latest version
VERSION=$(curl -sf https://pypi.org/pypi/agent-brain-rag/json | python3 -c "import sys,json; print(json.load(sys.stdin)['info']['version'])")
pip install agent-brain-rag==$VERSION agent-brain-cli==$VERSION
```

## Related Commands

- `/agent-brain-install` - Install Agent Brain packages
- `/agent-brain-verify` - Verify installation
- `/agent-brain-status` - Show server status
