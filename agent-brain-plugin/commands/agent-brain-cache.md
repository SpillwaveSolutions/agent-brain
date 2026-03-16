---
name: agent-brain-cache
description: View embedding cache metrics or clear the cache
parameters:
  - name: subcommand
    description: "Operation to perform: status or clear"
    required: true
    allowed: [status, clear]
  - name: yes
    description: Skip confirmation prompt (only for clear)
    required: false
    default: false
  - name: json
    description: Output in JSON format (only for status)
    required: false
    default: false
  - name: url
    description: "Server URL (default: AGENT_BRAIN_URL or http://127.0.0.1:8000)"
    required: false
skills:
  - using-agent-brain
---

# Agent Brain Cache Management

## Purpose

Manage the embedding cache used by Agent Brain to avoid redundant OpenAI API calls:

- **status** — View hit rate, entry counts, and cache size to understand cache health.
- **clear** — Flush all cached embeddings to force fresh computation on the next reindex.

The embedding cache is automatic — it requires no setup. Use this command to monitor it
and clear it when changing embedding providers or models.

## Usage

```
/agent-brain:agent-brain-cache status [--json] [--url <url>]
/agent-brain:agent-brain-cache clear [--yes] [--url <url>]
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| subcommand | Yes | - | Operation: `status` or `clear` |
| --yes | No | false | Skip confirmation prompt (clear only) |
| --json | No | false | Output in JSON format (status only) |
| --url | No | AGENT_BRAIN_URL or http://127.0.0.1:8000 | Server URL override |

### Examples

```
/agent-brain:agent-brain-cache status                # Show cache metrics (human-readable)
/agent-brain:agent-brain-cache status --json         # Show metrics as JSON
/agent-brain:agent-brain-cache clear                 # Clear cache (prompts for confirmation)
/agent-brain:agent-brain-cache clear --yes           # Clear cache (skips confirmation)
```

## Execution: Status Path

### Step 1: Run Cache Status

```bash
agent-brain cache status
```

For JSON output (useful for scripting):

```bash
agent-brain cache status --json
```

### Expected Output

```
Metric            Value
──────────────── ──────
Entries (disk)    1,234
Entries (memory)    500
Hit Rate          87.3%
Hits            5,432
Misses              800
Size             14.81 MB
```

### Interpreting Metrics

| Metric | Description |
|--------|-------------|
| Entries (disk) | Total embeddings persisted in the SQLite cache database |
| Entries (memory) | Embeddings currently held in the in-memory LRU (fastest tier) |
| Hit Rate | Percentage of embedding lookups served from cache (higher is better) |
| Hits | Total successful cache lookups this session |
| Misses | Total cache misses (embedding had to be computed via API) |
| Size | Total disk space used by the cache database |

**Healthy cache indicators:**
- Hit rate > 80% after the first full reindex cycle
- Growing disk entries (cache is accumulating over time)
- Low misses relative to hits (embeddings are being reused)

## Execution: Clear Path

**IMPORTANT**: Clearing the cache permanently removes all cached embeddings. The next
reindex will recompute embeddings via the embedding API (e.g., OpenAI). This may incur
API costs proportional to the amount of indexed content.

### Step 1: Show Current Cache State

Before clearing, MUST report to the user what will be deleted:

```bash
agent-brain cache status
```

Show the user:
- Number of cached entries (disk)
- Cache size (MB)
- Estimated API calls that will be needed on next reindex

### Step 2: Request Confirmation

Before running the clear, you MUST (unless `--yes` is passed):

1. Show the user what will be cleared
2. Ask for explicit confirmation
3. Only proceed if the user confirms with "yes" or similar affirmative

**Example interaction:**

```
The following will be permanently deleted:
  - 1,234 cached embeddings
  - 14.81 MB of cached data

After clearing, the next reindex will recompute all embeddings via the API.
Are you sure you want to clear the embedding cache? [y/N]
```

### Step 3: Execute Clear

Only after confirmation (or if `--yes` was passed):

```bash
agent-brain cache clear --yes
```

### Expected Output

```
Cleared 1,234 cached embeddings (14.8 MB freed)
```

## Output

### After Status

Report to the user:
- Cache hit rate (and whether it indicates healthy caching)
- Number of cached entries and disk usage
- Suggestion if hit rate is low (reindex to warm the cache)

### After Clear

Report to the user:
- Confirmation that clear completed
- Number of embeddings removed and space freed
- Next steps: run /agent-brain:agent-brain-index to rebuild the cache

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| Connection refused | Agent Brain server is not running | Start with `/agent-brain:agent-brain-start` |
| Cache not initialized (503) | Server started but cache subsystem not ready | Wait a moment and retry; restart server if persistent |
| Cache already empty | No cached embeddings to clear | No action needed — this is not an error |
| Permission denied | Cannot write to cache database file | Check directory permissions for `.agent-brain/` |

### Recovery Commands

```bash
# Check server status
agent-brain status

# Start server if needed
agent-brain start

# Verify cache state
agent-brain cache status
```

## When to Check Cache Status

- **After indexing** — verify cache is working and hit rate will improve on re-index
- **When queries seem slow** — a low or zero hit rate means embeddings are being recomputed
- **To monitor cache growth** — track disk usage over time for large indexes

## When to Clear the Cache

- **After changing embedding provider or model** — prevents dimension mismatches and stale vectors
- **Suspected cache corruption** — if embeddings seem incorrect or queries return poor results
- **To force fresh embeddings** — when you know source content has changed significantly

## Related Commands

| Command | Description |
|---------|-------------|
| `/agent-brain:agent-brain-status` | Show server status, document count, and overall health |
| `/agent-brain:agent-brain-reset` | Clear the document index (requires confirmation) |
| `/agent-brain:agent-brain-index` | Index documents for search |

## Safety Notes

- **Cache clear is reversible** — clearing removes cached embeddings, not source documents
- Clearing the cache does NOT remove indexed documents or search data
- The cache will be rebuilt automatically on the next reindex
- If you want to remove indexed documents, use `/agent-brain:agent-brain-reset` instead
