---
name: agent-brain-config
description: 12-step wizard to configure all Agent Brain settings — providers, storage, GraphRAG, reranking, caching, file watcher, chunking, and server deployment
parameters: []
context: fork
agent: setup-assistant
skills:
  - configuring-agent-brain
last_validated: 2026-03-16
---

# Configure Agent Brain

## Purpose

Guides users through configuring all aspects of Agent Brain across 12 wizard steps:
1. **Providers** - Ollama (local/free) or cloud providers (OpenAI, Anthropic, Gemini)
2. **Storage backend** - ChromaDB (local-first) or PostgreSQL + pgvector
3. **Indexing excludes** - Detect and exclude large directories (node_modules, .venv, etc.)
4. **GraphRAG** - Knowledge graph extraction and indexing (AST, LangExtract, or Kuzu)
5. **Caching** - Embedding cache and query result cache configuration
6. **File watcher** - Automatic re-indexing when files change
7. **Reranking** - Two-stage search quality with cross-encoder reranking
8. **Chunking and search tuning** - Chunk size, overlap, top-k, and similarity threshold
9. **Server and deployment** - Host, port, instance mode, and multi-project setup

## Usage

```
/agent-brain:agent-brain-config
```

## Execution

### Step 1: Detect Config File Location

**IMPORTANT: Check BOTH locations and edit the correct one.**

Config file search order (highest to lowest):
1. **AGENT_BRAIN_CONFIG** environment variable
2. **State directory**: `AGENT_BRAIN_STATE_DIR/config.yaml`
3. **Current directory**: `./config.yaml`
4. **Project-level** (walk up from CWD): `.agent-brain/config.yaml` or `.claude/agent-brain/config.yaml`
5. **XDG config** (preferred user-level): `~/.config/agent-brain/config.yaml`
6. **Legacy user-level** (deprecated): `~/.agent-brain/config.yaml`

Use `agent-brain config path` to see which file is active.

```bash
# Check which config file is active
agent-brain config path

# Show the full active configuration
agent-brain config show
```

**When editing config: Use the file reported by `agent-brain config path`. Project-level takes precedence over user-level.**

### Step 2: Run Pre-Flight Detection

Run the environment detection script once. It consolidates Ollama check, Docker check, large-dir scan, and config detection into a single call:

```bash
# Find the script — adjust path if plugin is installed to ~/.claude/plugins/
SCRIPT=$(find ~/.claude/plugins/agent-brain/scripts ~/.claude/skills/agent-brain/scripts agent-brain-plugin/scripts -name "ab-setup-check.sh" 2>/dev/null | head -1)
if [ -n "$SCRIPT" ]; then
  SETUP_STATE=$("$SCRIPT")
  echo "$SETUP_STATE"
else
  echo "ab-setup-check.sh not found — run detection manually (see fallback below)"
  SETUP_STATE="{}"
fi
```

Parse the JSON output into local variables for use in subsequent steps:

```bash
OLLAMA_RUNNING=$(echo "$SETUP_STATE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('ollama_running','false'))" 2>/dev/null || echo "false")
CONFIG_FILE=$(echo "$SETUP_STATE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('config_file_path',''))" 2>/dev/null || echo "")
DOCKER_AVAILABLE=$(echo "$SETUP_STATE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('docker_available','false'))" 2>/dev/null || echo "false")
AVAILABLE_PORT=$(echo "$SETUP_STATE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('available_postgres_port','5432'))" 2>/dev/null || echo "5432")
```

**Interpreting results:**
- `ollama_running: true` → Ollama IS running; proceed with configuration
- `ollama_running: false` → Tell user to start Ollama: `ollama serve`
- `docker_available: true` → Docker is installed; PostgreSQL setup is possible
- `config_file_path: "..."` → Edit THAT config file (project-level takes priority)

**Fallback (if ab-setup-check.sh not found):** Use the manual methods below — but `ab-setup-check.sh` should always be present if the plugin is installed.

<details>
<summary>Manual fallback (not needed when plugin is installed)</summary>

```bash
# Manual Ollama check
curl -s --connect-timeout 3 http://localhost:11434/ 2>/dev/null
lsof -i :11434 2>/dev/null | head -3
ollama list 2>/dev/null | head -10
```

</details>

### Step 3: Use AskUserQuestion for Provider Selection

```
Which provider setup would you like for Agent Brain?

Options:
1. Ollama (Local) - FREE, no API keys required. Uses nomic-embed-text + llama3.2
2. OpenAI + Anthropic - Best quality cloud providers. Requires OPENAI_API_KEY and ANTHROPIC_API_KEY
3. Google Gemini - Google's models. Requires GOOGLE_API_KEY
4. Custom Mix - Choose different providers for embedding vs summarization
5. Ollama + Mistral - FREE, uses nomic-embed-text + mistral-small3.2 (better summarization)
```

### Step 4: Based on Selection

**For Ollama (Option 1):**

```
=== Ollama Setup (Local, Free) ===

Ollama runs locally - no API keys or cloud costs!

1. Install Ollama (if not installed):

   macOS:   brew install ollama
   Linux:   curl -fsSL https://ollama.com/install.sh | sh
   Windows: Download from https://ollama.com/download

2. Start Ollama server:
   ollama serve

3. Pull required models:
   ollama pull nomic-embed-text      # For embeddings (8192 token context)
   ollama pull llama3.2              # For summarization

   IMPORTANT: Use nomic-embed-text (NOT mxbai-embed-large)
   - nomic-embed-text: 8192 token context - handles large documents
   - mxbai-embed-large: only 512 token context - causes indexing errors

4. Create config file (~/.agent-brain/config.yaml):

   mkdir -p ~/.agent-brain
   cat > ~/.agent-brain/config.yaml << 'EOF'
   embedding:
     provider: "ollama"
     model: "nomic-embed-text"
     base_url: "http://localhost:11434/v1"

   summarization:
     provider: "ollama"
     model: "llama3.2"
     base_url: "http://localhost:11434/v1"
   EOF

   OR use environment variables:
   export EMBEDDING_PROVIDER=ollama
   export EMBEDDING_MODEL=nomic-embed-text
   export SUMMARIZATION_PROVIDER=ollama
   export SUMMARIZATION_MODEL=llama3.2

5. Ollama performance tuning (optional — only relevant when embedding provider is Ollama):

   EMBEDDING_BATCH_SIZE=10       # default batch size; reduce if Ollama runs out of memory
   OLLAMA_REQUEST_DELAY_MS=0     # add delay (ms) between batches if Ollama is overwhelmed

   These can be added to .env in the agent-brain-server directory or set as env vars.

6. Start Agent Brain:
   /agent-brain:agent-brain-start

No API keys needed!
```

**For OpenAI + Anthropic (Option 2):**

```
=== Cloud Provider Setup ===

1. Get API keys:
   - OpenAI: https://platform.openai.com/account/api-keys
   - Anthropic: https://console.anthropic.com/

2. Create config file (~/.agent-brain/config.yaml):

   mkdir -p ~/.agent-brain
   cat > ~/.agent-brain/config.yaml << 'EOF'
   embedding:
     provider: "openai"
     model: "text-embedding-3-large"
     api_key: "sk-proj-YOUR-KEY-HERE"

   summarization:
     provider: "anthropic"
     model: "claude-haiku-4-5-20251001"
     api_key: "sk-ant-YOUR-KEY-HERE"
   EOF

   chmod 600 ~/.agent-brain/config.yaml  # Secure the file

   OR use environment variables:
   export OPENAI_API_KEY="sk-proj-..."
   export ANTHROPIC_API_KEY="sk-ant-..."

3. Start Agent Brain:
   /agent-brain:agent-brain-start
```

**For Gemini (Option 3):**

```
=== Google Gemini Setup ===

1. Get key: https://aistudio.google.com/apikey
2. Set: export GOOGLE_API_KEY="AIza..."

Create config file (~/.agent-brain/config.yaml):

  mkdir -p ~/.agent-brain
  cat > ~/.agent-brain/config.yaml << 'EOF'
  embedding:
    provider: "gemini"
    model: "text-embedding-004"
    api_key: "AIza..."

  summarization:
    provider: "gemini"
    model: "gemini-2.0-flash"
    api_key: "AIza..."
  EOF

  chmod 600 ~/.agent-brain/config.yaml  # Secure the file

OR use environment variables:
export EMBEDDING_PROVIDER=gemini
export EMBEDDING_MODEL=text-embedding-004
export SUMMARIZATION_PROVIDER=gemini
export SUMMARIZATION_MODEL=gemini-2.0-flash
export GOOGLE_API_KEY="AIza..."
```

**For Custom Mix (Option 4):**

Redirect to: `/agent-brain:agent-brain-providers switch`

**For Ollama + Mistral (Option 5):**

```
=== Ollama + Mistral Setup (Local, Free) ===

Uses Mistral's small model for better summarization quality.

1. Ensure Ollama is running:
   ollama serve

2. Pull required models:
   ollama pull nomic-embed-text           # For embeddings (8192 token context)
   ollama pull mistral-small3.2:latest    # For summarization (better quality)

3. Create config file (~/.agent-brain/config.yaml):

   mkdir -p ~/.agent-brain
   cat > ~/.agent-brain/config.yaml << 'EOF'
   embedding:
     provider: "ollama"
     model: "nomic-embed-text"
     base_url: "http://localhost:11434/v1"

   summarization:
     provider: "ollama"
     model: "mistral-small3.2:latest"
     base_url: "http://localhost:11434/v1"
   EOF

   OR use environment variables:
   export EMBEDDING_PROVIDER=ollama
   export EMBEDDING_MODEL=nomic-embed-text
   export SUMMARIZATION_PROVIDER=ollama
   export SUMMARIZATION_MODEL=mistral-small3.2:latest

4. Start Agent Brain:
   /agent-brain:agent-brain-start

No API keys needed! Mistral-small3.2 provides better summarization than llama3.2.
```

## Output

### Initial Status Display

```
Agent Brain Configuration
=========================

Current Configuration:
  Embedding:      ollama / nomic-embed-text
  Summarization:  ollama / llama3.2

Provider Options:
-----------------

1. OLLAMA (Local, Free)
   - No API keys required
   - Runs on your machine
   - Models: nomic-embed-text, llama3.2
   - Setup: ollama serve

2. OPENAI + ANTHROPIC (Cloud)
   - Best quality embeddings and summaries
   - Requires: OPENAI_API_KEY, ANTHROPIC_API_KEY
   - Models: text-embedding-3-large, claude-haiku

3. GOOGLE GEMINI (Cloud)
   - Google's models
   - Requires: GOOGLE_API_KEY
   - Models: text-embedding-004, gemini-2.0-flash

4. CUSTOM MIX
   - Choose different providers for each function
   - Run: /agent-brain:agent-brain-providers switch

5. OLLAMA + MISTRAL (Local, Free)
   - Better summarization than llama3.2
   - Models: nomic-embed-text, mistral-small3.2

Which setup would you like? (Enter 1-5)
```

### Ollama Setup Complete

```
Ollama Configuration Complete!
==============================

Config file created: ~/.agent-brain/config.yaml

  embedding:
    provider: "ollama"
    model: "nomic-embed-text"
    base_url: "http://localhost:11434/v1"

  summarization:
    provider: "ollama"
    model: "llama3.2"
    base_url: "http://localhost:11434/v1"

(Or if using environment variables):
  EMBEDDING_PROVIDER=ollama
  EMBEDDING_MODEL=nomic-embed-text
  SUMMARIZATION_PROVIDER=ollama
  SUMMARIZATION_MODEL=llama3.2

Next steps:
1. Ensure Ollama is running: ollama serve
2. Initialize project: /agent-brain:agent-brain-init
3. Start server: /agent-brain:agent-brain-start
```

**Note:** Configuration is loaded once at server startup. After changing
`config.yaml` or environment variables, restart the server for changes to
take effect:

```
agent-brain stop && agent-brain start
```

## Error Handling

### Ollama Not Installed

```
Ollama not found. Install with:

macOS:   brew install ollama
Linux:   curl -fsSL https://ollama.com/install.sh | sh
Windows: https://ollama.com/download
```

### Ollama Not Running

```
Ollama is installed but not running.

Start it with: ollama serve

Then pull models:
  ollama pull nomic-embed-text
  ollama pull llama3.2
```

### Missing API Key for Cloud Provider

```
Cloud provider selected but API key not set.

For OpenAI:    export OPENAI_API_KEY="sk-proj-..."
For Anthropic: export ANTHROPIC_API_KEY="sk-ant-..."
For Google:    export GOOGLE_API_KEY="AIza..."
For xAI:       export XAI_API_KEY="xai-..."
```

## Security Guidance

**For cloud providers:**
- Never commit API keys to version control
- Add `config.yaml` and `.env` files to `.gitignore`
- If storing API keys in config files, restrict permissions:
  ```bash
  chmod 600 ~/.agent-brain/config.yaml
  ```
- Use `api_key_env` in config to read from env vars instead of storing directly

**For Ollama:**
- Runs locally - no keys to manage
- Data stays on your machine

## Step 5: Select Storage Backend (ChromaDB or PostgreSQL)

After provider configuration, confirm which storage backend to use for indexing and search.

### AskUserQuestion: Storage Backend Selection

```
Which storage backend would you like to use?

Options:
1. ChromaDB (Default) - Local-first, zero ops, best for small to medium projects
2. PostgreSQL + pgvector - Best for larger datasets, requires a running database
```

### Backend Resolution Order

Agent Brain resolves the storage backend in this order:
1. `AGENT_BRAIN_STORAGE_BACKEND` environment variable (highest priority)
2. `storage.backend` in config.yaml
3. Default: `chroma`

### PostgreSQL Port Auto-Discovery

When the user selects PostgreSQL, automatically find an available port before writing config:

```bash
# Scan for a free port in the PostgreSQL range
POSTGRES_PORT=""
for port in $(seq 5432 5442); do
  if ! lsof -i :$port -sTCP:LISTEN >/dev/null 2>&1; then
    POSTGRES_PORT=$port
    echo "Found available port: $port"
    break
  else
    echo "Port $port in use, trying next..."
  fi
done

if [ -z "$POSTGRES_PORT" ]; then
  echo "ERROR: No available ports in range 5432-5442"
  echo "Free a port or configure storage.postgres.port manually."
  exit 1
fi
echo "PostgreSQL will use port: $POSTGRES_PORT"
```

Use this discovered port in BOTH the Docker Compose command AND config.yaml.

### YAML Configuration (PostgreSQL Example)

If the user selects PostgreSQL, add the `storage.backend` selection plus a full `storage.postgres` block.
**Use the auto-discovered port from the scan above** (not a hardcoded 5432):

```yaml
storage:
  backend: "postgres"  # or "chroma"
  postgres:
    host: "localhost"
    port: <DISCOVERED_PORT>  # e.g., 5433 if 5432 was in use
    database: "agent_brain"
    user: "agent_brain"
    password: "agent_brain_dev"
    pool_size: 10
    pool_max_overflow: 10
    language: "english"
    hnsw_m: 16
    hnsw_ef_construction: 64
    debug: false
```

Start the PostgreSQL container on the same discovered port:

```bash
POSTGRES_PORT=$POSTGRES_PORT docker compose -f <plugin_path>/templates/docker-compose.postgres.yml up -d
```

**Important notes:**
- `DATABASE_URL` overrides only the PostgreSQL connection string. Pool sizing and HNSW tuning still come from `storage.postgres`.
- There is no automatic migration between backends. Switching backends requires re-indexing your documents.
- The port auto-discovery ensures no conflicts with existing PostgreSQL instances on the host.

If the user selects ChromaDB, you can omit `storage.postgres` entirely and leave `storage.backend` as `chroma` (or omit it to use the default).

## Step 6: Configure Indexing Excludes

After provider setup, help the user configure which directories to exclude from indexing.

### Detect Large Directories

The pre-flight detection from Step 2 already scanned for large directories. Parse the results:

```bash
echo "$SETUP_STATE" | python3 -c "
import sys, json
d = json.load(sys.stdin)
dirs = d.get('large_dirs', [])
if dirs:
    print('Large directories found — consider excluding these:')
    for entry in dirs:
        print(f'  {entry[\"path\"]}/ - {entry[\"size\"]} ({entry[\"file_count\"]} files) — SHOULD EXCLUDE')
else:
    print('No large directories detected in current directory')
"
```

### Show Current Exclude Patterns

```bash
echo "=== Current Exclude Patterns ==="
if [ -f ".agent-brain/config.json" ]; then
  cat .agent-brain/config.json | grep -A20 '"exclude_patterns"'
else
  echo "Using defaults: node_modules, __pycache__, .venv, venv, .git, dist, build, target"
fi
```

### Ask User About Additional Excludes

Use AskUserQuestion:

```
Based on the scan above, would you like to:

Options:
1. Use defaults (node_modules, .venv, __pycache__, .git, dist, build, target)
2. Add custom exclude patterns
3. Skip - I'll configure manually later
```

**If Option 2 (Custom):**

Ask the user which additional directories to exclude, then update `.agent-brain/config.json`:

```bash
# Example: Add custom exclude pattern
# Read current config, add pattern, write back
cat .agent-brain/config.json | jq '.exclude_patterns += ["**/my-custom-dir/**"]' > /tmp/config.json && mv /tmp/config.json .agent-brain/config.json
```

### Default Exclude Patterns

These are excluded by default (no config needed):

| Pattern | Description |
|---------|-------------|
| `**/node_modules/**` | JavaScript/Node.js dependencies |
| `**/.venv/**` | Python virtual environments |
| `**/venv/**` | Python virtual environments |
| `**/__pycache__/**` | Python bytecode cache |
| `**/.git/**` | Git repository data |
| `**/dist/**` | Build output |
| `**/build/**` | Build output |
| `**/target/**` | Rust/Java build output |
| `**/.next/**` | Next.js build cache |
| `**/.nuxt/**` | Nuxt.js build cache |
| `**/coverage/**` | Test coverage reports |

## Step 7: Configure GraphRAG (Knowledge Graph)

After storage backend selection, ask whether to enable graph indexing.

### AskUserQuestion: GraphRAG Selection

```
Would you like to enable GraphRAG (knowledge graph indexing)?

GraphRAG extracts entity relationships from your documents and code, enabling
graph-based queries like "what classes depend on X?" alongside standard search.

Options:
1. Disabled (Default) - Standard vector + BM25 hybrid search only
2. AST + LangExtract (Recommended for mixed repos) - GraphRAG with JSON persistence,
   AST/code metadata for code chunks, and LangExtract for docs/prose chunks
3. Kuzu + AST + LangExtract - Same extractor behavior with Kuzu persistent graph store
4. AST only - GraphRAG with JSON persistence and AST/code metadata only
```

### Option mapping to config.yaml

The CLI wizard prompt text mirrors the current command implementation:

- `2) AST for code + LangExtract for docs (recommended for mixed repos)`
- `3) Kuzu + AST for code + LangExtract for docs`
- `4) AST for code only`

### If Option 2 (AST + LangExtract, simple JSON persistence):

Add to config.yaml:

```yaml
graphrag:
  enabled: true
  store_type: "simple"
  use_code_metadata: true
  doc_extractor: "langextract"
```

Or via environment variables:
```bash
export ENABLE_GRAPH_INDEX=true
export GRAPH_STORE_TYPE=simple          # JSON persistence, no kuzu needed
export GRAPH_USE_CODE_METADATA=true     # AST-based relationship extraction
export GRAPH_DOC_EXTRACTOR=langextract  # LangExtract for document chunks
```

### If Option 3 (Kuzu + AST + LangExtract):

First check if kuzu is installed:

```bash
python3 -c "import kuzu" 2>/dev/null && echo "kuzu available" || echo "kuzu NOT installed"
```

If not installed:
```
Kuzu requires the optional graphrag-kuzu dependency:
  cd agent-brain-server && poetry install --extras graphrag-kuzu

Or install directly:
  uv pip install kuzu
```

Add to config.yaml:

```yaml
graphrag:
  enabled: true
  store_type: "kuzu"
  use_code_metadata: true
  doc_extractor: "langextract"
```

### If Option 4 (AST only):

```yaml
graphrag:
  enabled: true
  store_type: "simple"
  use_code_metadata: true
```

**Note:** Enabling GraphRAG increases indexing time. Re-index after enabling:
```bash
agent-brain reset --yes && agent-brain index ./your-docs
```

### If Option 2 or 3: AskUserQuestion: GraphRAG Tuning (Optional)

After extraction mode selection, offer tuning:

```
Would you like to tune GraphRAG extraction settings?
(Default values work well for most projects)

Options:
1. Use defaults — traversal_depth=2, max_triplets=10 per chunk
2. Customize — adjust depth and triplet density
```

**If Option 2 (Customize):**

```bash
# Traversal depth: how many hops to follow from a matched entity (default: 2)
# Higher = richer context, slower queries (range: 1-5)
export GRAPH_TRAVERSAL_DEPTH=2

# Max triplets per chunk (default: 10)
# Higher = more relationships extracted, slower indexing
export GRAPH_MAX_TRIPLETS_PER_CHUNK=10
```

Config YAML equivalent:
```yaml
graphrag:
  traversal_depth: 2
  max_triplets_per_chunk: 10
```

## Step 8: Configure Caching

### Embedding Cache

The embedding cache reduces API costs by storing computed embeddings locally (two-tier: in-memory LRU + SQLite disk). Always beneficial for cloud providers; less relevant for Ollama.

### AskUserQuestion: Embedding Cache

```
Configure embedding cache settings?

The embedding cache avoids recomputing embeddings for unchanged content.
Healthy cache shows >80% hit rate after first full index.

Options:
1. Use defaults - 500 MB disk cache, 1000 in-memory entries
2. Customize - Set disk size and memory entries manually
3. Disable - No caching (not recommended for cloud providers)
```

**If Option 2 (Customize):** Ask for disk limit (MB) and memory entries, then add to config.yaml:

```yaml
cache:
  embedding_max_disk_mb: <user_value>     # e.g. 1000
  embedding_max_mem_entries: <user_value> # e.g. 2000
```

Or via environment variables:
```bash
export EMBEDDING_CACHE_MAX_DISK_MB=1000
export EMBEDDING_CACHE_MAX_MEM_ENTRIES=2000
```

**If Option 3 (Disable):**
```bash
export EMBEDDING_CACHE_MAX_DISK_MB=0
```

### Query Cache

The query cache stores identical query results for a TTL window. Graph and multi-mode queries are never cached.

### AskUserQuestion: Query Cache

```
Configure query result cache?

Caches repeated identical queries to reduce latency.
Note: graph and multi-mode queries are never cached.

Options:
1. Use defaults - 300s TTL, 256 max results
2. Customize - Set TTL and max size
3. Disable - TTL=0 (no caching)
```

**If Option 2 (Customize):** Add to config.yaml:

```yaml
cache:
  query_cache_ttl: <seconds>    # e.g. 600 for stable codebases
  query_cache_max_size: <count> # e.g. 512 for large query workloads
```

Or via environment variables:
```bash
export QUERY_CACHE_TTL=600
export QUERY_CACHE_MAX_SIZE=512
```

**If Option 3 (Disable):**
```bash
export QUERY_CACHE_TTL=0
```

## Step 9: Configure File Watcher (Auto-Reindex on Change)

### AskUserQuestion: File Watcher

```
Would you like to enable automatic re-indexing when files change?

Options:
1. Disabled (Default) — Index manually with `agent-brain index`
2. Enabled — Server watches indexed folders and re-indexes changed files
             Debounce: 30s by default (prevents re-index thrashing on rapid saves)
```

### If Option 2 (Enabled):

Ask for global debounce (default 30s, valid range 5–300s):

```
How many seconds should the watcher wait after a file change before re-indexing?
(Default: 30s — prevents re-indexing on every keystroke during active editing)
```

Set the global debounce via environment variable:

```bash
export AGENT_BRAIN_WATCH_DEBOUNCE_SECONDS=30
```

**Key facts about the file watcher:**

| Item | Detail |
|------|--------|
| Global debounce | `AGENT_BRAIN_WATCH_DEBOUNCE_SECONDS` (default 30s) |
| Per-folder watch | Set at index time, not in config.yaml |
| Enable per folder | `agent-brain folders add ./src --watch auto --debounce 10` |
| Disable per folder | `agent-brain folders add ./src --watch off` |
| View watch status | `agent-brain folders list` shows watch_mode per folder |
| Job source | Watcher-triggered jobs appear with `source="auto"` in queue |
| Deduplication | Same path is never double-indexed (dedupe_key prevents this) |

**Note:** `watch_mode` is a per-folder setting configured at index time. The
`AGENT_BRAIN_WATCH_DEBOUNCE_SECONDS` env var sets the global default debounce that
applies when no per-folder override is set.

```
Step 9 Complete: File Watcher
==============================

Global debounce: 30s
  AGENT_BRAIN_WATCH_DEBOUNCE_SECONDS=30

Per-folder watcher is configured at index time:
  agent-brain folders add ./src --watch auto              # use global debounce
  agent-brain folders add ./docs --watch auto --debounce 10  # 10s override

View current watch settings:
  agent-brain folders list

Restart server to apply:
  agent-brain stop && agent-brain start
```

---

## Step 10: Configure Reranking (Two-Stage Search Quality)

Reranking adds a second-pass scoring pass after the initial hybrid search, re-ranking
candidates with a cross-encoder model for higher precision results. It's off by default
because it requires additional model downloads.

### AskUserQuestion: Reranking

```
Would you like to enable two-stage reranking for higher search precision?

Reranking re-scores the top candidates with a cross-encoder model, improving
result quality at the cost of slightly higher query latency.

Options:
1. Disabled (Default) — single-stage hybrid BM25 + vector search
2. Enabled (sentence-transformers) — local cross-encoder, no API key needed
   Requires: pip install sentence-transformers (first run auto-downloads ~90 MB)
3. Enabled (Ollama) — uses Ollama for reranking, requires Ollama running
```

**If Option 2 (sentence-transformers):**

```bash
export ENABLE_RERANKING=true
export RERANKER_PROVIDER=sentence-transformers
export RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2  # default
```

Config YAML (`reranker` block):
```yaml
reranker:
  provider: "sentence-transformers"
  model: "cross-encoder/ms-marco-MiniLM-L-6-v2"
```

**If Option 3 (Ollama):**

```bash
export ENABLE_RERANKING=true
export RERANKER_PROVIDER=ollama
```

Config YAML:
```yaml
reranker:
  provider: "ollama"
  base_url: "http://localhost:11434"
```

**Advanced tuning** (rarely needed):
```bash
# How many candidates Stage 1 retrieves for Stage 2 to rerank (default: top_k × 10)
export RERANKER_TOP_K_MULTIPLIER=10
# Hard cap on Stage 1 candidates (default: 100)
export RERANKER_MAX_CANDIDATES=100
```

---

## Step 11: Chunking & Search Tuning

Default values work well for most projects. Ask only if the user wants to tune
indexing quality or search behavior.

### AskUserQuestion: Tuning

```
Would you like to adjust chunking and search defaults?
(These affect indexing quality and search result count)

Options:
1. Use defaults — chunk_size=512, overlap=50, top_k=5, threshold=0.7
2. Customize — adjust for your content type
3. Skip
```

**If Option 2 (Customize):**

#### Chunk Size

```
What chunk size would you like?

Larger chunks = more context per result but less precise retrieval.
Smaller chunks = more precise but may cut mid-thought.

Recommended by content type:
- Source code:      256–512  (default: 512)
- Prose/docs:       512–1024
- Long-form books:  1024–2048

Enter chunk size (128–2048, default: 512):
```

```bash
export DEFAULT_CHUNK_SIZE=512
export DEFAULT_CHUNK_OVERLAP=50   # tokens of overlap between adjacent chunks
```

#### Search Top-K

```
How many results should queries return by default? (default: 5, max: 50)
```

```bash
export DEFAULT_TOP_K=5
```

#### Similarity Threshold

```
Minimum similarity score to include a result (0.0–1.0, default: 0.7)

Lower = more results but potentially less relevant.
Higher = fewer but more precise results.
```

```bash
export DEFAULT_SIMILARITY_THRESHOLD=0.7
```

Config YAML (no `chunking` block — these are env-var only settings):
```bash
# All chunking/query settings are env-var only (not in config.yaml)
export DEFAULT_CHUNK_SIZE=512
export DEFAULT_CHUNK_OVERLAP=50
export DEFAULT_TOP_K=5
export DEFAULT_SIMILARITY_THRESHOLD=0.7
```

---

## Step 12: Server & Deployment Configuration

### AskUserQuestion: Deployment Mode

```
How will Agent Brain be deployed?

Options:
1. Local (Default) — binds to 127.0.0.1 using an auto-discovered available port
   from 8000-8300
2. Network — binds to 0.0.0.0 or specific IP, accessible from other machines
3. Custom port — same as option 1 but allows overriding the suggested port
```

### Auto-discover available API port before prompting

Before asking for the final API port value, scan 8000-8300 and suggest the first
available port:

```bash
API_PORT=""
for port in $(seq 8000 8300); do
  if ! lsof -i :$port -sTCP:LISTEN >/dev/null 2>&1; then
    API_PORT=$port
    echo "Discovered available API port in 8000-8300 range: $port"
    break
  fi
done

if [ -z "$API_PORT" ]; then
  echo "ERROR: No available API ports in 8000-8300"
  exit 1
fi
```

Prompt with the discovered value as default/suggestion:

```text
API port [<discovered-port>]:
```

### Host and port mapping

**If Option 1 (Local):**

```bash
export API_HOST=127.0.0.1
export API_PORT=<DISCOVERED_PORT>
```

**If Option 2 (Network):**

```bash
# Bind address (default: 127.0.0.1 — localhost only)
# Use 0.0.0.0 to accept connections from any interface
export API_HOST=0.0.0.0

# Port uses discovered default from 8000-8300 unless user overrides
export API_PORT=<DISCOVERED_PORT_OR_OVERRIDE>
```

**If Option 3 (Custom port):**

```bash
export API_HOST=127.0.0.1
export API_PORT=<USER_SELECTED_PORT>
```

**Security note for network deployment:**
```
WARNING: Binding to 0.0.0.0 exposes Agent Brain to your local network.
Agent Brain has no built-in authentication. Use a reverse proxy (nginx, Caddy)
with authentication in front of it for network deployments.
```

### Multi-Instance Mode (Advanced)

If running multiple Agent Brain instances (one per project):

```bash
# "project" (default) — state stored in .agent-brain/ in current directory
# "shared" — state stored in AGENT_BRAIN_STATE_DIR (one shared index)
export AGENT_BRAIN_MODE=project

# Override state directory (overrides project-level .agent-brain/)
# export AGENT_BRAIN_STATE_DIR=/custom/path/to/state
```

### Debug Mode

```bash
# Enable verbose logging (default: false)
# export DEBUG=true
```

---

## Advanced Configuration Reference

Settings not covered by the wizard (rarely need changing):

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `CHROMA_PERSIST_DIR` | `./chroma_db` | ChromaDB storage directory |
| `BM25_INDEX_PATH` | `./bm25_index` | BM25 keyword index directory |
| `COLLECTION_NAME` | `agent_brain_collection` | ChromaDB collection name |
| `EMBEDDING_DIMENSIONS` | `3072` | Vector dimensions (must match model) |
| `EMBEDDING_BATCH_SIZE` | `100` | API batch size for embedding calls |
| `MAX_CHUNK_SIZE` | `2048` | Hard cap on chunk size |
| `MIN_CHUNK_SIZE` | `128` | Minimum chunk size |
| `MAX_TOP_K` | `50` | Maximum results per query |
| `AGENT_BRAIN_MAX_QUEUE` | `100` | Max pending jobs in queue |
| `AGENT_BRAIN_JOB_TIMEOUT` | `7200` | Job timeout in seconds (2 hours) |
| `AGENT_BRAIN_MAX_RETRIES` | `3` | Job retry attempts on failure |
| `AGENT_BRAIN_CHECKPOINT_INTERVAL` | `50` | Progress save interval (files) |
| `EMBEDDING_CACHE_PERSIST_STATS` | `false` | Persist cache hit/miss stats across restarts |
| `AGENT_BRAIN_STRICT_MODE` | `false` | Fail on critical validation errors |
| `GRAPH_EXTRACTION_MODEL` | `claude-haiku-4-5` | LLM model for legacy LLM entity extraction |
| `GRAPH_RRF_K` | `60` | Reciprocal Rank Fusion constant for graph queries |

All settings can be placed in a `.env` file in the server directory or set as environment variables.

---

## CLI Subcommands Reference

The `agent-brain config` group has two subcommands:

| Subcommand | Description |
|------------|-------------|
| `agent-brain config show` | Display active provider configuration (embedding, summarization, reranker) |
| `agent-brain config path` | Show the path to the active config file |

Both support `--json` for machine-readable output.

## Related Commands

- `/agent-brain:agent-brain-embeddings` - Configure embedding provider only
- `/agent-brain:agent-brain-index` - Index documents with current exclude settings
- `/agent-brain:agent-brain-init` - Initialize project (creates .agent-brain/ directory)
