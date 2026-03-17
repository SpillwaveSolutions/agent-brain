---
name: agent-brain-folders
description: Manage indexed folders — list, add, or remove
parameters:
  - name: action
    description: Action to perform (list, add, remove)
    required: true
  - name: path
    description: Folder path (required for add/remove)
    required: false
  - name: yes
    description: Skip confirmation prompt for remove
    required: false
    default: false
skills:
  - using-agent-brain
---

# Manage Indexed Folders

## Purpose

List, add, or remove folders from the Agent Brain index. Use this to inspect
which folders are currently indexed, trigger indexing for new folders, or
remove all chunks associated with a folder.

## Usage

```
/agent-brain:agent-brain-folders list
/agent-brain:agent-brain-folders add <path>
/agent-brain:agent-brain-folders remove <path>
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| action | Yes | - | list, add, or remove |
| path | For add/remove | - | Path to the folder |
| --yes | No | false | Skip confirmation for remove |
| --include-code | No | false | Include code files (for add) |
| --include-type | No | - | File type presets, e.g., python,docs (for add) |
| --chunk-size | No | 512 | Target chunk size in tokens (for add) |
| --force | No | false | Force re-indexing, bypass manifest (for add) |
| --watch | No | off | Watch mode: `auto` (file watching) or `off` (for add) |
| --debounce | No | 30 | Debounce interval in seconds for file watching (for add) |
| --json | No | false | Output as JSON (for list, add, remove) |

### Examples

```
/agent-brain:agent-brain-folders list
/agent-brain:agent-brain-folders add ./docs
/agent-brain:agent-brain-folders add ./src --include-code
/agent-brain:agent-brain-folders add ./src --include-type python,docs
/agent-brain:agent-brain-folders add ./docs --force
/agent-brain:agent-brain-folders add ./src --watch auto --debounce 10
/agent-brain:agent-brain-folders remove ./old-docs
/agent-brain:agent-brain-folders remove ./old-docs --yes
```

## Execution

Based on the action parameter:

### List Folders

Show all indexed folders with chunk counts and last indexed timestamps:

```bash
agent-brain folders list
```

### Add Folder (triggers indexing)

Queue an indexing job for the specified folder. Add supports all index options:

```bash
agent-brain folders add <path>
agent-brain folders add <path> --include-code
agent-brain folders add <path> --include-type python,docs
agent-brain folders add <path> --include-code --force
```

Note: `folders add` is an alias for `index` — re-adding an already-indexed folder triggers incremental re-indexing (only changed files processed).

### Remove Folder (deletes all chunks)

Remove all indexed chunks for the folder. Requires confirmation unless
`--yes` is passed:

```bash
agent-brain folders remove <path> --yes
```

### Expected Output

**List:**
```
Folder Path              Chunks  Last Indexed          Watch
/home/user/docs          312     2026-02-24T12:00:00   off
/home/user/src           1024    2026-02-24T13:30:00   auto
```

**Add:**
```
Indexing job queued!

Job ID: abc123
Folder: /home/user/docs
Status: queued

Use 'agent-brain jobs' to monitor progress.
```

**Remove:**
```
Removed 312 chunks for /home/user/docs
```

## Output

Report the results clearly:

1. **List** — Show table of indexed folders, chunk counts, and timestamps
2. **Add** — Show job ID and status; remind user to monitor with `agent-brain jobs`
3. **Remove** — Confirm number of chunks deleted

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| Server not running | Agent Brain server is stopped | Run `agent-brain start` |
| Folder not found | Folder path not indexed | Check `agent-brain folders list` |
| Active job conflict | Indexing job running for folder | Wait or cancel with `agent-brain jobs JOB_ID --cancel` |
| Connection error | Server unreachable | Verify server with `agent-brain status` |

### Recovery Commands

```bash
# Verify server is running
agent-brain status

# Check indexed folders
agent-brain folders list

# Monitor job queue
agent-brain jobs --watch
```

## Notes

- Folder paths are resolved to absolute paths automatically
- Remove does not require the folder to exist on disk
- Add is idempotent — re-indexing an already-indexed folder updates its chunks
- Use `agent-brain types list` to see available file type presets for filtering
