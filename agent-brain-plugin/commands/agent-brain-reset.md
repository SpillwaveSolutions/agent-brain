---
name: agent-brain-reset
description: Clear the document index (requires confirmation)
parameters:
  - name: yes
    description: Skip confirmation prompt
    required: false
    default: false
  - name: url
    description: Server URL (default from config or http://127.0.0.1:8000)
    required: false
  - name: json
    description: Output as JSON
    required: false
    default: false
skills:
  - using-agent-brain
---

# Reset Document Index

## Purpose

Clears all indexed documents from the Agent Brain server. This removes all vector embeddings and BM25 index data. Use this when you need to completely rebuild the index or remove outdated content.

## Usage

```
/agent-brain:agent-brain-reset [--yes] [--url <url>] [--json]
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| --yes, -y | No | false | Skip confirmation prompt and proceed immediately |
| --url | No | from config or http://127.0.0.1:8000 | Server URL (env: AGENT_BRAIN_URL) |
| --json | No | false | Output as JSON |

### Examples

```
/agent-brain:agent-brain-reset           # Prompts for confirmation
/agent-brain:agent-brain-reset --yes     # Skips confirmation
/agent-brain:agent-brain-reset --json    # JSON output (skips confirmation)
```

## Execution

**IMPORTANT**: This command requires explicit user confirmation before executing.

### Step 1: Check Current Index Status

```bash
agent-brain status
```

Report to the user what will be deleted:
- Number of documents currently indexed
- Approximate index size
- Collections that will be cleared

### Step 2: Request Confirmation

Before running the reset, you MUST:

1. Show the user what will be deleted
2. Ask for explicit confirmation
3. Only proceed if the user confirms with "yes" or similar affirmative

**Example interaction:**
```
The following will be permanently deleted:
  - 156 indexed documents
  - 1,247 text chunks
  - Vector embeddings (~45 MB)
  - BM25 index data

Are you sure you want to reset the index? This cannot be undone.
```

### Step 3: Execute Reset

Only after confirmation:

```bash
agent-brain reset --yes
```

### Expected Output

```
Resetting Agent Brain index...

Clearing vector store... done
Clearing BM25 index... done
Clearing metadata... done

Index reset complete.
  Documents removed: 156
  Storage freed: 45.2 MB

The index is now empty. Run '/agent-brain:agent-brain-index <path>' to add documents.
```

## Output

After reset, report:
- Confirmation that reset completed
- Number of documents removed
- Storage space freed
- Next steps for re-indexing

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| Server not running | Agent Brain server is stopped | Start with `/agent-brain:agent-brain-start` |
| Server Error (409) | Indexing is in progress | Wait for indexing to complete, then retry |
| Index already empty | No documents to clear | No action needed |
| Permission denied | Cannot write to storage directory | Check directory permissions |

### Recovery Commands

```bash
# Check server status
agent-brain status

# Start server if needed
agent-brain start

# Verify index is clear
agent-brain status
```

## Safety Notes

- **This operation is irreversible** - all indexed data is permanently deleted
- The original source documents are NOT affected
- Only the search index is cleared
- Re-indexing will require re-processing all documents
- Consider backing up the `.agent-brain/` directory before resetting

## Notes

- The reset only affects the current project's index
- Other project instances are not affected
- Server remains running after reset
- Re-index with `/agent-brain:agent-brain-index <path>` after reset
