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
skills:
  - using-agent-brain
---

# Index Documents

## Purpose

Indexes documents at the specified path for semantic search. Processes markdown, PDF, text, and optionally code files. Creates vector embeddings for semantic search and builds the BM25 index for keyword search.

## Usage

```
/agent-brain-index <path> [--include-code]
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| path | Yes | - | Path to documents (file or directory) |
| --include-code | No | false | Include code files (.py, .ts, .js, .java, etc.) |

### Examples

```
/agent-brain-index docs/
/agent-brain-index ./src --include-code
/agent-brain-index /absolute/path/to/files
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

### Expected Output

```
Indexing documents from: /home/user/project/docs
==============================================

Scanning files...
Found 45 files to index:
  - 32 Markdown files (.md)
  - 8 PDF files (.pdf)
  - 5 Text files (.txt)

Processing...
[========================================] 100% (45/45)

Indexing complete!
  Documents indexed: 45
  Chunks created: 312
  Time elapsed: 12.3s
  Index size: 24.5 MB
```

## Output

Report progress and results:

1. **Scanning Phase**
   - Show path being indexed
   - Report file counts by type

2. **Processing Phase**
   - Show progress indicator
   - Report any skipped files

3. **Completion Summary**
   - Total documents indexed
   - Number of chunks created
   - Time elapsed
   - Index size

### Supported File Types

| Category | Extensions |
|----------|------------|
| Documents | `.md`, `.txt`, `.pdf`, `.rst` |
| Code (with --include-code) | `.py`, `.ts`, `.js`, `.java`, `.go`, `.rs`, `.c`, `.cpp`, `.h` |

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| Path not found | Invalid path specified | Verify the path exists |
| No files found | Path contains no supported files | Check file extensions |
| Server not running | Agent Brain server is stopped | Run `agent-brain start` first |
| Embedding provider error | Provider not configured | Run `/agent-brain-config` (use Ollama for free local option) |
| Permission denied | Cannot read files | Check file permissions |
| Out of memory | Too many files at once | Index in smaller batches |

### Recovery Commands

```bash
# Verify server is running
agent-brain status

# Check configuration
agent-brain verify

# Index smaller directory first
agent-brain index docs/getting-started/
```

## Notes

- Indexing is additive; existing documents are preserved
- Use `agent-brain reset --yes` to clear the index before re-indexing
- Large directories may take several minutes
- Code files require AST parsing and may be slower
- Binary files and images are automatically skipped
- Relative paths are resolved from the current directory
