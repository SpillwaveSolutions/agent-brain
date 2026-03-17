---
name: agent-brain-help
description: Show available Agent Brain commands and usage
parameters:
  - name: command
    description: Specific command to get help for
    required: false
skills:
  - using-agent-brain
  - agent-brain-setup
---

# Agent Brain Help

## Purpose

Displays available Agent Brain commands and usage information. Without parameters, shows a summary of all commands. With a specific command name, shows detailed help for that command.

## Usage

```
/agent-brain:agent-brain-help [--command <name>]
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| --command | No | - | Specific command to get detailed help for |

### Examples

```
/agent-brain:agent-brain-help                        # Show all commands
/agent-brain:agent-brain-help --command search       # Detailed help for search
/agent-brain:agent-brain-help --command index        # Detailed help for index
```

## Execution

### Without Parameters: Show All Commands

Display the complete command reference:

```
Agent Brain Commands
====================

SEARCH COMMANDS
  agent-brain-search     Hybrid BM25+semantic search (recommended default)
  agent-brain-bm25       Pure BM25 keyword search for exact terms
  agent-brain-keyword    Alias for BM25 keyword search
  agent-brain-hybrid     Hybrid BM25+semantic with alpha tuning
  agent-brain-graph      GraphRAG relationship search (requires ENABLE_GRAPH_INDEX=true)

SETUP COMMANDS
  agent-brain-install    Install Agent Brain packages from PyPI
  agent-brain-config     View and manage provider configuration
  agent-brain-init       Initialize Agent Brain for current project

SERVER COMMANDS
  agent-brain-start      Start the Agent Brain server for this project
  agent-brain-stop       Stop the running server
  agent-brain-status     Show server status, port, and document count
  agent-brain-list       List all running Agent Brain instances

INDEXING COMMANDS
  agent-brain-index      Index documents for search
  agent-brain-inject     Index documents with content injection (scripts/metadata)
  agent-brain-folders    Manage indexed folders (list, add, remove)
  agent-brain-types      List available file type presets
  agent-brain-jobs       Monitor and manage async indexing jobs
  agent-brain-reset      Clear the document index (requires confirmation)

CACHE COMMANDS
  agent-brain-cache      View cache metrics or clear embedding cache

RUNTIME COMMANDS
  agent-brain-install-agent  Install plugin for a runtime (Claude, OpenCode, Gemini, Codex, skill-runtime)
  agent-brain-uninstall      Uninstall Agent Brain plugin files

HELP
  agent-brain-help       Show this help message

Use '/agent-brain:agent-brain-help --command <name>' for detailed help on any command.
```

### With --command Parameter: Show Detailed Help

Display detailed information for the specified command:

```bash
agent-brain <command> --help
```

**Example output for `/agent-brain:agent-brain-help --command search`:**

```
agent-brain-search
==================

Hybrid BM25+semantic search combining keyword matching with semantic similarity.
This is the recommended default search mode for most queries.

USAGE
  /agent-brain:agent-brain-search <query> [options]

PARAMETERS
  query       Required. The search query text.
  --top-k     Number of results (1-20). Default: 5
  --threshold Minimum relevance score (0.0-1.0). Default: 0.3
  --alpha     Hybrid blend (0=BM25, 1=semantic). Default: 0.5

EXAMPLES
  /agent-brain:agent-brain-search "authentication flow"
  /agent-brain:agent-brain-search "error handling" --top-k 10
  /agent-brain:agent-brain-search "OAuth" --alpha 0.3 --threshold 0.5

SEE ALSO
  agent-brain-semantic   For pure conceptual queries
  agent-brain-keyword    For exact term matching
```

## Output

### All Commands View

Format as grouped table:
- Group by category (Search, Setup, Server, Indexing, Help)
- Show command name and brief description
- Include footer with how to get detailed help

### Single Command View

Show comprehensive details:
- Full command name and description
- Usage syntax
- All parameters with types and defaults
- 2-3 practical examples
- Related commands (See Also)

## Command Reference

| Command | Category | Description |
|---------|----------|-------------|
| agent-brain-search | Search | Hybrid BM25+semantic search |
| agent-brain-bm25 | Search | Pure BM25 keyword search |
| agent-brain-keyword | Search | Alias for BM25 keyword search |
| agent-brain-hybrid | Search | Hybrid BM25+semantic with alpha tuning |
| agent-brain-graph | Search | GraphRAG relationship search* |
| agent-brain-install | Setup | Install packages from PyPI |
| agent-brain-config | Setup | View and manage provider configuration |
| agent-brain-init | Setup | Initialize for current project |
| agent-brain-embeddings | Setup | Configure embedding provider |
| agent-brain-start | Server | Start the server |
| agent-brain-stop | Server | Stop the server |
| agent-brain-status | Server | Show server status |
| agent-brain-list | Server | List all instances |
| agent-brain-index | Indexing | Index documents |
| agent-brain-inject | Indexing | Index with content injection |
| agent-brain-folders | Indexing | Manage indexed folders (list, add, remove) |
| agent-brain-types | Indexing | List file type presets |
| agent-brain-jobs | Indexing | Monitor and manage async jobs |
| agent-brain-reset | Indexing | Clear the index |
| agent-brain-cache | Cache | View cache metrics or clear embedding cache |
| agent-brain-install-agent | Runtime | Install plugin for Claude, OpenCode, Gemini, Codex, or skill-runtime |
| agent-brain-uninstall | Runtime | Uninstall Agent Brain plugin |
| agent-brain-help | Help | Show help |

*Graph search requires `ENABLE_GRAPH_INDEX=true` (disabled by default)

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| Unknown command | Invalid command name specified | Check spelling, use `/agent-brain:agent-brain-help` for list |
| Command not found | Typo in command parameter | Refer to command reference table above |

## Notes

- All commands use the `agent-brain-` prefix
- Commands can be invoked as `/agent-brain:agent-brain-<name>` in Claude Code
- Setup commands are typically run once per project
- Search commands require a running server with indexed documents
- GraphRAG is disabled by default. Enable with `export ENABLE_GRAPH_INDEX=true` before starting the server, then re-index documents
