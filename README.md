# Agent Brain

A RAG-based (Retrieval-Augmented Generation) document indexing and semantic search system for AI agents and applications. Agent Brain enables intelligent querying of documentation and source code using natural language.

## Overview

Agent Brain provides **AI-first** document and code search through a Claude Code plugin with skills, commands, and agents. Use slash commands to search, agents for complex research tasks, and skills for intelligent query optimization.

| Component | Description |
|-----------|-------------|
| **Plugin** | 24 slash commands, 3 agents, 2 skills for Claude Code |
| **Skills** | Intelligent search mode selection and query optimization |
| **Agents** | Research assistant, search assistant, setup assistant |
| **Server** | FastAPI backend for indexing and retrieval |
| **CLI** | Command-line tool (also used by plugin internally) |

## Quick Start (Claude Code Plugin)

### 1. Install the Plugin

```bash
claude plugins install github:SpillwaveSolutions/agent-brain
```

### 2. Set Up Your Project

In Claude Code, run:
```
/agent-brain-setup
```

This interactive wizard will:
- Install the Python packages (`agent-brain-rag`, `agent-brain-cli`)
- Configure your API keys
- Initialize the project
- Start the server
- Index your documentation

### 3. Search with Commands

```
/agent-brain-search "how does authentication work"
```

That's it! The plugin handles everything automatically.

## Plugin Commands

### Search Commands

| Command | Description | Use When |
|---------|-------------|----------|
| `/agent-brain-search` | Smart hybrid search (recommended) | General questions |
| `/agent-brain-semantic` | Pure semantic/vector search | Conceptual queries |
| `/agent-brain-keyword` | BM25 keyword search | Error messages, function names |
| `/agent-brain-hybrid` | Hybrid with alpha tuning | Fine-tuned searches |
| `/agent-brain-graph` | Knowledge graph search | "What calls X?", dependencies |
| `/agent-brain-multi` | All modes combined (RRF) | Maximum recall |

### Server Commands

| Command | Description |
|---------|-------------|
| `/agent-brain-start` | Start the server (auto-port) |
| `/agent-brain-stop` | Stop the server |
| `/agent-brain-status` | Check health and document count |
| `/agent-brain-index` | Index documents or code |

### Setup Commands

| Command | Description |
|---------|-------------|
| `/agent-brain-setup` | Complete guided setup wizard |
| `/agent-brain-install` | Install pip packages |
| `/agent-brain-init` | Initialize project directory |
| `/agent-brain-verify` | Verify configuration |
| `/agent-brain-providers` | Configure embedding/summarization providers |

## Plugin Agents

Agent Brain includes three intelligent agents for complex tasks:

| Agent | Description | Triggered By |
|-------|-------------|--------------|
| **Search Assistant** | Multi-step search across modes, synthesizes answers | "Find all references to...", "Research how..." |
| **Research Assistant** | Deep exploration with follow-up queries | "Investigate...", "Analyze the architecture of..." |
| **Setup Assistant** | Guided installation and troubleshooting | "Help me set up Agent Brain", configuration issues |

### Example Agent Interaction

**You**: "Research how authentication is implemented across the codebase"

**Research Assistant**:
1. Searches documentation for auth concepts
2. Queries code for auth-related functions
3. Uses graph mode to find dependencies
4. Synthesizes comprehensive answer with references

## Plugin Skills

Skills provide intelligent context to Claude for optimal searching:

| Skill | Purpose |
|-------|---------|
| **using-agent-brain** | Search mode selection, query optimization, API knowledge |
| **configuring-agent-brain** | Installation, provider configuration, troubleshooting |

When you ask about documentation or code, Claude automatically uses the skill to:
- Choose the best search mode for your query
- Set appropriate parameters (top_k, threshold, alpha)
- Interpret and synthesize results

## Search Modes

| Mode | Best For | Example Query |
|------|----------|---------------|
| `HYBRID` | General questions (default) | "How does caching work?" |
| `VECTOR` | Conceptual understanding | "Explain the architecture" |
| `BM25` | Exact terms, error codes | "NullPointerException", "getUserById" |
| `GRAPH` | Relationships, dependencies | "What classes use AuthService?" |
| `MULTI` | Comprehensive search | "Everything about data validation" |

## Pluggable Providers

Agent Brain supports multiple providers for embeddings and summarization:

### Embedding Providers
| Provider | Models | Local |
|----------|--------|-------|
| OpenAI | text-embedding-3-large, text-embedding-3-small | No |
| Ollama | nomic-embed-text, mxbai-embed-large | Yes |
| Cohere | embed-english-v3.0, embed-multilingual-v3.0 | No |

### Summarization Providers
| Provider | Models | Local |
|----------|--------|-------|
| Anthropic | claude-haiku-4-5-20251001, claude-sonnet-4-5-20250514 | No |
| OpenAI | gpt-5, gpt-5-mini | No |
| Gemini | gemini-3-flash, gemini-3-pro | No |
| Grok | grok-4, grok-4-fast | No |
| Ollama | llama4:scout, mistral-small3.2, qwen3-coder | Yes |

### Fully Local Mode

Run completely offline with Ollama:
```
/agent-brain-providers
# Select Ollama for both embeddings and summarization
```

## Features

### Code Search
- **10 Programming Languages**: Python, TypeScript, JavaScript, Java, Kotlin, C, C++, C#, Go, Rust, Swift
- **AST-Aware Chunking**: Tree-sitter parsing preserves code structure
- **LLM Summaries**: AI-generated descriptions improve semantic search
- **Language Filtering**: Filter results by programming language

### GraphRAG (Knowledge Graph)
- Entity and relationship extraction
- Dependency-aware queries ("What calls X?")
- Code structure visualization

### Multi-Instance Architecture
- Per-project isolated servers
- Automatic port allocation
- Work on multiple projects simultaneously

## Project Structure

```
agent-brain/
├── agent-brain-plugin/        # Claude Code plugin (primary interface)
│   ├── commands/              # 24 slash commands
│   ├── agents/                # 3 intelligent agents
│   └── skills/                # 2 context skills
├── agent-brain-server/        # FastAPI backend
├── agent-brain-cli/           # CLI tool (used by plugin)
└── docs/                      # Documentation
```

## Documentation

### Getting Started
- [Quick Start](docs/QUICK_START.md) - Get running in minutes
- [Plugin Guide](docs/PLUGIN_GUIDE.md) - Complete plugin documentation
- [User Guide](docs/USER_GUIDE.md) - Detailed usage guide

### Reference
- [API Reference](docs/API_REFERENCE.md) - REST API documentation
- [Configuration](docs/CONFIGURATION.md) - All configuration options
- [Provider Configuration](agent-brain-plugin/skills/using-agent-brain/references/provider-configuration.md) - Provider setup

### Architecture
- [Architecture Overview](docs/ARCHITECTURE.md) - System design
- [GraphRAG Guide](docs/GRAPHRAG_GUIDE.md) - Knowledge graph features
- [Code Indexing](docs/CODE_INDEXING.md) - AST-aware chunking

## CLI Usage (Alternative)

While the plugin is the recommended interface, you can also use the CLI directly:

```bash
# Install
pip install agent-brain-rag agent-brain-cli

# Initialize and start
agent-brain init
agent-brain start --daemon

# Index and query
agent-brain index /path/to/docs --include-code
agent-brain query "authentication" --mode hybrid
```

## Development

### Prerequisites
- Python 3.10+
- Poetry (dependency management)
- Task (task runner)

### Setup
```bash
git clone https://github.com/SpillwaveSolutions/agent-brain.git
cd agent-brain
task install
```

### Running Tests
```bash
task test           # All tests
task before-push    # Full quality check
```

## Technology Stack

- **Plugin**: Claude Code slash commands, agents, skills
- **Server**: FastAPI + Uvicorn
- **Vector Store**: ChromaDB (HNSW, cosine similarity)
- **BM25 Index**: LlamaIndex BM25Retriever
- **Graph Store**: SimplePropertyGraphStore / Kuzu
- **Embeddings**: OpenAI or Ollama
- **Summarization**: Claude, GPT-5, Gemini, Grok, or Ollama
- **AST Parsing**: tree-sitter (10 languages)
- **CLI**: Click + Rich
- **Build System**: Poetry

## Contributing

See the [Developer Guide](docs/DEVELOPERS_GUIDE.md) for setup instructions.

**Before pushing changes**, always run:
```bash
task before-push
```

## License

MIT License - see LICENSE file for details.

## Links

- [GitHub Wiki](https://github.com/SpillwaveSolutions/agent-brain/wiki)
- [Plugin Marketplace](https://skillzwave.ai/)
- [Issue Tracker](https://github.com/SpillwaveSolutions/agent-brain/issues)
