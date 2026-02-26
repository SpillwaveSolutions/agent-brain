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
/agent-brain-folders list
/agent-brain-folders add <path>
/agent-brain-folders remove <path>
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| action | Yes | - | list, add, or remove |
| path | For add/remove | - | Path to the folder |
| --yes | No | false | Skip confirmation for remove |

### Examples

```
/agent-brain-folders list
/agent-brain-folders add ./docs
/agent-brain-folders add ./src --include-code
/agent-brain-folders remove ./old-docs
```

## Execution

Based on the action parameter:

### List Folders

Show all indexed folders with chunk counts and last indexed timestamps:

```bash
agent-brain folders list
```

### Add Folder (triggers indexing)

Queue an indexing job for the specified folder:

```bash
agent-brain folders add <path>
```

To include source code files:

```bash
agent-brain folders add <path> --include-code
```

### Remove Folder (deletes all chunks)

Remove all indexed chunks for the folder. Requires confirmation unless
`--yes` is passed:

```bash
agent-brain folders remove <path> --yes
```

### Expected Output

**List:**
```
Folder Path              Chunks  Last Indexed
/home/user/docs          312     2026-02-24T12:00:00
/home/user/src           1024    2026-02-24T13:30:00
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
