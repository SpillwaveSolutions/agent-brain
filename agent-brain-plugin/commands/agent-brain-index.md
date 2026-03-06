---
name: agent-brain-index
description: Index documents for semantic search
parameters:
  - name: path
    description: Path to documents to index
    required: true
  - name: include-code
    description: Include code files in indexing
    required: false
    default: false
  - name: include-type
    description: File type presets to include (e.g., python,docs)
    required: false
  - name: force
    description: Force re-indexing (bypass manifest, evict all prior chunks)
    required: false
    default: false
skills:
  - using-agent-brain
---

# Index Documents

## Purpose

Indexes documents at the specified path for semantic search. Processes markdown, PDF, text, and optionally code files. Creates vector embeddings for semantic search and builds the BM25 index for keyword search. Supports incremental indexing — only changed files are re-processed on subsequent runs.

## Usage

```
/agent-brain-index <path> [options]
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| path | Yes | - | Path to documents (file or directory) |
| --include-code | No | false | Include code files (.py, .ts, .js, .java, etc.) |
| --include-type | No | - | File type presets (e.g., python,docs,typescript). Use `agent-brain types list` to see all. |
| --chunk-size | No | 512 | Target chunk size in tokens |
| --chunk-overlap | No | 50 | Overlap between chunks in tokens |
| --no-recursive | No | false | Don't scan subdirectories |
| --languages | No | - | Comma-separated language list for code files |
| --code-strategy | No | ast_aware | Code splitting strategy: ast_aware or text_based |
| --include-patterns | No | - | Additional glob include patterns |
| --exclude-patterns | No | - | Additional glob exclude patterns |
| --generate-summaries | No | false | Generate LLM summaries for better search quality |
| --force | No | false | Force re-indexing (bypass manifest, evict all prior chunks) |
| --allow-external | No | false | Allow indexing paths outside the project directory |
| --json | No | false | Output results as JSON |

### Examples

```
/agent-brain-index docs/
/agent-brain-index ./src --include-code
/agent-brain-index ./project --include-type python,docs
/agent-brain-index ./src --include-type typescript --include-patterns "*.json"
/agent-brain-index ./docs --force
/agent-brain-index ./src --include-code --chunk-size 1024 --generate-summaries
```

## Execution

Run the appropriate command based on parameters:

**Index documents only:**
```bash
agent-brain index <path>
```

**Include code files:**
```bash
agent-brain index <path> --include-code
```

**With file type presets:**
```bash
agent-brain index <path> --include-type python,docs
```

**Force full re-index (bypass incremental):**
```bash
agent-brain index <path> --force
```

**With all options:**
```bash
agent-brain index <path> --include-code --include-type python,docs --chunk-size 1024 --generate-summaries --force
```

### Expected Output

```
Indexing job queued!

Job ID: abc123
Folder: /home/user/project/docs
Include types: python, docs
Status: queued

Use 'agent-brain jobs' to monitor progress.
```

**After completion (check with `agent-brain jobs <job_id>`):**

First-time indexing:
```
Files added: 45
Chunks created: 312
```

Incremental re-indexing:
```
Eviction Summary:
  Files added:     3
  Files changed:   2
  Files deleted:   1
  Files unchanged: 39
  Chunks evicted:  15
  Chunks created:  25
```

## Output

Report progress and results:

1. **Job Queued** — Show job ID and status
2. **Monitor Progress** — Use `agent-brain jobs --watch`
3. **Completion Summary** — Eviction summary for incremental runs

### Supported File Types

| Category | Extensions |
|----------|------------|
| Documents | `.md`, `.txt`, `.pdf`, `.rst` |
| Code (with --include-code) | `.py`, `.ts`, `.js`, `.java`, `.go`, `.rs`, `.c`, `.cpp`, `.h`, `.cs` |

### File Type Presets (with --include-type)

| Preset | Extensions |
|--------|------------|
| python | `.py`, `.pyi`, `.pyw` |
| javascript | `.js`, `.jsx`, `.mjs`, `.cjs` |
| typescript | `.ts`, `.tsx` |
| go | `.go` |
| rust | `.rs` |
| java | `.java` |
| csharp | `.cs` |
| c | `.c`, `.h` |
| cpp | `.cpp`, `.hpp`, `.cc`, `.hh` |
| web | `.html`, `.css`, `.scss`, `.jsx`, `.tsx` |
| docs | `.md`, `.txt`, `.rst`, `.pdf` |
| text | `.md`, `.txt`, `.rst` |
| pdf | `.pdf` |
| code | All language presets combined |

Use `agent-brain types list` to see all available presets.

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| Path not found | Invalid path specified | Verify the path exists |
| No files found | Path contains no supported files | Check file extensions or use --include-type |
| Server not running | Agent Brain server is stopped | Run `agent-brain start` first |
| Embedding provider error | Provider not configured | Run `/agent-brain-config` |
| Permission denied | Cannot read files | Check file permissions |
| Queue full (429) | Too many concurrent jobs | Wait or cancel with `agent-brain jobs JOB_ID --cancel` |

### Recovery Commands

```bash
# Verify server is running
agent-brain status

# Check configuration
agent-brain verify

# Monitor job progress
agent-brain jobs --watch

# Force full re-index if incremental fails
agent-brain index <path> --force
```

## Notes

- Indexing runs asynchronously via job queue — use `agent-brain jobs` to monitor
- Incremental indexing: only changed/new files are processed (unchanged files skipped)
- Use `--force` to bypass manifest tracking and fully re-index
- Deleted files' chunks are automatically evicted during incremental re-indexing
- Use `agent-brain reset --yes` to clear the entire index before re-indexing
- Large directories may take several minutes
- Code files require AST parsing and may be slower
- Binary files and images are automatically skipped
- Relative paths are resolved from the current directory
- Use `/agent-brain-inject` to enrich chunks with custom metadata during indexing
