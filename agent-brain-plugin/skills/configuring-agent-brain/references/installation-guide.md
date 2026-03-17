# Agent Brain Installation Guide

## Overview

This guide covers the complete installation process for Agent Brain, including multiple installation methods, prerequisites, and verification steps.

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
| uv | `uv python install 3.12` |

---

## Installation Methods

Choose the best method for your workflow:

| Method | Best For | Scope | Requires Activation |
|--------|----------|-------|---------------------|
| pipx (recommended) | Most users | Global (isolated) | No |
| uv | Power users | Global (isolated) | No |
| pip (venv) | Project-scoped | Project | Yes |
| conda | Data science | Environment | Yes |

---

## Method 1: pipx (Recommended)

**Best for:** Most users who want a simple, global CLI installation

pipx installs the CLI globally while keeping dependencies isolated in their own virtual environment.

### Install pipx

```bash
# Check if pipx is installed
pipx --version

# Install pipx (if needed)
python -m pip install --user pipx
python -m pipx ensurepath
```

Restart your terminal after installing pipx.

### Install Agent Brain

```bash
pipx install agent-brain-cli
```

### Verify

```bash
agent-brain --version
```

### Upgrade

```bash
pipx upgrade agent-brain-cli
```

### Uninstall

```bash
pipx uninstall agent-brain-cli
```

---

## Method 2: uv

**Best for:** Power users, those already using uv, or wanting fast installs

uv is a modern, Rust-based Python package installer that's very fast.

### Install uv

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
irm https://astral.sh/uv/install.ps1 | iex
```

### Install Agent Brain

```bash
uv tool install agent-brain-cli
```

### Verify

```bash
agent-brain --version
```

### Upgrade

```bash
uv tool upgrade agent-brain-cli
```

### Uninstall

```bash
uv tool uninstall agent-brain-cli
```

---

## Method 3: pip with Virtual Environment

**Best for:** Project-scoped installations, CI/CD environments

This method keeps Agent Brain local to a specific project directory.

### Create Virtual Environment

```bash
# Create venv
python -m venv .venv

# Activate (Linux/macOS)
source .venv/bin/activate

# Activate (Windows)
.venv\Scripts\activate
```

### Install Agent Brain

```bash
pip install agent-brain-rag agent-brain-cli
```

### Verify

```bash
agent-brain --version
```

**Note:** You must activate the virtual environment before using Agent Brain:
```bash
source .venv/bin/activate  # Run this each time
```

### Upgrade

```bash
source .venv/bin/activate
pip install --upgrade agent-brain-rag agent-brain-cli
```

### Uninstall

```bash
pip uninstall agent-brain-rag agent-brain-cli
```

---

## Method 4: Conda

**Best for:** Data science users already in the conda ecosystem

Agent Brain is distributed on PyPI (not conda-forge), so you install it with pip inside a conda environment.

### Create Conda Environment

```bash
conda create -n agent-brain python=3.12 -y
conda activate agent-brain
```

### Install Agent Brain

```bash
pip install agent-brain-rag agent-brain-cli
```

### Verify

```bash
agent-brain --version
```

**Note:** Activate the conda environment before using Agent Brain:
```bash
conda activate agent-brain  # Run this each time
```

### Upgrade

```bash
conda activate agent-brain
pip install --upgrade agent-brain-rag agent-brain-cli
```

---

## Post-Installation Verification

After installation, verify everything is working:

```bash
# Check CLI is available
agent-brain --help

# Check version
agent-brain --version
```

Expected help output:
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

---

## Quick Reference

| Method | Install Command | Upgrade Command |
|--------|-----------------|-----------------|
| pipx | `pipx install agent-brain-cli` | `pipx upgrade agent-brain-cli` |
| uv | `uv tool install agent-brain-cli` | `uv tool upgrade agent-brain-cli` |
| pip | `pip install agent-brain-rag agent-brain-cli` | `pip install --upgrade agent-brain-rag agent-brain-cli` |
| conda | `pip install ...` (in conda env) | `pip install --upgrade ...` |

---

## Troubleshooting Installation

### Issue: Command Not Found

**Symptom:** `agent-brain: command not found`

**Solutions by method:**

**pipx:**
```bash
python -m pipx ensurepath
# Restart terminal
```

**uv:**
```bash
uv tool list  # Verify it's installed
# Restart terminal
```

**pip (venv):**
```bash
source .venv/bin/activate  # Must activate first
which agent-brain
```

**conda:**
```bash
conda activate agent-brain  # Must activate first
which agent-brain
```

### Issue: Permission Denied

**Symptom:** `Permission denied` during installation

**Solutions:**

1. **Use pipx (recommended):** Avoids permission issues entirely
2. **Use user installation:** `pip install --user agent-brain-cli`
3. **Use virtual environment:** See Method 3 above
4. **Never use sudo with pip**

### Issue: Module Not Found

**Symptom:** `ModuleNotFoundError` when running

**Solutions:**

```bash
# Reinstall packages
pip install --force-reinstall agent-brain-rag agent-brain-cli

# Check Python environment
which python
pip list | grep agent-brain
```

### Issue: pip Not Found

**Symptom:** `pip: command not found`

**Solutions:**

```bash
# Use python -m pip
python -m pip install agent-brain-rag agent-brain-cli

# Or install pip
python -m ensurepip --upgrade
```

### Issue: Python Version Too Low

**Symptom:** Installation fails with Python version error

**Solutions:**

```bash
# Install newer Python
brew install python@3.11  # macOS
sudo apt install python3.11  # Ubuntu
uv python install 3.12  # Using uv

# Or use conda
conda create -n agent-brain python=3.12
```

### Issue: SSL Certificate Error

**Symptom:** SSL errors during installation

**Solutions:**

```bash
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org agent-brain-rag agent-brain-cli
```

---

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

---

## Multi-Runtime Installation (v9.0+)

After installing the CLI, deploy the Agent Brain plugin to your AI coding assistant:

```bash
# Install for Claude Code (default)
agent-brain install-agent --agent claude

# Install for OpenCode
agent-brain install-agent --agent opencode

# Install for Gemini
agent-brain install-agent --agent gemini

# Install for Codex (generates skill directories + AGENTS.md)
agent-brain install-agent --agent codex

# Install for any skill-based runtime (requires --dir)
agent-brain install-agent --agent skill-runtime --dir /path/to/skills

# Dry run to preview files
agent-brain install-agent --agent claude --dry-run

# Global (user-level) installation
agent-brain install-agent --agent claude --scope global
```

### Supported Runtimes

| Runtime | Project Install Dir | Format |
|---------|-------------------|--------|
| `claude` | `.claude/plugins/agent-brain` | Claude plugin |
| `opencode` | `.opencode/plugins/agent-brain` | OpenCode plugin |
| `gemini` | `.gemini/plugins/agent-brain` | Gemini plugin |
| `codex` | `.codex/skills/agent-brain` | Skill dirs + AGENTS.md |
| `skill-runtime` | (requires `--dir`) | Generic skill dirs |

### Uninstalling

```bash
agent-brain uninstall --agent claude
agent-brain uninstall --agent claude --scope global
```

---

## Key Features by Version

| Version | Key Features |
|---------|-------------|
| v7.0 | Folder management (`folders add/list/remove`), file type presets (`types list`), content injection (`inject`), chunk eviction |
| v8.0 | File watcher (auto-reindex on file changes), embedding cache, setup wizard, query cache, reranking |
| v9.0+ | Multi-runtime install (5 runtimes), pluggable providers (7 providers), generic skill-runtime converter |

---

## Next Steps

After installation:
1. [Configure providers](configuration-guide.md) (API keys or Ollama)
2. Initialize project: `/agent-brain:agent-brain-init`
3. Start server: `/agent-brain:agent-brain-start`
4. Index documents: `/agent-brain:agent-brain-index /path/to/docs`
