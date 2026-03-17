---
last_validated: 2026-03-16
---

# Agent Brain User Guide

This guide covers how to use Agent Brain for document indexing and semantic search using the Claude Code plugin.

## Table of Contents

- [Overview](#overview)
- [Plugin Commands](#plugin-commands)
- [Plugin Agents](#plugin-agents)
- [Search Modes](#search-modes)
- [Two-Stage Retrieval with Reranking](#two-stage-retrieval-with-reranking)
- [Indexing](#indexing)
- [Folder Management](#folder-management)
- [File Type Presets](#file-type-presets)
- [Content Injection](#content-injection)
- [Chunk Eviction](#chunk-eviction)
- [File Watcher](#file-watcher)
- [Embedding Cache](#embedding-cache)
- [Job Queue](#job-queue)
- [Provider Configuration](#provider-configuration)
- [Multi-Project Support](#multi-project-support)
- [Runtime Autodiscovery](#runtime-autodiscovery)
- [Runtime Installation](#runtime-installation)
- [CLI Reference](#cli-reference)
- [Local Integration Check](#local-integration-check)
- [Troubleshooting](#troubleshooting)

---

## Overview

Agent Brain is a RAG (Retrieval-Augmented Generation) system that indexes and searches documentation and source code. The primary interface is the **Claude Code plugin** which provides:

| Component | Count | Description |
|-----------|-------|-------------|
| **Commands** | 30 | Slash commands for all operations |
| **Agents** | 3 | Intelligent assistants for complex tasks |
| **Skills** | 2 | Context for optimal search and configuration |

### How It Works

1. **Indexing**: Reads documents/code, splits into semantic chunks, generates embeddings
2. **Storage**: Stores chunks in ChromaDB with metadata for filtering
3. **Retrieval**: Finds similar chunks using hybrid search (semantic + keyword)
4. **GraphRAG**: Extracts entities and relationships for dependency queries

---

## Plugin Commands

### Search Commands

| Command | Description | Best For |
|---------|-------------|----------|
| `/agent-brain-search` | Smart hybrid search | General questions |
| `/agent-brain-semantic` | Pure vector search | Conceptual queries |
| `/agent-brain-keyword` | BM25 keyword search | Exact terms, function names |
| `/agent-brain-bm25` | Alias for keyword search | Error messages, symbols |
| `/agent-brain-vector` | Alias for semantic search | "How does X work?" |
| `/agent-brain-hybrid` | Hybrid with alpha control | Fine-tuned searches |
| `/agent-brain-graph` | Knowledge graph search | Dependencies, relationships |
| `/agent-brain-multi` | All modes with RRF fusion | Maximum recall |

### Server Commands

| Command | Description |
|---------|-------------|
| `/agent-brain-start` | Start server (auto-port allocation) |
| `/agent-brain-stop` | Stop the running server |
| `/agent-brain-status` | Check health and document count |
| `/agent-brain-list` | List all running instances |
| `/agent-brain-index` | Index documents or code |
| `/agent-brain-reset` | Clear the index |
| `/agent-brain-jobs` | Manage indexing job queue |

### Index Management Commands

| Command | Description |
|---------|-------------|
| `/agent-brain-folders` | Manage indexed folders (list, add, remove) |
| `/agent-brain-inject` | Inject custom metadata into chunks during indexing |
| `/agent-brain-types` | List available file type presets for indexing |
| `/agent-brain-cache` | View embedding cache metrics or clear the cache |

### Setup Commands

| Command | Description |
|---------|-------------|
| `/agent-brain-setup` | Complete guided setup wizard |
| `/agent-brain-install` | Install pip packages |
| `/agent-brain-install-agent` | Install for different AI runtimes (Claude, OpenCode, Gemini, Codex) |
| `/agent-brain-init` | Initialize project directory |
| `/agent-brain-config` | View/edit configuration |
| `/agent-brain-verify` | Verify configuration |
| `/agent-brain-help` | Show help information |
| `/agent-brain-version` | Show version information |

### Provider Commands

| Command | Description |
|---------|-------------|
| `/agent-brain-providers` | List and configure providers |
| `/agent-brain-embeddings` | Configure embedding provider |
| `/agent-brain-summarizer` | Configure summarization provider |

---

## Plugin Agents

Agent Brain includes three intelligent agents that handle complex, multi-step tasks:

### Search Assistant

Performs multi-step searches across different modes and synthesizes answers.

**Triggers**: "Find all references to...", "Search for...", "What files contain..."

**Example**:
```
You: "Find all references to the authentication module"

Search Assistant:
1. Searches documentation for auth concepts
2. Searches code for auth imports and usage
3. Uses graph mode to find dependencies
4. Returns comprehensive list with file locations
```

### Research Assistant

Deep exploration with follow-up queries and cross-referencing.

**Triggers**: "Research how...", "Investigate...", "Analyze the architecture of..."

**Example**:
```
You: "Research how error handling is implemented"

Research Assistant:
1. Identifies error handling patterns in docs
2. Finds exception classes and try/catch blocks
3. Traces error propagation through call graph
4. Synthesizes findings with code references
```

### Setup Assistant

Guided installation, configuration, and troubleshooting.

**Triggers**: "Help me set up Agent Brain", "Configure...", "Why isn't... working"

**Example**:
```
You: "Help me set up Agent Brain with Ollama"

Setup Assistant:
1. Checks if Ollama is installed
2. Verifies embedding model is pulled
3. Configures provider settings
4. Tests the configuration
5. Reports success or guides through fixes
```

---

## Search Modes

### HYBRID (Default)

Combines semantic similarity with keyword matching. Best for general questions.

```
/agent-brain-search "how does the caching system work"
```

Adjust the balance with `--alpha`:
- `--alpha 0.7` - More semantic (conceptual queries)
- `--alpha 0.3` - More keyword (specific terms)

```
/agent-brain-hybrid "authentication flow" --alpha 0.7
```

### VECTOR (Semantic)

Pure embedding-based search. Best for conceptual understanding.

```
/agent-brain-semantic "explain the overall architecture"
```

### BM25 (Keyword)

TF-IDF based search. Best for exact terms, function names, error codes.

```
/agent-brain-keyword "NullPointerException"
/agent-brain-bm25 "getUserById"
```

### GRAPH (Knowledge Graph)

Traverses entity relationships. Best for dependency and relationship queries.

```
/agent-brain-graph "what classes use AuthService"
/agent-brain-graph "what calls the validate function"
```

### MULTI (Fusion)

Combines all modes using Reciprocal Rank Fusion. Best for maximum recall.

```
/agent-brain-multi "everything about data validation"
```

---

## Two-Stage Retrieval with Reranking

Agent Brain can optionally use two-stage retrieval to improve search precision by 15-20%.

### How It Works

**Without Reranking (Default)**:
1. Query is embedded using the embedding model
2. Vector similarity search finds top_k most similar documents
3. Results are returned

**With Reranking Enabled**:
1. Query is embedded using the embedding model
2. Vector + BM25 hybrid search retrieves 10x more candidates
3. Cross-encoder model scores each candidate for relevance to the query
4. Results are reordered by cross-encoder score
5. Top_k results are returned

### Why Reranking Helps

Embedding models (bi-encoders) are fast but approximate. They encode the query and documents separately, then compare vectors. This can miss nuanced relevance.

Cross-encoders process the query AND document together, allowing the model to attend across both texts. This is slower but more accurate.

### When to Enable Reranking

Enable reranking when:
- Precision matters more than latency
- Queries are complex or nuanced
- Initial results seem "close but not quite right"

Keep reranking disabled when:
- Latency is critical (real-time search)
- Running on resource-constrained hardware
- Search quality is already acceptable

### Configuration

Enable with environment variable:
```bash
export ENABLE_RERANKING=true
```

Or in config.yaml:
```yaml
reranker:
  provider: sentence-transformers
  model: cross-encoder/ms-marco-MiniLM-L-6-v2
```

### Provider Choices

**sentence-transformers (Recommended)**:
- Uses HuggingFace CrossEncoder models
- Downloads model on first use (~50MB)
- Fast inference (~50ms for 100 candidates)

**ollama (Fully Local)**:
- Uses Ollama chat completions for scoring
- No external downloads
- Slower (~500ms for 100 candidates)
- Requires Ollama running locally

### Response Fields

When reranking is enabled, results include additional metadata:
- `rerank_score`: Cross-encoder relevance score
- `original_rank`: Position before reranking (1-indexed)

---

## Indexing

### Index Documentation

```
/agent-brain-index ./docs
```

### Index Code and Documentation

```
/agent-brain-index . --include-code
```

### Index Specific Languages

```
/agent-brain-index ./src --include-code --languages python,typescript
```

### Index with File Type Presets

```
/agent-brain-index ./src --include-type python
/agent-brain-index ./project --include-type python,docs
```

### Generate Code Summaries

Improves semantic search for code by generating LLM descriptions:

```
/agent-brain-index ./src --include-code --generate-summaries
```

### Supported Languages

Agent Brain supports AST-aware chunking for:
- **Python** (.py)
- **TypeScript** (.ts, .tsx)
- **JavaScript** (.js, .jsx)
- **Java** (.java)
- **Go** (.go)
- **Rust** (.rs)
- **C** (.c, .h)
- **C++** (.cpp, .hpp, .cc)
- **C#** (.cs, .csx)
- **Swift** (.swift)

Other languages use intelligent text-based chunking.

### Check Index Status

```
/agent-brain-status
```

### Clear and Rebuild Index

```
/agent-brain-reset
/agent-brain-index . --include-code
```

---

## Folder Management

Agent Brain tracks indexed folders and provides commands to list, add, and remove them. Folders are persisted in a JSONL manifest that enables incremental re-indexing -- only changed files are processed on subsequent runs.

### List Indexed Folders

Show all indexed folders with chunk counts and last-indexed timestamps:

```
agent-brain folders list
```

Example output:
```
Folder Path              Chunks  Last Indexed
/home/user/docs          312     2026-02-24T12:00:00
/home/user/src           1024    2026-02-24T13:30:00
```

### Add a Folder

Queue an indexing job for a folder. Supports all indexing options:

```
agent-brain folders add ./docs
agent-brain folders add ./src --include-code
agent-brain folders add ./src --include-type python,docs
agent-brain folders add ./docs --force
```

Adding an already-indexed folder triggers incremental re-indexing (only changed files are processed). Use `--force` to bypass the manifest and re-index everything.

### Remove a Folder

Remove all indexed chunks associated with a folder:

```
agent-brain folders remove ./old-docs
agent-brain folders remove ./old-docs --yes   # skip confirmation
```

The folder does not need to exist on disk to be removed from the index.

### File Watcher Integration

When adding a folder, you can enable automatic re-indexing via the file watcher (see [File Watcher](#file-watcher) section). Folders with `watch_mode=auto` are monitored for changes and re-indexed automatically.

### Plugin Command

Use the plugin command for the same operations:

```
/agent-brain-folders list
/agent-brain-folders add ./src --include-code
/agent-brain-folders remove ./old-docs --yes
```

---

## File Type Presets

File type presets are named groups of glob patterns that simplify indexing. Instead of specifying individual file extensions, use a preset name with the `--include-type` flag.

### Available Presets

| Preset | Extensions |
|--------|------------|
| `python` | `*.py`, `*.pyi`, `*.pyw` |
| `javascript` | `*.js`, `*.jsx`, `*.mjs`, `*.cjs` |
| `typescript` | `*.ts`, `*.tsx` |
| `go` | `*.go` |
| `rust` | `*.rs` |
| `java` | `*.java` |
| `csharp` | `*.cs` |
| `c` | `*.c`, `*.h` |
| `cpp` | `*.cpp`, `*.hpp`, `*.cc`, `*.hh` |
| `web` | `*.html`, `*.css`, `*.scss`, `*.jsx`, `*.tsx` |
| `docs` | `*.md`, `*.txt`, `*.rst`, `*.pdf` |
| `text` | `*.md`, `*.txt`, `*.rst` |
| `pdf` | `*.pdf` |
| `code` | All programming language extensions combined |

### Usage Examples

```bash
# Index only Python files
agent-brain index ./src --include-type python

# Index Python and documentation files
agent-brain index ./project --include-type python,docs

# Index all code files
agent-brain index ./repo --include-type code

# Combine presets with custom patterns
agent-brain index ./project --include-type typescript --include-patterns "*.json"
```

### Viewing Available Presets

Use the types command to see all presets:

```
/agent-brain-types
```

Presets can be combined with commas: `--include-type python,docs`. The `code` preset is a union of all individual language presets.

---

## Content Injection

Content injection enriches chunk metadata during indexing using custom Python scripts or static JSON metadata files. Injectors run after chunking but before embedding generation (step 2.5 in the pipeline), so enriched metadata is stored alongside vectors in the index.

### Script Injection

Provide a Python script that exports a `process_chunk` function:

```bash
agent-brain inject ./docs --script enrich.py
```

The script must define:

```python
def process_chunk(chunk: dict) -> dict:
    """Enrich a single chunk with custom metadata."""
    chunk["project"] = "my-project"
    chunk["team"] = "backend"
    return chunk
```

**Input keys available:** `chunk_id`, `content`, `source`, `language`, `start_line`, `end_line`, `summary`

**Constraints:**
- Values must be scalars (str, int, float, bool) -- lists and dicts are stripped for ChromaDB compatibility
- Core schema keys (`chunk_id`, `source`, etc.) cannot be overwritten
- Exceptions are caught per-chunk and logged as warnings (the pipeline continues)

### Folder Metadata Injection

Merge a static JSON file into every chunk from a folder:

```bash
agent-brain inject ./src --folder-metadata project-meta.json --include-code
```

JSON format:
```json
{
  "project": "my-project",
  "team": "backend",
  "version": "2.0"
}
```

### Dry-Run Validation

Validate an injector against sample chunks without actually indexing:

```bash
agent-brain inject ./docs --script enrich.py --dry-run
```

### Plugin Command

```
/agent-brain-inject ./docs --script enrich.py
/agent-brain-inject ./src --folder-metadata project-meta.json --include-code
/agent-brain-inject ./docs --script enrich.py --dry-run
```

At least one of `--script` or `--folder-metadata` must be provided.

---

## Chunk Eviction

When files change or are removed, Agent Brain automatically evicts stale chunks from the index during the next indexing run. This is powered by the manifest tracker, which records per-file checksums, modification times, and chunk IDs.

### How It Works

1. **Manifest comparison**: On each indexing run, the current filesystem state is compared against the prior folder manifest.
2. **Diff computation**: Files are categorized as added, changed, deleted, or unchanged.
   - **mtime check first**: If the file modification time is unchanged, the file is skipped (fast path).
   - **Checksum verification**: If mtime changed, a SHA-256 content checksum confirms whether the content actually changed (handles `touch`, `git checkout`, etc.).
3. **Bulk eviction**: Chunk IDs for deleted and changed files are removed from the storage backend in bulk.
4. **Re-indexing**: Only added and changed files are processed, saving time on large codebases.

### Force Mode

Use `--force` to bypass the manifest and re-index all files:

```bash
agent-brain index ./src --force
```

Force mode evicts all prior chunks for the folder and processes every file fresh.

### Manifest Storage

Manifests are stored as JSON files in the state directory:
```
.agent-brain/manifests/<sha256(folder_path)>.json
```

Each manifest records per-file checksums, mtimes, and chunk IDs for targeted deletion.

---

## File Watcher

The file watcher service monitors indexed folders for changes and triggers automatic incremental re-indexing. It uses `watchfiles` (based on the Rust `notify` crate) for efficient filesystem event detection.

### How It Works

- One asyncio task is created per watched folder
- When file changes are detected, an incremental indexing job is enqueued
- Jobs are deduplicated -- if a job for the same folder is already pending, no duplicate is created
- Changes are debounced to avoid rapid re-indexing (default: 30 seconds)

### Watch Modes

| Mode | Behavior |
|------|----------|
| `off` | No automatic re-indexing (default) |
| `auto` | Watch for changes and re-index automatically |

### Configuration

Configure the file watcher via `config.yaml`:

```yaml
file_watcher:
  default_debounce_seconds: 30  # Global debounce interval
```

Per-folder debounce can be set when adding a folder with watch mode enabled.

### Ignored Directories

The watcher automatically ignores common non-source directories: `.git/`, `__pycache__/`, `node_modules/`, `.venv/`, `dist/`, `build/`, `.next/`, `.nuxt/`, `coverage/`, `htmlcov/`.

### Jobs Triggered by Watcher

Watcher-triggered jobs are tagged with `source="auto"` to distinguish them from manual indexing jobs. They always use `force=False` (incremental mode via the manifest tracker).

---

## Embedding Cache

Agent Brain automatically caches embeddings in a two-layer architecture to avoid redundant API calls. The cache is transparent -- it requires no setup and works with any embedding provider.

### Architecture

- **Layer 1 (Memory)**: In-memory LRU cache with fixed capacity (default: 1,000 entries). Sub-millisecond lookups with zero I/O.
- **Layer 2 (Disk)**: aiosqlite SQLite database in WAL mode. Single-digit millisecond lookups. Persists across server restarts. Default limit: 500 MB (~42,000 entries at 3,072 dimensions).

### Cache Key Format

Keys are computed as `SHA-256(content_text):provider:model:dimensions`. This ensures cached embeddings are invalidated when the embedding provider or model changes.

### Provider Change Detection

On startup, the cache compares the current provider fingerprint against the stored fingerprint. If they differ, all cached embeddings are automatically cleared to prevent dimension mismatches.

### Cache Management Commands

Use the CLI or plugin command to view cache status and clear the cache:

```bash
# View cache metrics
agent-brain cache status

# View metrics as JSON
agent-brain cache status --json

# Clear the cache (prompts for confirmation)
agent-brain cache clear

# Clear without confirmation
agent-brain cache clear --yes
```

Plugin commands:
```
/agent-brain-cache status
/agent-brain-cache clear --yes
```

### Interpreting Cache Metrics

| Metric | Description |
|--------|-------------|
| Entries (disk) | Total embeddings persisted in the SQLite database |
| Entries (memory) | Embeddings in the in-memory LRU (fastest tier) |
| Hit Rate | Percentage of lookups served from cache (higher is better) |
| Hits | Total successful cache lookups this session |
| Misses | Cache misses (embedding computed via API) |
| Size | Disk space used by the cache database |

A healthy cache has a hit rate above 80% after the first full indexing cycle.

### When to Clear the Cache

- After changing embedding provider or model (prevents dimension mismatches)
- If embeddings seem incorrect or queries return poor results
- To force fresh embeddings after significant content changes

---

## Job Queue

As of v3.0.0, indexing operations are queued and processed asynchronously.

### How It Works

1. **Submit**: `POST /index` returns immediately with a job ID
2. **Queue**: Jobs are stored in `.agent-brain/jobs/index_queue.jsonl`
3. **Process**: Background worker processes jobs sequentially
4. **Track**: Poll job status or use CLI `--watch` option

### CLI Jobs Commands

```bash
# List all jobs
agent-brain jobs

# Watch queue with live updates
agent-brain jobs --watch

# Get job details
agent-brain jobs job_abc123def456

# Cancel a job
agent-brain jobs job_abc123def456 --cancel
```

### Job States

| Status | Description |
|--------|-------------|
| `pending` | Queued, waiting to run |
| `running` | Currently processing |
| `done` | Completed successfully |
| `failed` | Failed with error |
| `cancelled` | Cancelled by user |

### Deduplication

The queue automatically deduplicates identical requests. If you submit the same folder with the same options while a job is pending or running, you get back the existing job ID.

### Polling for Completion

```bash
# Check if indexing is done
agent-brain status --json | jq '.indexing.indexing_in_progress'

# Or poll specific job
agent-brain jobs job_abc123 | grep status
```

---

## Provider Configuration

Agent Brain supports pluggable providers for embeddings and summarization.

### Configure Providers Interactively

```
/agent-brain-providers
```

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
# Select Ollama for embeddings
# Select Ollama for summarization
```

---

## Multi-Project Support

Agent Brain supports multiple isolated instances for different projects.

### Initialize a Project

```
/agent-brain-init
```

Creates `.agent-brain/` with project-specific configuration.

### Start Project Server

```
/agent-brain-start
```

Automatically allocates a unique port (no conflicts).

### List Running Instances

```
/agent-brain-list
```

Shows all running Agent Brain servers across projects.

### Work from Subdirectories

Commands automatically resolve the project root:

```
cd src/deep/nested/directory
/agent-brain-status  # Finds the parent project's server
```

---

## Runtime Autodiscovery

The CLI automatically discovers the server URL without manual configuration.

### How It Works

When you run `agent-brain start`, the server writes a `runtime.json` file:

```
.agent-brain/runtime.json
```

Contents:
```json
{
  "base_url": "http://127.0.0.1:49321",
  "port": 49321,
  "bind_host": "127.0.0.1",
  "pid": 12345,
  "started_at": "2026-02-03T10:00:00Z",
  "foreground": false
}
```

### CLI Resolution Order

The CLI resolves the server URL in this priority:

1. **Environment variable**: `AGENT_BRAIN_URL`
2. **Runtime file**: `.agent-brain/runtime.json` (searches cwd upward)
3. **Config file**: `config.yaml` (if contains URL)
4. **Default**: `http://127.0.0.1:8000`

### Config Discovery Order

Config files are searched in this order:

1. `.agent-brain/config.yaml` (cwd, then walk upward)
2. `~/.config/agent-brain/config.yaml` (XDG config)
3. `~/.agent-brain/config.yaml` (legacy, deprecated)
4. Environment variable: `AGENT_BRAIN_CONFIG`

### Example Workflow

```bash
# Start server (writes runtime.json automatically)
agent-brain start

# CLI auto-discovers server URL - no --url flag needed
agent-brain status
agent-brain index ./docs
agent-brain query "search term"
```

---

## Runtime Installation

Agent Brain can be installed for multiple AI runtimes. The `install-agent` command converts the canonical Claude plugin format into the target runtime's native format.

### Supported Runtimes

| Runtime | Command | Default Directory |
|---------|---------|-------------------|
| Claude Code | `--agent claude` | `.claude/plugins/agent-brain/` |
| OpenCode | `--agent opencode` | `.opencode/plugins/agent-brain/` |
| Gemini CLI | `--agent gemini` | `.gemini/plugins/agent-brain/` |
| Codex | `--agent codex` | `.codex/skills/agent-brain/` |
| Any skill-based | `--agent skill-runtime --dir <path>` | (required) |

### Installation Examples

```bash
# Install for Claude Code (default)
agent-brain install-agent --agent claude

# Install for Codex (generates AGENTS.md at project root)
agent-brain install-agent --agent codex

# Install for any skill-based runtime (e.g., Qwen, Cursor)
agent-brain install-agent --agent skill-runtime --dir ./my-skills

# Preview what would be installed
agent-brain install-agent --agent codex --dry-run

# Install globally (user-level)
agent-brain install-agent --agent claude --global

# JSON output for automation
agent-brain install-agent --agent codex --json
```

### Skill-Runtime Converter

The `skill-runtime` converter flattens all plugin artifacts into skill directories:

- **Commands** become individual skill directories with `SKILL.md`
- **Agents** become orchestration skill directories referencing dependent skills
- **Skills** are copied with references intact
- **Templates** are placed in `agent-brain-setup/assets/`
- **Scripts** are placed in `agent-brain-verify/scripts/`

### Codex Adapter

The `codex` adapter is a preset built on `skill-runtime` that also:

- Installs to `.codex/skills/agent-brain/` by default
- Generates/updates `AGENTS.md` at the project root
- Adds invocation guidance headers to each skill
- Uses HTML comment markers for idempotent AGENTS.md updates

### Adding New Runtime Support

To add support for a new runtime, implement the `RuntimeConverter` protocol:

```python
from agent_brain_cli.runtime.converter_base import RuntimeConverter

class MyConverter:
    @property
    def runtime_type(self) -> RuntimeType: ...
    def convert_command(self, command: PluginCommand) -> str: ...
    def convert_agent(self, agent: PluginAgent) -> str: ...
    def convert_skill(self, skill: PluginSkill) -> str: ...
    def install(self, bundle: PluginBundle, target: Path, scope: Scope) -> list[Path]: ...
```

Then register it in `install_agent.py`'s `CONVERTERS` dict.

---

## CLI Reference

For advanced users or automation, the CLI provides direct access:

### Installation

```bash
pip install agent-brain-rag agent-brain-cli
```

### Common Commands

```bash
# Initialize project
agent-brain init

# Start/stop server
agent-brain start          # Backgrounds by default
agent-brain start --foreground  # Run in foreground
agent-brain stop

# Index documents
agent-brain index ./docs --include-code

# Index with file type presets
agent-brain index ./src --include-type python

# Folder management
agent-brain folders list
agent-brain folders add ./src --include-code
agent-brain folders remove ./old-docs --yes

# Content injection
agent-brain inject ./docs --script enrich.py
agent-brain inject ./src --folder-metadata project-meta.json

# Query
agent-brain query "your question" --mode hybrid

# Job management (v3.0+)
agent-brain jobs           # List all jobs
agent-brain jobs --watch   # Watch with live updates
agent-brain jobs JOB_ID    # Job details
agent-brain jobs JOB_ID --cancel  # Cancel job

# Cache management
agent-brain cache status
agent-brain cache clear --yes

# File type presets
agent-brain types list

# Runtime installation
agent-brain install-agent --agent claude
agent-brain install-agent --agent codex
agent-brain install-agent --agent skill-runtime --dir ./skills

# Status
agent-brain status
agent-brain list
```

### Query Options

```bash
# Search modes
agent-brain query "term" --mode vector
agent-brain query "term" --mode bm25
agent-brain query "term" --mode hybrid --alpha 0.7
agent-brain query "term" --mode graph
agent-brain query "term" --mode multi

# Result tuning
agent-brain query "term" --top-k 10 --threshold 0.3

# Filtering
agent-brain query "term" --source-types code
agent-brain query "term" --languages python,typescript

# Output formats
agent-brain query "term" --json
agent-brain query "term" --scores
```

---

## Local Integration Check

Before releasing or after major changes, run the local integration check to validate E2E functionality.

### Running the Check

```bash
./scripts/local_integration_check.sh
```

Or using Task:

```bash
task local-integration
```

### What It Validates

1. **Server startup**: Verifies server starts and writes `runtime.json`
2. **Runtime autodiscovery**: CLI finds server URL from `runtime.json`
3. **Job queue**: Indexing job completes without 409/500 errors
4. **Query**: Returns valid HTTP 200 response
5. **CLI commands**: `agent-brain jobs` works correctly

### Expected Output

```
=== Agent Brain Local Integration Check ===
Step 1: Cleaning up stray processes...
Step 2: Cleaning up old state...
Step 3: Starting server in foreground...
Step 4: Checking runtime.json...
  Found runtime.json
  Server URL: http://127.0.0.1:49321
Step 5: Waiting for health endpoint...
  Server is healthy!
...
=== Integration Check PASSED ===
```

### Troubleshooting Failed Checks

If the check fails:

1. **runtime.json not found**: Server failed to start - check for port conflicts
2. **Job failed**: Check server logs in `.agent-brain/logs/`
3. **Query failed**: Index may be empty - verify test data was created

---

## Troubleshooting

### Server Not Running

```
/agent-brain-status
```

If not running:
```
/agent-brain-start
```

### No Results Found

1. Check document count: `/agent-brain-status`
2. If 0 documents, re-index: `/agent-brain-index ./docs`
3. Try lowering threshold: `/agent-brain-search "term" --threshold 0.3`
4. Try different search mode: `/agent-brain-keyword "exact term"`

### Configuration Issues

```
/agent-brain-verify
```

This checks:
- Package installation
- API key configuration
- Server connectivity
- Provider setup

### Provider Errors

```
/agent-brain-providers
```

Verify your API keys are set correctly for the selected provider.

### Reset Everything

```
/agent-brain-reset
/agent-brain-init
/agent-brain-start
/agent-brain-index . --include-code
```

---

## Next Steps

- [Quick Start](QUICK_START.md) - Get running in minutes
- [Plugin Guide](PLUGIN_GUIDE.md) - All 30 commands in detail
- [API Reference](API_REFERENCE.md) - REST API documentation
- [GraphRAG Guide](GRAPHRAG_GUIDE.md) - Knowledge graph features
- [Provider Configuration](../agent-brain-plugin/skills/using-agent-brain/references/provider-configuration.md) - Provider setup
