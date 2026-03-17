---
name: agent-brain-stop
description: Stop the Agent Brain server for this project
parameters:
  - name: path
    description: Project path (default auto-detect project root)
    required: false
  - name: force
    description: Force stop with SIGKILL if SIGTERM fails
    required: false
    default: false
  - name: timeout
    description: Timeout for graceful shutdown in seconds
    required: false
    default: 10
  - name: json
    description: Output as JSON
    required: false
    default: false
skills:
  - using-agent-brain
last_validated: 2026-03-16
---

# Stop Agent Brain Server

## Purpose

Gracefully stops the Agent Brain server running for the current project. Sends SIGTERM and waits for graceful shutdown. If `--force` is specified and the process does not exit within the timeout, sends SIGKILL.

## Usage

```
/agent-brain:agent-brain-stop [--path <dir>] [--force] [--timeout <sec>] [--json]
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| --path, -p | No | auto-detect | Project path |
| --force, -f | No | false | Force stop with SIGKILL if SIGTERM fails |
| --timeout | No | 10 | Graceful shutdown timeout in seconds |
| --json | No | false | Output as JSON |

## Execution

```bash
# Stop server for current project
agent-brain stop

# Force stop if graceful shutdown fails
agent-brain stop --force

# Stop a specific project's server
agent-brain stop --path /my/project

# JSON output for scripting
agent-brain stop --json
```

### Expected Output (Success)

```
Stopping server (PID 12345)...
Server stopped gracefully (PID 12345).
```

### JSON Output (Success)

```json
{
  "status": "stopped",
  "message": "Server stopped gracefully",
  "pid": 12345,
  "project_root": "/home/user/my-project"
}
```

### Expected Output (Server Not Running)

```
No server running for this project.
```

### Force Kill Output

```
Stopping server (PID 12345)...
Graceful shutdown timeout, sending SIGKILL...
Server force killed (PID 12345).
```

## Output

Format the result as follows:

**Server Stopped Successfully:**
- Confirm the server was stopped
- Report the PID that was terminated
- State files and registry entry are cleaned up automatically

**Server Not Running:**
- Inform the user no server was found

**Server Already Stopped:**
- If the process is no longer alive but state files exist, they are cleaned up

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| No server running | Server already stopped or never started | No action needed |
| Permission denied | Process owned by different user | Run with appropriate permissions |
| Graceful shutdown timeout | Process unresponsive within timeout | Use `--force` to send SIGKILL |
| No Agent Brain state found | State directory missing | Project may not be initialized |

### Recovery Commands

```bash
# Check if any instances are still running
agent-brain list --all

# Force stop if graceful fails
agent-brain stop --force

# Force kill manually if all else fails (use PID from list)
kill -9 <pid>

# Verify cleanup
agent-brain status
```

## Notes

- The stop command only affects the server for the current project
- Other project instances remain running
- The document index is preserved; only the server process is stopped
- State files (runtime.json, lock, PID) are cleaned up on stop
- The project is removed from the global registry on stop
- Restart with `/agent-brain:agent-brain-start` when needed
