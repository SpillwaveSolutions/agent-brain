---
name: agent-brain-list
description: List all running Agent Brain instances across projects
parameters: []
skills:
  - using-agent-brain
---

# List Agent Brain Instances

## Purpose

Displays all running Agent Brain server instances across all projects. Shows each instance's project path, port, process ID, and health status.

## Usage

```
/agent-brain:agent-brain-list
```

## Execution

Run the following command to list all instances:

```bash
agent-brain list
```

### Expected Output

```
Agent Brain Instances
=====================

| Project                | Port  | PID   | Status  | Documents |
|------------------------|-------|-------|---------|-----------|
| /home/user/my-project  | 49321 | 12345 | healthy | 156       |
| /home/user/api-docs    | 49322 | 12678 | healthy | 89        |
| /home/user/legacy      | 49323 | 12890 | stopped | -         |

Total: 3 instances (2 running, 1 stopped)
```

## Output

Format the result as a table with the following columns:

| Column | Description |
|--------|-------------|
| Project | Absolute path to the project directory |
| Port | Server port number (49xxx range) |
| PID | Process ID of the server |
| Status | Health status: `healthy`, `unhealthy`, `stopped` |
| Documents | Number of indexed documents (or `-` if unavailable) |

### Status Indicators

- **healthy**: Server is running and responding to health checks
- **unhealthy**: Server is running but not responding properly
- **stopped**: PID file exists but process is not running

### Summary Line

Include a summary showing:
- Total number of instances tracked
- Number currently running
- Number stopped or crashed

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| No instances found | No servers have been started | Run `agent-brain init` and `agent-brain start` |
| Connection refused | Server crashed or was killed externally | Clean up with `agent-brain stop` |
| Stale PID file | Server stopped without cleanup | Run `agent-brain stop` to clean up |

### Cleanup Stale Instances

```bash
# For each stopped instance, clean up its state
cd /path/to/project
agent-brain stop

# Or check system processes directly
ps aux | grep agent-brain
```

## Notes

- Instances are discovered from `.claude/agent-brain/runtime.json` files
- Each project has its own isolated instance
- Ports are automatically assigned in the 49000-49999 range
- Health checks query the `/health` endpoint of each instance
