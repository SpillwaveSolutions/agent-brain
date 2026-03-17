---
name: agent-brain-list
description: List all running Agent Brain instances across projects
parameters:
  - name: all
    description: Show all instances including stale ones
    required: false
    default: false
  - name: json
    description: Output as JSON
    required: false
    default: false
skills:
  - using-agent-brain
last_validated: 2026-03-16
---

# List Agent Brain Instances

## Purpose

Displays all running Agent Brain server instances across all projects. Shows each instance's project name, URL, process ID, mode, and health status by scanning the global registry.

## Usage

```
/agent-brain:agent-brain-list [--all] [--json]
```

## Execution

Run the following command to list all instances:

```bash
agent-brain list
```

### Options

```bash
agent-brain list              # List running instances only
agent-brain list --all        # Include stale/unhealthy instances
agent-brain list -a           # Short form of --all
agent-brain list --json       # Output as JSON for scripting
```

### Expected Output

```
         Agent Brain Instances
Project         URL                      PID   Mode     Status
my-project      http://127.0.0.1:8000    12345 project  running
api-docs        http://127.0.0.1:8001    12678 project  running

2 running, 0 stale/unhealthy
```

### JSON Output

```bash
agent-brain list --json
```

```json
{
  "instances": [
    {
      "project_root": "/home/user/my-project",
      "project_name": "my-project",
      "base_url": "http://127.0.0.1:8000",
      "pid": 12345,
      "mode": "project",
      "status": "running",
      "started_at": "2026-01-31T10:30:00Z"
    }
  ],
  "total": 1
}
```

## Output

Format the result as a table with the following columns:

| Column | Description |
|--------|-------------|
| Project | Project directory name |
| URL | Server base URL (e.g., `http://127.0.0.1:8000`) |
| PID | Process ID of the server |
| Mode | Instance mode: `project` or `shared` |
| Status | Health status: `running`, `unhealthy`, `stale` |

### Status Indicators

- **running**: Server process is alive and health endpoint responds
- **unhealthy**: Server process is alive but health endpoint fails
- **stale**: Process is no longer alive (auto-cleaned from registry)

### Registry Cleanup

Stale entries are automatically removed from the global registry when `agent-brain list` runs. By default, only `running` instances are shown. Use `--all` to include stale and unhealthy instances.

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| No running instances found | No servers have been started | Run `agent-brain init` and `agent-brain start` |
| Permission Error | Cannot read registry or signal processes | Check file permissions |
| Connection refused | Server crashed or was killed externally | Clean up with `agent-brain stop` |

### Cleanup Stale Instances

```bash
# For each stopped instance, clean up its state
cd /path/to/project
agent-brain stop

# Or check system processes directly
ps aux | grep agent-brain
```

## Notes

- Instances are discovered from the global registry at `~/.local/state/agent-brain/registry.json`
- Each instance is validated by checking process liveness and the `/health/` endpoint
- Each project has its own isolated instance
- Ports are automatically assigned from the 8000-8100 range (configurable)
- Stale registry entries are automatically cleaned up during listing
