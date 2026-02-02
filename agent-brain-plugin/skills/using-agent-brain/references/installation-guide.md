# Agent Brain Installation Guide

Complete installation options for Agent Brain v2.0.0 with pluggable providers and GraphRAG support.

## Prerequisites

- Python 3.10 or higher
- pip (Python package manager)
- Optional: Ollama for local embeddings/summarization

## Installation Options

### Basic Installation

Installs core RAG functionality with hybrid search (BM25 + semantic):

```bash
pip install agent-brain-rag==2.0.0 agent-brain-cli==2.0.0
```

### With GraphRAG Support

Includes knowledge graph capabilities with SimplePropertyGraphStore:

```bash
pip install "agent-brain-rag[graphrag]==2.0.0" agent-brain-cli==2.0.0
```

### With All Features

Includes GraphRAG with Kuzu database backend for production use:

```bash
pip install "agent-brain-rag[graphrag-all]==2.0.0" agent-brain-cli==2.0.0
```

## Installation Extras Reference

| Extra | Includes | Use Case |
|-------|----------|----------|
| (none) | Core RAG, ChromaDB, BM25, LlamaIndex | Basic document search |
| `graphrag` | + langextract, SimplePropertyGraphStore | Development GraphRAG |
| `graphrag-all` | + Kuzu database | Production GraphRAG |

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

## Verifying Installation

```bash
# Check CLI version
agent-brain --version

# Check server package
python -c "import agent_brain_server; print(agent_brain_server.__version__)"

# Verify all dependencies
agent-brain verify
```

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

## Troubleshooting Installation

### pip installation fails

```bash
# Upgrade pip first
pip install --upgrade pip

# Try with --no-cache-dir
pip install --no-cache-dir agent-brain-rag agent-brain-cli
```

### Dependency conflicts

```bash
# Create virtual environment
python -m venv agent-brain-env
source agent-brain-env/bin/activate  # Linux/macOS
# or
.\agent-brain-env\Scripts\activate   # Windows

pip install agent-brain-rag agent-brain-cli
```

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

## Uninstallation

```bash
pip uninstall agent-brain-rag agent-brain-cli -y
```

## Next Steps

After installation:

1. [Configure providers](provider-configuration.md)
2. [Initialize your project](../SKILL.md#server-management)
3. [Index documents](../SKILL.md#server-management)
4. [Start searching](../SKILL.md#search-modes)
