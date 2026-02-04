# Agent Brain Installation Guide

Complete installation options for Agent Brain with pluggable providers and GraphRAG support.

## Prerequisites

- Python 3.10 or higher
- pip, pipx, uv, or conda (package manager)
- Optional: Ollama for local embeddings/summarization

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

```bash
# Install pipx (if needed)
python -m pip install --user pipx
python -m pipx ensurepath

# Install Agent Brain
pipx install agent-brain-cli

# Verify
agent-brain --version

# Upgrade later
pipx upgrade agent-brain-cli
```

---

## Method 2: uv

**Best for:** Power users, those already using uv

```bash
# Install uv (macOS/Linux)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install Agent Brain
uv tool install agent-brain-cli

# Verify
agent-brain --version

# Upgrade later
uv tool upgrade agent-brain-cli
```

---

## Method 3: pip with Virtual Environment

**Best for:** Project-scoped installations, CI/CD

```bash
# Create and activate venv
python -m venv .venv
source .venv/bin/activate  # Linux/macOS

# Install Agent Brain
pip install agent-brain-rag agent-brain-cli

# Verify
agent-brain --version
```

**Note:** Must activate venv each time: `source .venv/bin/activate`

---

## Method 4: Conda

**Best for:** Data science users

```bash
# Create conda environment
conda create -n agent-brain python=3.12 -y
conda activate agent-brain

# Install Agent Brain (pip inside conda)
pip install agent-brain-rag agent-brain-cli

# Verify
agent-brain --version
```

**Note:** Must activate env each time: `conda activate agent-brain`

---

## Installation Extras

### Basic Installation

Installs core RAG functionality with hybrid search (BM25 + semantic):

```bash
pip install agent-brain-rag agent-brain-cli
```

### With GraphRAG Support

Includes knowledge graph capabilities with SimplePropertyGraphStore:

```bash
pip install "agent-brain-rag[graphrag]" agent-brain-cli
```

### With All Features

Includes GraphRAG with Kuzu database backend for production use:

```bash
pip install "agent-brain-rag[graphrag-all]" agent-brain-cli
```

## Installation Extras Reference

| Extra | Includes | Use Case |
|-------|----------|----------|
| (none) | Core RAG, ChromaDB, BM25, LlamaIndex | Basic document search |
| `graphrag` | + langextract, SimplePropertyGraphStore | Development GraphRAG |
| `graphrag-all` | + Kuzu database | Production GraphRAG |

---

## Development Installation

For contributors or local development:

```bash
# Clone repository
git clone https://github.com/SpillwaveSolutions/agent-brain.git
cd agent-brain

# Install in editable mode
pip install -e "./agent-brain-server[dev]"
pip install -e "./agent-brain-cli[dev]"

# Or use Poetry
cd agent-brain-server && poetry install
cd ../agent-brain-cli && poetry install
```

---

## Verifying Installation

```bash
# Check CLI version
agent-brain --version

# Check server package
python -c "import agent_brain_server; print(agent_brain_server.__version__)"

# Verify all dependencies
agent-brain verify
```

---

## Quick Reference

| Method | Install Command | Upgrade Command |
|--------|-----------------|-----------------|
| pipx | `pipx install agent-brain-cli` | `pipx upgrade agent-brain-cli` |
| uv | `uv tool install agent-brain-cli` | `uv tool upgrade agent-brain-cli` |
| pip | `pip install agent-brain-rag agent-brain-cli` | `pip install --upgrade ...` |
| conda | `pip install ...` (in conda env) | `pip install --upgrade ...` |

---

## System Requirements

### Minimum Requirements

| Component | Requirement |
|-----------|-------------|
| Python | 3.10+ |
| RAM | 2GB (4GB recommended) |
| Disk | 500MB + index storage |

### With GraphRAG

| Component | Requirement |
|-----------|-------------|
| Python | 3.10+ |
| RAM | 4GB (8GB recommended) |
| Disk | 1GB + index storage |

---

## Troubleshooting Installation

### Command Not Found

**pipx:**
```bash
python -m pipx ensurepath
# Restart terminal
```

**uv:**
```bash
uv tool list  # Verify installed
# Restart terminal
```

**pip (venv):**
```bash
source .venv/bin/activate  # Must activate first
```

### pip installation fails

```bash
# Upgrade pip first
pip install --upgrade pip

# Try with --no-cache-dir
pip install --no-cache-dir agent-brain-rag agent-brain-cli
```

### Dependency conflicts

Use a virtual environment (Method 3) or pipx (Method 1) to isolate dependencies.

### ChromaDB build issues

On some systems, ChromaDB may require additional build tools:

```bash
# Ubuntu/Debian
sudo apt-get install build-essential

# macOS
xcode-select --install

# Then reinstall
pip install --no-cache-dir agent-brain-rag
```

### Kuzu installation issues (graphrag-all)

Kuzu requires a C++ compiler:

```bash
# Ubuntu/Debian
sudo apt-get install g++

# macOS (already included with Xcode)
xcode-select --install
```

---

## Uninstallation

| Method | Command |
|--------|---------|
| pipx | `pipx uninstall agent-brain-cli` |
| uv | `uv tool uninstall agent-brain-cli` |
| pip | `pip uninstall agent-brain-rag agent-brain-cli -y` |
| conda | `pip uninstall agent-brain-rag agent-brain-cli -y` (in conda env) |

---

## Next Steps

After installation:

1. [Configure providers](provider-configuration.md)
2. [Initialize your project](../SKILL.md#server-management)
3. [Index documents](../SKILL.md#server-management)
4. [Start searching](../SKILL.md#search-modes)
