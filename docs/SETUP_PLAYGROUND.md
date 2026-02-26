# Agent Brain Setup Playground

Complete walkthrough of every setup path. Use this to understand the decision tree from install to first query.

---

## Master Flow

```
/agent-brain-install
        |
        v
/agent-brain-config
   |              |
   v              v
 Ollama        Cloud (OpenAI/Anthropic/Gemini)
   |              |
   v              v
Storage Backend Selection
   |              |
   v              v
 ChromaDB      PostgreSQL
   |              |
   v              v
/agent-brain-init
        |
        v
agent-brain start
        |
        v
agent-brain index ./src
        |
        v
agent-brain query "search term"
```

---

## Part 1: Installation Paths

### Path A: Install via uv (Recommended for power users)

```bash
# 1. Install uv if needed
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Get latest version
VERSION=$(curl -sf https://pypi.org/pypi/agent-brain-rag/json | \
  python3 -c "import sys,json; print(json.load(sys.stdin)['info']['version'])")
echo "Latest: $VERSION"

# 3. Install CLI (includes server as dependency)
uv tool install agent-brain-cli==$VERSION

# 4. Verify
agent-brain --version
# Output: agent-brain, version 6.0.2
```

**For PostgreSQL support, add extras:**
```bash
uv tool install agent-brain-cli==$VERSION \
  --with asyncpg \
  --with "sqlalchemy[asyncio]"
```

### Path B: Install via pipx (Recommended for most users)

```bash
# 1. Install pipx if needed
python -m pip install --user pipx && python -m pipx ensurepath

# 2. Install
pipx install agent-brain-cli==$VERSION

# 3. Verify
agent-brain --version
```

### Path C: Install via pip (venv)

```bash
# 1. Create and activate venv
python -m venv .venv
source .venv/bin/activate

# 2. Install both packages
pip install agent-brain-rag==$VERSION agent-brain-cli==$VERSION

# 3. Verify (must activate venv first each time)
agent-brain --version
```

### Path D: Install via conda

```bash
conda create -n agent-brain python=3.12 -y
conda activate agent-brain
pip install agent-brain-rag==$VERSION agent-brain-cli==$VERSION
agent-brain --version
```

---

## Part 2: Provider Configuration Paths

### Decision Matrix

| Embedding | Summarization | API Keys Needed | Cost | Quality | Speed |
|-----------|---------------|-----------------|------|---------|-------|
| Ollama (nomic-embed-text) | Ollama (llama3.2) | None | FREE | Good | Slow |
| Ollama (nomic-embed-text) | Ollama (mistral-small3.2) | None | FREE | Better | Slow |
| OpenAI (text-embedding-3-large) | Anthropic (claude-haiku) | OPENAI + ANTHROPIC | ~$0.01/query | Best | Fast |
| OpenAI (text-embedding-3-large) | Ollama (mistral-small3.2) | OPENAI only | ~$0.005/query | Best embed + Good summary | Mixed |
| Ollama (nomic-embed-text) | Anthropic (claude-haiku) | ANTHROPIC only | ~$0.003/query | Good embed + Best summary | Mixed |

---

### Path 2A: Ollama Embeddings + Ollama Summarization (100% Free)

**Prerequisites:**
```bash
# Install Ollama
brew install ollama          # macOS
# curl -fsSL https://ollama.com/install.sh | sh  # Linux

# Start Ollama
ollama serve                 # keep terminal open

# Pull models
ollama pull nomic-embed-text      # 274 MB - embeddings (8192 token context)
ollama pull llama3.2              # 2 GB - summarization (basic)
```

**Config file** (`.claude/agent-brain/config.yaml`):
```yaml
embedding:
  provider: ollama
  model: nomic-embed-text
  base_url: "http://localhost:11434/v1"

summarization:
  provider: ollama
  model: llama3.2
  base_url: "http://localhost:11434/v1"
```

**Or with better summarization** (mistral-small3.2):
```bash
ollama pull mistral-small3.2:latest    # 15 GB - better quality
```
```yaml
embedding:
  provider: ollama
  model: nomic-embed-text
  base_url: "http://localhost:11434/v1"

summarization:
  provider: ollama
  model: mistral-small3.2:latest
  base_url: "http://localhost:11434/v1"
```

**Trade-offs:**
- Embedding dimension: 768 (vs 3072 for OpenAI)
- Indexing speed: ~2-5x slower (local GPU/CPU)
- Search quality: Good for most codebases
- No API keys, no cost, fully offline

---

### Path 2B: OpenAI Embeddings + Anthropic Haiku Summarization (Best Quality)

**Prerequisites:**
```bash
export OPENAI_API_KEY="sk-proj-..."       # https://platform.openai.com/api-keys
export ANTHROPIC_API_KEY="sk-ant-..."     # https://console.anthropic.com/
```

**Config file** (`.claude/agent-brain/config.yaml`):
```yaml
embedding:
  provider: openai
  model: text-embedding-3-large

summarization:
  provider: anthropic
  model: claude-haiku-4-5-20251001
```

**Trade-offs:**
- Embedding dimension: 3072 (highest quality)
- Indexing speed: Fast (API calls, not local compute)
- Search quality: Best — large embeddings capture more nuance
- Cost: ~$0.13 per 1M tokens embedded, ~$0.25/1M tokens summarized
- Requires internet connection

---

### Path 2C: OpenAI Embeddings + Ollama Summarization (Hybrid)

Best embeddings, free summarization.

**Prerequisites:**
```bash
export OPENAI_API_KEY="sk-proj-..."
ollama pull mistral-small3.2:latest
```

**Config file:**
```yaml
embedding:
  provider: openai
  model: text-embedding-3-large

summarization:
  provider: ollama
  model: mistral-small3.2:latest
  base_url: "http://localhost:11434/v1"
```

**Trade-offs:**
- Best search quality (OpenAI 3072-dim embeddings)
- Free summarization (slower but no cost)
- Only need OPENAI_API_KEY
- Good balance of quality and cost

---

### Path 2D: Ollama Embeddings + Anthropic Haiku Summarization (Hybrid)

Free embeddings, best summaries.

**Prerequisites:**
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
ollama pull nomic-embed-text
```

**Config file:**
```yaml
embedding:
  provider: ollama
  model: nomic-embed-text
  base_url: "http://localhost:11434/v1"

summarization:
  provider: anthropic
  model: claude-haiku-4-5-20251001
```

**Trade-offs:**
- Lower embedding dimension (768) — slightly less precise search
- Best summaries (Haiku excels at code summarization)
- Only need ANTHROPIC_API_KEY
- Good if you value summary quality over search precision

---

## Part 3: Storage Backend Paths

### Decision Matrix

| Feature | ChromaDB | PostgreSQL + pgvector |
|---------|----------|----------------------|
| Setup complexity | None (embedded) | Docker required |
| Scaling | Good to ~100K chunks | Excellent (millions) |
| Full-text search | BM25 (disk-based) | tsvector (GIN index) |
| Vector search | HNSW (in-process) | pgvector HNSW |
| Dependencies | Included | asyncpg + sqlalchemy |
| Best for | Small-medium projects | Large codebases, teams |
| Persistence | Local files | Docker volume |
| Backup | Copy directory | pg_dump |

---

### Path 3A: ChromaDB (Default, Zero Setup)

**Config file** (`.claude/agent-brain/config.yaml`):
```yaml
embedding:
  provider: ollama
  model: nomic-embed-text
  base_url: "http://localhost:11434/v1"

summarization:
  provider: ollama
  model: mistral-small3.2:latest
  base_url: "http://localhost:11434/v1"

# No storage section needed — ChromaDB is the default
# Or explicitly:
# storage:
#   backend: chroma
```

**Full workflow:**
```bash
# 1. Initialize project
cd ~/my-project
agent-brain init

# 2. Create config (providers only, no storage section needed)
cat > .claude/agent-brain/config.yaml << 'EOF'
embedding:
  provider: ollama
  model: nomic-embed-text
  base_url: "http://localhost:11434/v1"

summarization:
  provider: ollama
  model: mistral-small3.2:latest
  base_url: "http://localhost:11434/v1"
EOF

# 3. Start server
agent-brain start

# 4. Verify
agent-brain status
# Output: HEALTHY, Total Chunks: 0, Indexing: Idle

# 5. Index your code
agent-brain index ./src --include-code

# 6. Search
agent-brain query "authentication flow" --mode hybrid
agent-brain query "database connection" --mode bm25
agent-brain query "how does error handling work" --mode vector
```

**Data location:** `.claude/agent-brain/chroma_db/` (auto-created)

---

### Path 3B: PostgreSQL + pgvector (Docker)

**Step 1: Ensure Docker is running**
```bash
docker --version
docker compose version
```

**Step 2: Auto-discover a free port**
```bash
# Port 5432 may already be used by another PostgreSQL instance
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
echo "Will use port: $POSTGRES_PORT"
```

**Step 3: Start PostgreSQL with pgvector**
```bash
# Using the bundled template (POSTGRES_PORT is passed as env var)
POSTGRES_PORT=$POSTGRES_PORT docker compose \
  -f ~/.claude/plugins/agent-brain/templates/docker-compose.postgres.yml up -d

# Wait for health check
sleep 5
docker exec agent-brain-postgres pg_isready -U agent_brain -d agent_brain
# Output: /var/run/postgresql:5432 - accepting connections
```

**Step 4: Initialize and configure**
```bash
cd ~/my-project
agent-brain init
```

Create config with the discovered port:
```yaml
# .claude/agent-brain/config.yaml
embedding:
  provider: ollama
  model: nomic-embed-text
  base_url: "http://localhost:11434/v1"

summarization:
  provider: ollama
  model: mistral-small3.2:latest
  base_url: "http://localhost:11434/v1"

storage:
  backend: postgres
  postgres:
    host: localhost
    port: 5433           # <-- your discovered port
    database: agent_brain
    user: agent_brain
    password: agent_brain_dev
    pool_size: 10
    pool_max_overflow: 10
    language: english
```

**Step 5: Install PostgreSQL extras** (if using uv tool install):
```bash
uv tool install agent-brain-cli==$VERSION \
  --with asyncpg \
  --with "sqlalchemy[asyncio]" \
  --force
```

**Step 6: Start and use**
```bash
agent-brain start
agent-brain status
# Output: HEALTHY, Server Version: 6.0.2

agent-brain index ./src --include-code
agent-brain query "database schema" --mode hybrid
```

**Managing the container:**
```bash
# Stop PostgreSQL
POSTGRES_PORT=$POSTGRES_PORT docker compose \
  -f ~/.claude/plugins/agent-brain/templates/docker-compose.postgres.yml down

# Stop and delete data
POSTGRES_PORT=$POSTGRES_PORT docker compose \
  -f ~/.claude/plugins/agent-brain/templates/docker-compose.postgres.yml down -v

# View logs
docker logs agent-brain-postgres --tail 50
```

---

## Part 4: Complete End-to-End Examples

### Example A: Cheapest (100% Free, Local)

**Ollama + ChromaDB** -- Zero cost, zero API keys

```bash
# Install
uv tool install agent-brain-cli

# Setup Ollama
ollama pull nomic-embed-text
ollama pull mistral-small3.2:latest

# Initialize project
cd ~/my-project
agent-brain init

# Configure
cat > .claude/agent-brain/config.yaml << 'EOF'
embedding:
  provider: ollama
  model: nomic-embed-text
  base_url: "http://localhost:11434/v1"
summarization:
  provider: ollama
  model: mistral-small3.2:latest
  base_url: "http://localhost:11434/v1"
EOF

# Start and index
agent-brain start
agent-brain index ./src --include-code

# Search
agent-brain query "error handling" --mode hybrid
```

---

### Example B: Best Quality (Cloud + PostgreSQL)

**OpenAI + Haiku + PostgreSQL** -- Premium quality, scales to millions of chunks

```bash
# Install with postgres extras
VERSION=6.0.2
uv tool install agent-brain-cli==$VERSION \
  --with asyncpg --with "sqlalchemy[asyncio]"

# Set API keys
export OPENAI_API_KEY="sk-proj-..."
export ANTHROPIC_API_KEY="sk-ant-..."

# Start PostgreSQL (auto-discovers free port)
POSTGRES_PORT=""
for port in $(seq 5432 5442); do
  if ! lsof -i :$port -sTCP:LISTEN >/dev/null 2>&1; then
    POSTGRES_PORT=$port; break
  fi
done
echo "Using port: $POSTGRES_PORT"

POSTGRES_PORT=$POSTGRES_PORT docker compose \
  -f ~/.claude/plugins/agent-brain/templates/docker-compose.postgres.yml up -d

# Initialize project
cd ~/my-project
agent-brain init

# Configure (use the discovered port)
cat > .claude/agent-brain/config.yaml << EOF
embedding:
  provider: openai
  model: text-embedding-3-large
summarization:
  provider: anthropic
  model: claude-haiku-4-5-20251001
storage:
  backend: postgres
  postgres:
    host: localhost
    port: $POSTGRES_PORT
    database: agent_brain
    user: agent_brain
    password: agent_brain_dev
    pool_size: 10
    pool_max_overflow: 10
    language: english
EOF

# Start and index
agent-brain start
agent-brain index ./src --include-code

# Search (all modes work with PostgreSQL)
agent-brain query "authentication" --mode bm25       # tsvector full-text
agent-brain query "how does auth work" --mode vector  # pgvector similarity
agent-brain query "login flow" --mode hybrid          # RRF fusion of both
```

---

### Example C: Budget Hybrid (OpenAI Embed + Ollama Summary + ChromaDB)

**Best search quality, free summarization, simple storage**

```bash
# Install
uv tool install agent-brain-cli

# Set OpenAI key only
export OPENAI_API_KEY="sk-proj-..."

# Setup Ollama for summarization
ollama pull mistral-small3.2:latest

# Initialize
cd ~/my-project
agent-brain init

# Configure
cat > .claude/agent-brain/config.yaml << 'EOF'
embedding:
  provider: openai
  model: text-embedding-3-large
summarization:
  provider: ollama
  model: mistral-small3.2:latest
  base_url: "http://localhost:11434/v1"
EOF

# Start and index
agent-brain start
agent-brain index ./src --include-code
agent-brain query "database migrations" --mode hybrid
```

---

### Example D: Ollama Embed + Haiku Summary + PostgreSQL

**Free embeddings, best summaries, scalable storage**

```bash
# Install with postgres extras
uv tool install agent-brain-cli \
  --with asyncpg --with "sqlalchemy[asyncio]"

# Set Anthropic key only
export ANTHROPIC_API_KEY="sk-ant-..."

# Setup Ollama for embeddings
ollama pull nomic-embed-text

# Start PostgreSQL
POSTGRES_PORT=5433  # or auto-discover
POSTGRES_PORT=$POSTGRES_PORT docker compose \
  -f ~/.claude/plugins/agent-brain/templates/docker-compose.postgres.yml up -d

# Initialize
cd ~/my-project
agent-brain init

# Configure
cat > .claude/agent-brain/config.yaml << 'EOF'
embedding:
  provider: ollama
  model: nomic-embed-text
  base_url: "http://localhost:11434/v1"
summarization:
  provider: anthropic
  model: claude-haiku-4-5-20251001
storage:
  backend: postgres
  postgres:
    host: localhost
    port: 5433
    database: agent_brain
    user: agent_brain
    password: agent_brain_dev
    pool_size: 10
    pool_max_overflow: 10
    language: english
EOF

# Start and index
agent-brain start
agent-brain index ./src --include-code
agent-brain query "API endpoints" --mode hybrid
```

---

## Part 5: Search Modes Reference

All search modes work with both ChromaDB and PostgreSQL backends.

| Mode | Flag | How it works | Best for |
|------|------|-------------|----------|
| **Hybrid** | `--mode hybrid` | RRF fusion of keyword + vector | General purpose (default) |
| **BM25** | `--mode bm25` | Keyword matching (tsvector on PG) | Exact terms, function names |
| **Vector** | `--mode vector` | Semantic similarity (pgvector on PG) | Conceptual questions |
| **Graph** | `--mode graph` | Knowledge graph traversal | Dependencies, relationships |
| **Multi** | `--mode multi` | All modes fused together | Comprehensive search |

```bash
# Examples
agent-brain query "parseConfig" --mode bm25            # exact function name
agent-brain query "how does config loading work" --mode vector  # conceptual
agent-brain query "config" --mode hybrid                # balanced
agent-brain query "what calls parseConfig" --mode graph # relationships
agent-brain query "configuration system" --mode multi   # everything
```

---

## Part 6: Switching Between Configurations

### Switch from ChromaDB to PostgreSQL

```bash
# 1. Stop server
agent-brain stop

# 2. Start PostgreSQL container
POSTGRES_PORT=5433 docker compose \
  -f ~/.claude/plugins/agent-brain/templates/docker-compose.postgres.yml up -d

# 3. Update config.yaml — add storage section
# (edit .claude/agent-brain/config.yaml)

# 4. Install postgres extras if needed
uv tool install agent-brain-cli --with asyncpg --with "sqlalchemy[asyncio]" --force

# 5. Restart and RE-INDEX (no auto-migration)
agent-brain start
agent-brain index ./src --include-code --force
```

### Switch from Ollama to OpenAI embeddings

```bash
# 1. Stop server
agent-brain stop

# 2. Set API key
export OPENAI_API_KEY="sk-proj-..."

# 3. Update config.yaml — change embedding section
# 4. Restart and RE-INDEX (embedding dimensions change: 768 -> 3072)
agent-brain start
agent-brain reset --yes    # clear old embeddings
agent-brain index ./src --include-code
```

**Important:** Switching embedding providers requires re-indexing because embedding dimensions differ (Ollama nomic: 768, OpenAI large: 3072). Switching summarization providers does NOT require re-indexing.

### Switch summarization without re-indexing

```bash
# Just update config.yaml and restart — no re-index needed
agent-brain stop
# (edit config.yaml — change summarization section)
agent-brain start
# New documents will use the new summarizer; existing summaries remain
```

---

## Quick Reference: Config File Location

| Priority | Path | Scope |
|----------|------|-------|
| 1 (highest) | `.claude/agent-brain/config.yaml` | Per-project |
| 2 | `~/.agent-brain/config.yaml` | User-wide |
| 3 | Environment variables | Session |
| 4 | Built-in defaults | Fallback |

Environment variable overrides:
```bash
AGENT_BRAIN_STORAGE_BACKEND=postgres  # Override backend
OPENAI_API_KEY=sk-...                 # API key
ANTHROPIC_API_KEY=sk-...              # API key
EMBEDDING_PROVIDER=ollama             # Override embedding
SUMMARIZATION_PROVIDER=anthropic      # Override summarization
```
