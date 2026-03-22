# Phase 34: Config Command Spec

## Purpose

Formal specification for the `/agent-brain:agent-brain-config` command.

This document is the **source of truth** for the 12-step wizard behavior. The command file
(`agent-brain-plugin/commands/agent-brain-config.md`) is the implementation; this spec is the
contract. Any drift between the two is a bug.

---

## Trigger Conditions

The command is invoked explicitly:
```
/agent-brain:agent-brain-config
```

It is also referenced as a prerequisite from:
- `/agent-brain:agent-brain-setup` (full setup wizard)
- `/agent-brain:agent-brain-install` (post-install config step)

---

## 12-Step Wizard

### Step 1: Detect Config File Location

**Goal:** Identify which config file is active so subsequent steps edit the correct file.

**Action:**
```bash
agent-brain config path
agent-brain config show
```

**Config search order (highest to lowest priority):**
1. `AGENT_BRAIN_CONFIG` env var
2. `$AGENT_BRAIN_STATE_DIR/config.yaml`
3. `./config.yaml`
4. `.agent-brain/config.yaml` or `.claude/agent-brain/config.yaml` (walk up from CWD)
5. `~/.config/agent-brain/config.yaml` (XDG preferred)
6. `~/.agent-brain/config.yaml` (legacy, deprecated)

**Output:** Path to the active config file.

---

### Step 2: Run Pre-Flight Detection

**Goal:** Consolidate environment state into a single JSON blob used by all subsequent steps.

**Action:** Run `ab-setup-check.sh` script from the plugin.

**Output keys:**
| Key | Type | Description |
|-----|------|-------------|
| `agent_brain_installed` | bool | Whether `agent-brain` CLI is installed and on PATH |
| `agent_brain_version` | str | Installed CLI version (empty string if not installed) |
| `config_file_found` | bool | Whether an existing config.yaml was found |
| `config_file_path` | str | Active config file path (empty string if not found) |
| `ollama_running` | bool | Whether Ollama is reachable on localhost:11434 |
| `ollama_models` | list | Array of installed Ollama model names (empty array if none) |
| `docker_available` | bool | Whether Docker CLI is installed |
| `docker_compose_available` | bool | Whether `docker compose` plugin is available |
| `python_version` | str | Python3 version string (e.g. "3.10.14") |
| `api_keys` | obj | Booleans for each key presence: `{"openai": bool, "anthropic": bool, "google": bool}` |
| `available_postgres_port` | int | First free port in 5432-5442 range |
| `large_dirs` | list | Common cache/dependency dirs found in CWD with size and file count |

---

### Step 3: Provider Selection

**Goal:** Choose the embedding + summarization provider stack.

**AskUserQuestion options:**
| # | Name | Providers | Keys Required |
|---|------|-----------|---------------|
| 1 | Ollama (Local) | ollama/nomic-embed-text + ollama/llama3.2 | None |
| 2 | OpenAI + Anthropic | openai/text-embedding-3-large + anthropic/claude-haiku | OPENAI_API_KEY, ANTHROPIC_API_KEY |
| 3 | Google Gemini | gemini/text-embedding-004 + gemini/gemini-2.0-flash | GOOGLE_API_KEY |
| 4 | Custom Mix | User-chosen | Varies |
| 5 | Ollama + Mistral | ollama/nomic-embed-text + ollama/mistral-small3.2 | None |

**Config keys written:**
```yaml
embedding:
  provider: "<provider>"
  model: "<model>"
  base_url: "<url>"   # only for ollama
  api_key: "<key>"    # only for cloud providers

summarization:
  provider: "<provider>"
  model: "<model>"
  base_url: "<url>"   # only for ollama
  api_key: "<key>"    # only for cloud providers
```

**Env var equivalents:**
- `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`
- `SUMMARIZATION_PROVIDER`, `SUMMARIZATION_MODEL`
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`

---

### Step 4: Provider Setup Instructions

**Goal:** Show provider-specific setup instructions based on Step 3 selection.

**Per-option output:** Installation commands, model pull commands, config YAML snippet.

**Error states:**
- Ollama not installed → show install instructions
- Ollama not running → show `ollama serve`
- Missing API key for cloud provider → show export command

---

### Step 5: Storage Backend Selection

**Goal:** Choose ChromaDB or PostgreSQL.

**AskUserQuestion options:**
| # | Backend | Description |
|---|---------|-------------|
| 1 | ChromaDB (Default) | Local-first, zero ops |
| 2 | PostgreSQL + pgvector | Larger datasets, requires database |

**Auto-discovery:** When PostgreSQL selected, scan ports 5432-5442 for first free port.

**Config keys written:**
```yaml
storage:
  backend: "postgres"   # or "chroma"
  postgres:
    host: "localhost"
    port: <DISCOVERED_PORT>
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

**Env var equivalents:**
- `AGENT_BRAIN_STORAGE_BACKEND` — `"chroma"` or `"postgres"`

**Resolution order:** `AGENT_BRAIN_STORAGE_BACKEND` env > `storage.backend` YAML > default `"chroma"`.

---

### Step 6: Indexing Excludes

**Goal:** Configure which directories to skip during indexing.

**Action:** Use large_dirs output from Step 2 pre-flight scan to suggest excludes.

**Default excluded patterns (no config needed):**
`node_modules`, `.venv`, `venv`, `__pycache__`, `.git`, `dist`, `build`, `target`, `.next`, `.nuxt`, `coverage`

**AskUserQuestion options:**
| # | Action |
|---|--------|
| 1 | Use defaults |
| 2 | Add custom exclude patterns |
| 3 | Skip |

**Config keys written (if custom):**
```json
{ "exclude_patterns": ["**/my-custom-dir/**"] }
```
Written to `.agent-brain/config.json`.

---

### Step 7: GraphRAG Configuration

**Goal:** Enable/configure the knowledge graph index.

**AskUserQuestion (GraphRAG enable + extraction mode — combined):**
| # | Option | Description |
|---|--------|-------------|
| 1 | Disabled (Default) | Standard vector + BM25 hybrid search only |
| 2 | AST + LangExtract (Recommended for mixed repos) | GraphRAG with JSON persistence, AST/code metadata for code chunks, LangExtract for docs/prose chunks |
| 3 | Kuzu + AST + LangExtract | Same extractor behavior as option 2 with Kuzu persistent graph store |
| 4 | AST only | GraphRAG with JSON persistence and AST/code metadata only |

**Note:** Extraction mode is integrated into the main question (options 2-4 encode the extractor choice). There is no separate extraction mode sub-question.

**Config keys written (Option 2 — AST + LangExtract, simple JSON):**
```yaml
graphrag:
  enabled: true
  store_type: "simple"
  use_code_metadata: true
  doc_extractor: "langextract"
```

**Config keys written (Option 3 — Kuzu + AST + LangExtract):**
```yaml
graphrag:
  enabled: true
  store_type: "kuzu"
  use_code_metadata: true
  doc_extractor: "langextract"
```

**Config keys written (Option 4 — AST only):**
```yaml
graphrag:
  enabled: true
  store_type: "simple"
  use_code_metadata: true
```

**Env var equivalents:**
- `ENABLE_GRAPH_INDEX=true`
- `GRAPH_STORE_TYPE=simple` or `kuzu`
- `GRAPH_USE_CODE_METADATA=true/false`
- `GRAPH_DOC_EXTRACTOR=langextract` or `none`

---

### Step 8: Caching Configuration

**Goal:** Configure embedding cache and query cache.

**Embedding cache AskUserQuestion:**
| # | Option |
|---|--------|
| 1 | Use defaults (500 MB disk, 1000 in-memory) |
| 2 | Customize |
| 3 | Disable |

**Query cache AskUserQuestion:**
| # | Option |
|---|--------|
| 1 | Use defaults (300s TTL, 256 max results) |
| 2 | Customize |
| 3 | Disable |

**Config keys written:**
```yaml
cache:
  embedding_max_disk_mb: <value>
  embedding_max_mem_entries: <value>
  query_cache_ttl: <seconds>
  query_cache_max_size: <count>
```

**Env var equivalents:**
- `EMBEDDING_CACHE_MAX_DISK_MB`
- `EMBEDDING_CACHE_MAX_MEM_ENTRIES`
- `QUERY_CACHE_TTL`
- `QUERY_CACHE_MAX_SIZE`

---

### Step 9: File Watcher Configuration

**Goal:** Enable automatic re-indexing when files change.

**AskUserQuestion:**
| # | Option |
|---|--------|
| 1 | Disabled (Default) — index manually with `agent-brain index` |
| 2 | Enabled — server watches indexed folders and re-indexes changed files |

**If option 2:**
- Ask for global debounce (default 30s, valid range 5–300s)
- Set env var: `AGENT_BRAIN_WATCH_DEBOUNCE_SECONDS=<seconds>`
- Inform user: per-folder watch control is set at index time, not here

**Key facts:**
| Item | Value |
|------|-------|
| Global debounce env var | `AGENT_BRAIN_WATCH_DEBOUNCE_SECONDS` (default: 30) |
| Per-folder watch mode | `watch_mode`: `"off"` or `"auto"` |
| Per-folder debounce | `watch_debounce_seconds` (falls back to global if unset) |
| Storage | `indexed_folders.jsonl` per-folder entry |
| Enable per folder | `agent-brain folders add ./src --watch auto --debounce 10` |
| Job source marker | `source="auto"` in queue (watcher-triggered) |
| Dedup key | `dedupe_key` prevents double-indexing same path |

**YAML config (no config.yaml key — global debounce is env-only):**
```bash
# Global debounce (env var only, not in config.yaml):
export AGENT_BRAIN_WATCH_DEBOUNCE_SECONDS=30

# Per-folder watch (set at index time, not in config.yaml):
agent-brain folders add ./src --watch auto --debounce 10
agent-brain folders add ./docs --watch auto            # uses global debounce
```

---

### Step 10: Reranking Configuration

**Goal:** Enable/configure two-stage search reranking.

**AskUserQuestion:**
| # | Option |
|---|--------|
| 1 | Disabled (Default) |
| 2 | sentence-transformers (local, no API key) |
| 3 | Ollama |

**Config keys written:**
```yaml
reranker:
  provider: "sentence-transformers"
  model: "cross-encoder/ms-marco-MiniLM-L-6-v2"
```

**Env var equivalents:**
- `ENABLE_RERANKING=true`
- `RERANKER_PROVIDER=sentence-transformers|ollama`
- `RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2`
- `RERANKER_TOP_K_MULTIPLIER=10`
- `RERANKER_MAX_CANDIDATES=100`

---

### Step 11: Chunking & Search Tuning

**Goal:** Tune chunk size, overlap, and query defaults for content type.

**AskUserQuestion:** Use defaults or customize.

**Config keys (env-only, no config.yaml block):**
- `DEFAULT_CHUNK_SIZE` (default 512, range 128–2048)
- `DEFAULT_CHUNK_OVERLAP` (default 50)
- `DEFAULT_TOP_K` (default 5)
- `DEFAULT_SIMILARITY_THRESHOLD` (default 0.7)

**Content type guidance:**
- Source code → 256–512
- Prose/docs → 512–1024
- Long-form → 1024–2048

---

### Step 12: Server & Deployment Configuration

**Goal:** Configure server bind address, port, and instance mode.

**AskUserQuestion:**
| # | Option |
|---|--------|
| 1 | Local (Default) — 127.0.0.1 using auto-discovered port from 8000-8300 |
| 2 | Network — 0.0.0.0 accessible from other machines |
| 3 | Custom port — same as option 1 but allows overriding the suggested port |

**Security warning:** Binding to `0.0.0.0` requires a reverse proxy with auth.

**Config keys (env-only):**
- `API_HOST` (default `127.0.0.1`)
- `API_PORT` (default `8000`)
- `AGENT_BRAIN_MODE` (`project` or `shared`)
- `AGENT_BRAIN_STATE_DIR` (optional state dir override)
- `DEBUG` (default `false`)

---

### Advanced Configuration Reference

Settings rarely changed, listed for completeness:
`CHROMA_PERSIST_DIR`, `BM25_INDEX_PATH`, `COLLECTION_NAME`, `EMBEDDING_DIMENSIONS`,
`EMBEDDING_BATCH_SIZE`, `MAX_CHUNK_SIZE`, `MIN_CHUNK_SIZE`, `MAX_TOP_K`,
`AGENT_BRAIN_MAX_QUEUE`, `AGENT_BRAIN_JOB_TIMEOUT`, `AGENT_BRAIN_MAX_RETRIES`,
`AGENT_BRAIN_CHECKPOINT_INTERVAL`, `EMBEDDING_CACHE_PERSIST_STATS`,
`AGENT_BRAIN_STRICT_MODE`, `GRAPH_EXTRACTION_MODEL`, `GRAPH_RRF_K`

---

## Output Format Per Step

Each step shows a YAML/env snippet of what was configured, e.g.:

```
Step 9 Complete: File Watcher
==============================

Global debounce: 30s
  AGENT_BRAIN_WATCH_DEBOUNCE_SECONDS=30

Per-folder watcher is configured at index time:
  agent-brain folders add ./src --watch auto --debounce 10

Restart server to apply:
  agent-brain stop && agent-brain start
```

---

## Error States and Fallbacks

| Condition | Response |
|-----------|----------|
| Ollama not installed | Show install instructions |
| Ollama not running | Show `ollama serve` |
| Missing API key | Show export command |
| kuzu not installed | Show install command |
| langextract not installed | Show `poetry install --extras graphrag` |
| No free PostgreSQL port | Show manual port config instructions |
| ab-setup-check.sh not found | Fall back to manual env detection |

---

## Version

This spec was introduced in v9.3.0 (Phase 34). It must be updated whenever the
`agent-brain-config.md` command file changes. The version field in the command frontmatter
must match the CLI version at release time.

Current spec version: v9.3.0 (Phase 34)
Current command version: matches CLI `agent-brain-cli` version.
