# Agent Brain Installation Guide

## Overview

This guide covers the complete installation process for Agent Brain, including prerequisites, package installation, and verification steps.

## Prerequisites

### Python 3.10+

Agent Brain requires Python 3.10 or higher.

**Check Python Version:**
```bash
python --version
# or
python3 --version
```

**Install Python (if needed):**

| Platform | Command |
|----------|---------|
| macOS | `brew install python@3.11` |
| Ubuntu/Debian | `sudo apt install python3.11` |
| Windows | Download from python.org |

### pip Package Manager

pip is required to install Agent Brain packages.

**Check pip:**
```bash
pip --version
# or
pip3 --version
```

**Install pip (if needed):**
```bash
python -m ensurepip --upgrade
```

### Virtual Environment (Recommended)

Using a virtual environment keeps your system Python clean.

**Create and Activate:**
```bash
# Create virtual environment
python -m venv agent-brain-env

# Activate (Linux/macOS)
source agent-brain-env/bin/activate

# Activate (Windows)
agent-brain-env\Scripts\activate
```

## Installation Steps

### Step 1: Install Packages

```bash
pip install agent-brain-rag agent-brain-cli
```

This installs:
- `agent-brain-rag`: The RAG server with FastAPI, ChromaDB, and LlamaIndex
- `agent-brain-cli`: The command-line interface for managing the server

### Step 2: Verify Installation

```bash
# Check CLI is available
agent-brain --help

# Check version
agent-brain --version
```

Expected output:
```
Usage: agent-brain [OPTIONS] COMMAND [ARGS]...

  Agent Brain CLI - Document search and indexing management

Options:
  --version  Show version
  --help     Show this message and exit.

Commands:
  index   Index documents
  init    Initialize project
  list    List running instances
  query   Search documents
  reset   Clear index
  start   Start server
  status  Check server status
  stop    Stop server
```

### Step 3: Configure API Key

```bash
export OPENAI_API_KEY="sk-proj-..."
```

See [Configuration Guide](configuration-guide.md) for detailed API key setup.

## Installation Options

### Global Installation

```bash
pip install agent-brain-rag agent-brain-cli
```

### User Installation (No sudo)

```bash
pip install --user agent-brain-rag agent-brain-cli
```

### Virtual Environment Installation

```bash
python -m venv venv
source venv/bin/activate
pip install agent-brain-rag agent-brain-cli
```

### Specific Version

```bash
pip install agent-brain-rag==1.2.0 agent-brain-cli==1.2.0
```

## Upgrade

### Upgrade to Latest

```bash
pip install --upgrade agent-brain-rag agent-brain-cli
```

### Check for Updates

```bash
pip list --outdated | grep agent-brain
```

## Uninstall

```bash
pip uninstall agent-brain-rag agent-brain-cli
```

## Troubleshooting Installation

### Issue: Command Not Found

**Symptom:** `agent-brain: command not found`

**Solutions:**

1. **Check pip installed to correct Python:**
```bash
which pip
which python
# Should point to same Python installation
```

2. **Add to PATH (user installation):**
```bash
# Add to ~/.bashrc or ~/.zshrc
export PATH="$HOME/.local/bin:$PATH"
source ~/.bashrc
```

3. **Reinstall:**
```bash
pip install --force-reinstall agent-brain-cli
```

### Issue: Permission Denied

**Symptom:** `Permission denied` during installation

**Solutions:**

1. **Use user installation:**
```bash
pip install --user agent-brain-rag agent-brain-cli
```

2. **Use virtual environment:**
```bash
python -m venv venv
source venv/bin/activate
pip install agent-brain-rag agent-brain-cli
```

### Issue: Module Not Found

**Symptom:** `ModuleNotFoundError` when running

**Solutions:**

1. **Reinstall packages:**
```bash
pip install --force-reinstall agent-brain-rag agent-brain-cli
```

2. **Check Python environment:**
```bash
which python
pip list | grep agent-brain
```

### Issue: pip Not Found

**Symptom:** `pip: command not found`

**Solutions:**

1. **Use python -m pip:**
```bash
python -m pip install agent-brain-rag agent-brain-cli
```

2. **Install pip:**
```bash
python -m ensurepip --upgrade
```

### Issue: SSL Certificate Error

**Symptom:** SSL errors during installation

**Solutions:**

```bash
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org agent-brain-rag agent-brain-cli
```

## Dependencies

Agent Brain installs these major dependencies:

| Package | Purpose |
|---------|---------|
| FastAPI | REST API server |
| ChromaDB | Vector database |
| LlamaIndex | Document processing |
| OpenAI | Embeddings API |
| Click | CLI framework |
| Rich | CLI formatting |

## System Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| RAM | 512MB | 2GB |
| Disk | 500MB | 2GB |
| Python | 3.10 | 3.11+ |

## Next Steps

After installation:
1. [Configure API keys](configuration-guide.md)
2. Initialize project: `agent-brain init`
3. Start server: `agent-brain start --daemon`
4. Index documents: `agent-brain index /path/to/docs`
