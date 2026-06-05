# Phase 34: Spec vs Command Drift Checklist

**Audited:** 2026-03-22
**Spec:** .planning/phases/34-config-command-spec/SPEC.md
**Command:** agent-brain-plugin/commands/agent-brain-config.md
**Script:** agent-brain-plugin/scripts/ab-setup-check.sh

---

## Step-by-Step Verification

### Step 1: Detect Config File Location

- [x] Config search order matches (6 locations):
  1. `AGENT_BRAIN_CONFIG` env var
  2. `$AGENT_BRAIN_STATE_DIR/config.yaml`
  3. `./config.yaml`
  4. `.agent-brain/config.yaml` or `.claude/agent-brain/config.yaml` (walk up from CWD)
  5. `~/.config/agent-brain/config.yaml` (XDG preferred)
  6. `~/.agent-brain/config.yaml` (legacy, deprecated)
- [x] CLI commands shown: `agent-brain config path`, `agent-brain config show`
- [x] Command includes note about editing the file reported by `agent-brain config path`

**Status: PASS**

Note: The command correctly lists all 6 config search locations in order, shows both CLI
commands, and adds a helpful note: "Project-level takes precedence over user-level."

---

### Step 2: Pre-Flight Detection

- [x] Script name: `ab-setup-check.sh`
- [x] Script search uses multi-path find: `~/.claude/plugins/agent-brain/scripts`, `~/.claude/skills/agent-brain/scripts`, `agent-brain-plugin/scripts`
- [x] Output keys documented match script output (see Output Key Verification table below)
- [x] Fallback documented for missing script: `SETUP_STATE="{}"` and manual curl/lsof/ollama fallback
- [x] Parsed output variables: `OLLAMA_RUNNING`, `CONFIG_FILE`, `DOCKER_AVAILABLE`, `AVAILABLE_PORT`

**Status: PASS**

Note: Command implements the script invocation pattern correctly and parses four key output
variables. The fallback (details tag with manual curl commands) is present.

---

### Step 3: Provider Selection

- [x] 5 options match:
  1. Ollama (Local) — nomic-embed-text + llama3.2
  2. OpenAI + Anthropic — text-embedding-3-large + claude-haiku
  3. Google Gemini — text-embedding-004 + gemini-2.0-flash
  4. Custom Mix — user-chosen
  5. Ollama + Mistral — nomic-embed-text + mistral-small3.2
- [x] Config keys: `embedding.provider`, `embedding.model`, `embedding.base_url`, `embedding.api_key`
- [x] Config keys: `summarization.provider`, `summarization.model`, `summarization.base_url`, `summarization.api_key`
- [x] Env vars: `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`, `SUMMARIZATION_PROVIDER`, `SUMMARIZATION_MODEL`

**Status: PASS**

Note: All 5 provider options appear in the AskUserQuestion block with matching descriptions.
Config keys and env vars match the SPEC exactly.

---

### Step 4: Provider Setup Instructions

- [x] Ollama install/pull commands present (brew, curl, Windows download)
- [x] `ollama serve` start command present
- [x] Model pull commands present (`ollama pull nomic-embed-text`, `ollama pull llama3.2`)
- [x] Cloud provider API key instructions present (OpenAI, Anthropic, Gemini with links)
- [x] Error states: Ollama not installed → install instructions
- [x] Error states: Ollama not running → `ollama serve`
- [x] Error states: Missing API key → export command shown in Error Handling section
- [x] Ollama `batch_size`/`delay` tuning present (Step 4, Ollama Option 1, item 5)

**Status: PASS**

Note: All four provider-specific instruction blocks are present. The Ollama performance tuning
(`EMBEDDING_BATCH_SIZE=10`, `OLLAMA_REQUEST_DELAY_MS=0`) is documented in the Ollama setup
block with a clear note that it applies only when embedding provider is Ollama.

---

### Step 5: Storage Backend

- [x] 2 options: ChromaDB (Default), PostgreSQL + pgvector
- [x] Port auto-discovery (5432-5442) — scan loop with lsof present
- [x] Full postgres config block documented (host, port, database, user, password, pool_size,
      pool_max_overflow, language, hnsw_m, hnsw_ef_construction, debug)
- [x] Resolution order documented: `AGENT_BRAIN_STORAGE_BACKEND` env > `storage.backend` YAML > default `"chroma"`
- [x] Note that DATABASE_URL overrides only connection string, not pool/HNSW tuning

**Status: PASS**

Note: The command includes the exact port-scan bash loop from the SPEC, uses `<DISCOVERED_PORT>`
placeholder in the YAML example, and explicitly notes no automatic migration between backends.

---

### Step 6: Indexing Excludes

- [x] 3 options: Use defaults, Add custom exclude patterns, Skip
- [x] Default patterns listed (11 patterns): node_modules, .venv, venv, __pycache__, .git, dist,
      build, target, .next, .nuxt, coverage
- [x] `large_dirs` from pre-flight used to suggest excludes
- [x] Custom excludes written to `.agent-brain/config.json` (via jq `exclude_patterns +=`)

**Status: PASS**

Note: The command shows the large-dir scan output from Step 2, lists all 11 default exclude
patterns in a table with descriptions, and provides the jq command for custom patterns.

---

### Step 7: GraphRAG Configuration

- [x] 4 options: Disabled, AST + LangExtract, Kuzu + AST + LangExtract, AST only
- [x] Extraction mode integrated into the main 4-option question (no separate sub-question)
- [x] Config keys: `graphrag.enabled`, `graphrag.store_type`, `graphrag.use_code_metadata`,
      `graphrag.doc_extractor`
- [x] Env vars: `ENABLE_GRAPH_INDEX`, `GRAPH_STORE_TYPE`, `GRAPH_USE_CODE_METADATA`,
      `GRAPH_DOC_EXTRACTOR`
- [x] Kuzu install instructions present (`poetry install --extras graphrag-kuzu` and `uv pip install kuzu`)
- [x] langextract install implicit via graphrag-kuzu extras (same as kuzu path)
- [x] Optional tuning sub-question for Options 2 & 3 (traversal_depth, max_triplets_per_chunk)

**Status: PASS**

Note: The 4-option combined question is implemented correctly. Option descriptions in the command
use slightly different phrasing from SPEC (e.g., "AST for code + LangExtract for docs" vs "AST +
LangExtract") but convey the same meaning. The doc_extractor config key replaces the legacy
use_llm_extraction key — this was a Phase 34 decision captured in STATE.md.

---

### Step 8: Caching Configuration

- [x] Embedding cache: 3 options (Use defaults, Customize, Disable)
- [x] Default values documented: 500 MB disk, 1000 in-memory entries
- [x] Query cache: 3 options (Use defaults, Customize, Disable)
- [x] Default values documented: 300s TTL, 256 max results
- [x] Config keys: `cache.embedding_max_disk_mb`, `cache.embedding_max_mem_entries`,
      `cache.query_cache_ttl`, `cache.query_cache_max_size`
- [x] Env vars: `EMBEDDING_CACHE_MAX_DISK_MB`, `EMBEDDING_CACHE_MAX_MEM_ENTRIES`,
      `QUERY_CACHE_TTL`, `QUERY_CACHE_MAX_SIZE`
- [x] Disable path documented (EMBEDDING_CACHE_MAX_DISK_MB=0, QUERY_CACHE_TTL=0)

**Status: PASS**

Note: Both embedding and query cache AskUserQuestion blocks are present with all 3 options
each. Config YAML and env var equivalents match the SPEC exactly.

---

### Step 9: File Watcher Configuration

- [x] 2 options: Disabled (Default), Enabled
- [x] Global debounce env var documented: `AGENT_BRAIN_WATCH_DEBOUNCE_SECONDS`
- [x] Default debounce: 30s, valid range 5–300s (range mentioned in ask prompt)
- [x] Per-folder watch documented: `agent-brain folders add ./src --watch auto --debounce 10`
- [x] Noted as env-only (not in config.yaml): explicit note in command
- [x] Job source marker (`source="auto"`) documented in key facts table
- [x] Dedup key (`dedupe_key`) documented in key facts table
- [x] Step completion output block matches SPEC format

**Status: PASS**

Note: Step 9 is fully implemented in the command. The key facts table in the command contains
all 7 items from the SPEC (global debounce, per-folder watch, per-folder debounce, storage,
enable per folder, job source marker, deduplication). The step completion output matches the
SPEC example exactly.

---

### Step 10: Reranking Configuration

- [x] 3 options: Disabled (Default), sentence-transformers, Ollama
- [x] Config keys: `reranker.provider`, `reranker.model`
- [x] Env vars: `ENABLE_RERANKING`, `RERANKER_PROVIDER`, `RERANKER_MODEL`
- [x] Advanced tuning documented: `RERANKER_TOP_K_MULTIPLIER=10`, `RERANKER_MAX_CANDIDATES=100`
- [x] sentence-transformers install note present (auto-downloads ~90 MB)
- [x] Ollama reranking config block present (`base_url` in config.yaml)

**Status: PASS**

Note: All 3 options present. Advanced tuning env vars are labeled "rarely needed" and
documented under the Option 2 block. The Ollama reranker config uses `base_url` in YAML,
which is consistent with how the Ollama embedding provider is configured.

---

### Step 11: Chunking & Search Tuning

- [x] Options: Use defaults or Customize (plus Skip option)
- [x] Env vars: `DEFAULT_CHUNK_SIZE` (default 512, range 128–2048)
- [x] Env vars: `DEFAULT_CHUNK_OVERLAP` (default 50)
- [x] Env vars: `DEFAULT_TOP_K` (default 5)
- [x] Env vars: `DEFAULT_SIMILARITY_THRESHOLD` (default 0.7)
- [x] Content type guidance present:
  - Source code: 256–512
  - Prose/docs: 512–1024
  - Long-form books: 1024–2048
- [x] Noted as env-only (not in config.yaml): "Config YAML (no `chunking` block — these are env-var only settings)"

**Status: PASS**

Note: All 4 env vars are documented with defaults and explanations. The content type guidance
table appears in the chunk-size section. The command explicitly states these settings are
env-var only (no config.yaml block).

---

### Step 12: Server & Deployment Configuration

- [x] 3 options: Local (Default), Network, Custom port
- [x] Port auto-discovery (8000-8300) — scan loop with lsof present
- [x] Auto-discovered port used as default in prompt
- [x] Security warning for 0.0.0.0 documented (reverse proxy + auth required)
- [x] Multi-instance mode documented: `AGENT_BRAIN_MODE=project` or `shared`
- [x] Env vars: `API_HOST`, `API_PORT`, `AGENT_BRAIN_MODE`, `AGENT_BRAIN_STATE_DIR`, `DEBUG`
- [x] Debug mode documented

**Status: PASS**

Note: The port auto-discovery bash loop (8000-8300) is present and used as the default
suggestion. The network binding security warning is clearly labeled "WARNING". The
`AGENT_BRAIN_STATE_DIR` env var is documented in the multi-instance section.

---

## ab-setup-check.sh Output Key Verification

| Script Output Key | Used In Step | Documented in SPEC |
|---|---|---|
| `agent_brain_installed` | Step 2 | Yes |
| `agent_brain_version` | Step 2 | Yes |
| `config_file_found` | Step 1 | Yes |
| `config_file_path` | Step 1 | Yes |
| `ollama_running` | Step 3/4 | Yes |
| `ollama_models` | Step 3/4 | Yes |
| `docker_available` | Step 5 | Yes |
| `docker_compose_available` | Step 5 | Yes |
| `python_version` | Step 2 | Yes |
| `api_keys.openai` | Step 3 | Yes |
| `api_keys.anthropic` | Step 3 | Yes |
| `api_keys.google` | Step 3 | Yes |
| `available_postgres_port` | Step 5 | Yes |
| `large_dirs` | Step 6 | Yes |

**Script vs SPEC alignment notes:**
- All 14 output keys produced by `ab-setup-check.sh` are documented in the SPEC
- The script outputs `available_postgres_port` as a string (not int) due to the bash `cat` JSON
  construction. The SPEC lists the type as `int`. This is a cosmetic type mismatch in JSON only;
  the command reads it with `python3 -c` and treats it as a string anyway — no functional impact.
- The command parses `AVAILABLE_PORT` (for PostgreSQL) from `available_postgres_port` — correct.
- The `api_keys` object (`{"openai": bool, "anthropic": bool, "google": bool}`) matches exactly.

---

## Error States Coverage

| Condition | In SPEC | In Command |
|---|---|---|
| Ollama not installed | Yes | Yes |
| Ollama not running | Yes | Yes |
| Missing API key | Yes | Yes |
| kuzu not installed | Yes | Yes |
| langextract not installed | Yes | Yes (via graphrag-kuzu extras) |
| No free PostgreSQL port | Yes | Yes |
| ab-setup-check.sh not found | Yes | Yes |

**Notes:**
- Ollama not installed: Both SPEC and command show platform-specific install commands (brew, curl, Windows)
- Ollama not running: Command shows `ollama serve` in both Step 4 and the Error Handling section
- Missing API key: Command shows export commands for OpenAI, Anthropic, Google, and xAI in the Error Handling section
- kuzu not installed: Command shows `poetry install --extras graphrag-kuzu` and `uv pip install kuzu`
- langextract not installed: Handled via the same graphrag-kuzu extras path; `poetry install --extras graphrag` also noted
- No free PostgreSQL port: Command shows `exit 1` with manual config instructions
- ab-setup-check.sh not found: Command shows `SETUP_STATE="{}"` fallback with manual curl/lsof steps

---

## Summary

- **Total steps:** 12
- **Steps aligned:** 12/12
- **Drift items fixed in Plan 01:**
  - SPEC title referenced "9-step wizard" (stale); corrected to 12-step wizard in SPEC and downstream docs
  - GraphRAG extraction mode integrated into 4-option combined question (eliminated separate sub-question)
  - `doc_extractor` key replaces legacy `use_llm_extraction` in Step 7 config YAML
  - Step 9 (File Watcher) verified present and complete in command (was flagged as potentially incomplete)
  - Step 12 port auto-discovery (8000-8300) verified implemented in command
- **Remaining issues:** None — all 12 steps pass spec-command alignment verification
- **Minor cosmetic note:** `available_postgres_port` is output as a JSON string by the shell script
  (not int as SPEC documents), but this has no functional impact since the command reads it via python3.
