# Agent Brain Plugin

A Claude Code plugin for document search with hybrid BM25/semantic retrieval. Index your documentation and source code, then search using keyword matching, semantic similarity, or combined hybrid mode.

## Features

- **Hybrid Search**: Combines BM25 keyword matching with semantic vector search for best results
- **Three Search Modes**: BM25 (fast keywords), Vector (semantic), Hybrid (combined)
- **Multi-Instance**: Run separate servers for different projects with automatic port allocation
- **Code Search**: AST-aware indexing for Python, TypeScript, JavaScript, Java, Go, Rust, C, C++

## Installation

### 1. Install Claude Code Plugin

```bash
# Add the marketplace, then install the plugin from it
claude plugins marketplace add SpillwaveSolutions/agent-brain
claude plugins install agent-brain@agent-brain-marketplace
```

### 2. Install Agent Brain Packages

```bash
pip install agent-brain-rag agent-brain-cli
```

### 3. Configure API Key

```bash
export OPENAI_API_KEY="sk-proj-..."
```

### 4. Initialize and Start

```bash
agent-brain init
agent-brain start
agent-brain index /path/to/docs
```

## Quick Start

Once installed, use these slash commands in Claude Code:

```
/agent-brain-search "authentication flow"    # Hybrid search (recommended)
/agent-brain-semantic "how does auth work"   # Conceptual search
/agent-brain-keyword "AuthenticationError"   # Exact term search
```

## Commands

### Search Commands
| Command | Description |
|---------|-------------|
| `/agent-brain-search` | Hybrid search (BM25 + semantic) |
| `/agent-brain-semantic` | Semantic vector search |
| `/agent-brain-keyword` | BM25 keyword search |

### Setup Commands
| Command | Description |
|---------|-------------|
| `/agent-brain-install` | Install pip packages |
| `/agent-brain-setup` | Complete guided setup |
| `/agent-brain-config` | Configure API keys |
| `/agent-brain-init` | Initialize project |
| `/agent-brain-verify` | Verify installation |

### Server Commands
| Command | Description |
|---------|-------------|
| `/agent-brain-start` | Start server (auto-port) |
| `/agent-brain-stop` | Stop server |
| `/agent-brain-status` | Show server health |
| `/agent-brain-list` | List all instances |

### Indexing Commands
| Command | Description |
|---------|-------------|
| `/agent-brain-index` | Index documents |
| `/agent-brain-reset` | Clear all indexed content |

### Help
| Command | Description |
|---------|-------------|
| `/agent-brain-help` | Show all commands |

## Search Modes

| Mode | Speed | Best For | Example Query |
|------|-------|----------|---------------|
| `hybrid` | Slower | General queries | "OAuth implementation guide" |
| `bm25` | Fast | Technical terms, function names | "AuthenticationError" |
| `vector` | Slower | Concepts, explanations | "how does authentication work" |

## Requirements

- Python 3.10+
- OpenAI API key (for vector/hybrid search)
- Optional: Anthropic API key (for code summarization)

## Skills

This plugin includes two skills:

1. **using-agent-brain**: Search mode guidance and API reference
2. **agent-brain-setup**: Installation, configuration, and troubleshooting

## License

MIT

## Support

- Issues: https://github.com/SpillwaveSolutions/agent-brain-plugin/issues
- Documentation: See `skills/` folder for detailed guides
