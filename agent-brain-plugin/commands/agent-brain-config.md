---
name: agent-brain-config
description: Configure providers, API keys, and indexing settings for Agent Brain (providers, exclude patterns)
parameters: []
skills:
  - configuring-agent-brain
---

# Configure Agent Brain

## Purpose

Guides users through configuring Agent Brain:
1. **Providers** - Ollama (local/free) or cloud providers (OpenAI, Anthropic, Gemini)
2. **Indexing** - Detect and exclude large directories (node_modules, .venv, etc.)

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
  SETUP_STATE=$(bash "$SCRIPT")
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

5. Start Agent Brain:
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

Configuration (Gemini for both):
export EMBEDDING_PROVIDER=gemini
export EMBEDDING_MODEL=text-embedding-004
export SUMMARIZATION_PROVIDER=gemini
export SUMMARIZATION_MODEL=gemini-2.0-flash
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
