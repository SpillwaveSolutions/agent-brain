---
created: 2026-03-19T03:40:14.668Z
title: Fix chroma_db and cache dirs resolving relative to CWD instead of AGENT_BRAIN_STATE_DIR
area: tooling
files:
  - agent-brain-server/agent_brain_server/config/settings.py
  - agent-brain-server/agent_brain_server/storage/vector_store.py
  - agent-brain-server/agent_brain_server/api/main.py
---

## Problem

`chroma_db/` appears at the project root (`./chroma_db`) instead of exclusively
under `.agent-brain/data/chroma_db`. The embedding cache may also be misplaced.

Observed:
```
/Users/richardhightower/articles/chroma_db        ← STRAY at project root
/Users/richardhightower/articles/.agent-brain/data/chroma_db    ← correct
/Users/richardhightower/articles/.agent-brain/data/bm25_index   ← correct
/Users/richardhightower/articles/.agent-brain/data/graph_index  ← correct
/Users/richardhightower/articles/.agent-brain/data/llamaindex   ← correct
```

Root cause: `CHROMA_PERSIST_DIR` defaults to `./chroma_db` (relative to CWD).
When the server starts from a directory that isn't the state dir, it creates
a stray `chroma_db` at CWD instead of using the state directory.

From CLAUDE.md env var reference:
```
CHROMA_PERSIST_DIR  ./chroma_db   ChromaDB storage directory
BM25_INDEX_PATH     ./bm25_index  BM25 keyword index directory
```
Both defaults are CWD-relative, not state-dir-relative.

## Solution

**Approach A — Resolve all data paths relative to state dir (primary fix)**
When `AGENT_BRAIN_STATE_DIR` is set, derive all data paths from it automatically.
No env var needed — just compute from state dir:

```
{STATE_DIR}/data/chroma_db      ← vector store  (was CHROMA_PERSIST_DIR)
{STATE_DIR}/data/bm25_index     ← keyword index  (was BM25_INDEX_PATH)
{STATE_DIR}/data/graph_index    ← graph store
{STATE_DIR}/data/llamaindex/    ← llamaindex persistence
{STATE_DIR}/data/cache/         ← embedding cache (consolidate here)
```

Target directory layout:
```
.agent-brain/
  data/
    chroma_db/
    bm25_index/
    graph_index/
    llamaindex/
    cache/           ← embedding cache (new consolidated location)
  runtime.json
  config.yaml
  agent-brain.lock
  agent-brain.pid
```

**Approach B — Explicit env var override**
Keep defaults but document that users MUST set `CHROMA_PERSIST_DIR` and
`BM25_INDEX_PATH` to paths under `.agent-brain/data/`. Expose in config wizard.
Fragile — easy to forget, doesn't fix existing installs.

**Approach C — Auto-migrate stray directories on startup**
On server start, detect stray `./chroma_db` or `./bm25_index` at CWD, move them
into `{STATE_DIR}/data/`, log a warning. Handles existing bad installs gracefully.

## Recommended

Approach A + C together:
- A fixes the root cause for new installs
- C migrates existing stray directories automatically

## Notes

- Must run `task before-push` after changes — storage path changes affect tests
- The stray `./chroma_db` at project root should be added to `.gitignore` as a
  safety net even after the fix
- Embedding cache currently stored via `EMBEDDING_CACHE_MAX_DISK_MB` setting —
  consolidate its persist path to `{STATE_DIR}/data/cache/` as part of this fix
