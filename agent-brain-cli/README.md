# Agent Brain CLI

> Command-line interface for managing AI agent memory and knowledge retrieval with the **Agent Brain** RAG server.

**Agent Brain** (formerly doc-serve) is an intelligent document indexing and semantic search system designed to give AI agents long-term memory. This CLI provides a convenient way to manage your Agent Brain server and knowledge base.

[![PyPI version](https://badge.fury.io/py/agent-brain-cli.svg)](https://pypi.org/project/agent-brain-cli/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Why Agent Brain?

AI agents need persistent memory to be truly useful. Agent Brain provides the retrieval infrastructure that enables context-aware, knowledge-grounded AI interactions.

### Search Capabilities

| Search Type | Description | Best For |
|-------------|-------------|----------|
| **Semantic Search** | Natural language queries using OpenAI embeddings | Conceptual questions, related content |
| **Keyword Search (BM25)** | Traditional keyword matching with TF-IDF ranking | Exact matches, technical terms |
| **Hybrid Search** | Combines vector + BM25 approaches | General-purpose queries |
| **GraphRAG** | Knowledge graph retrieval | Understanding relationships |

## Installation

```bash
pip install agent-brain-cli
```

## Quick Start

```bash
agent-brain init          # Initialize project
agent-brain start         # Start server
agent-brain index ./docs  # Index documents
agent-brain query "search term"
```

> **Note**: The legacy command `doc-svr-ctl` is still available but deprecated. Please use `agent-brain` for new installations.

## Development Installation

```bash
cd agent-brain-cli
poetry install
```

## Usage

```bash
# Check server status
agent-brain status

# Search documents
agent-brain query "how to use python"

# Index documents from a folder
agent-brain index ./docs

# Reset/clear the index
agent-brain reset --yes
```

## Configuration

Set the server URL via environment variable:

```bash
export AGENT_BRAIN_URL=http://localhost:8000
```

Or use the `--url` flag:

```bash
agent-brain --url http://localhost:8000 status
```

> **Note**: The legacy environment variable `DOC_SERVE_URL` is still supported for backwards compatibility.

## Commands

### Server Management

| Command | Description |
|---------|-------------|
| `init` | Initialize project for Agent Brain (creates `.claude/agent-brain/`) |
| `start` | Start the Agent Brain server for current project |
| `stop` | Stop the running server |
| `list` | List all running Agent Brain instances |
| `status` | Check server health and indexing status |

### Data Management

| Command | Description |
|---------|-------------|
| `query` | Search indexed documents |
| `index` | Start indexing documents from a folder |
| `reset` | Clear all indexed documents |

## Options

All commands support:
- `--url` - Server URL (or `AGENT_BRAIN_URL` / `DOC_SERVE_URL` env var)
- `--json` - Output as JSON for scripting

## Example Workflow

```bash
# 1. Initialize a new project
cd my-project
agent-brain init

# 2. Start the server
agent-brain start

# 3. Index your documentation
agent-brain index ./docs ./src

# 4. Query your knowledge base
agent-brain query "How does authentication work?"

# 5. Stop when done
agent-brain stop
```

## Documentation

- [User Guide](https://github.com/SpillwaveSolutions/agent-brain/wiki/User-Guide) - Getting started and usage
- [Developer Guide](https://github.com/SpillwaveSolutions/agent-brain/wiki/Developer-Guide) - Contributing and development
- [API Reference](https://github.com/SpillwaveSolutions/agent-brain/wiki/API-Reference) - Full API documentation

## Release Information

- **Current Version**: See [pyproject.toml](./pyproject.toml)
- **Release Notes**: [GitHub Releases](https://github.com/SpillwaveSolutions/agent-brain/releases)
- **Changelog**: [Latest Release](https://github.com/SpillwaveSolutions/agent-brain/releases/latest)

## Related Packages

- [agent-brain-rag](https://pypi.org/project/agent-brain-rag/) - The RAG server that powers Agent Brain

## License

MIT
