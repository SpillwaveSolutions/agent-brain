---
name: agent-brain-stop
description: Stop the Agent Brain server for this project
parameters: []
skills:
  - using-agent-brain
---

# Stop Agent Brain Server

## Purpose

Gracefully stops the Agent Brain server running for the current project. This terminates the background server process and frees up the port for other uses.

## Usage

```
/agent-brain:agent-brain-stop
```

## Execution

Run the following command to stop the server:

```bash
agent-brain stop
```

### Expected Output (Success)

```
Agent Brain server stopped successfully.
PID 12345 terminated.
Port 49321 is now available.
```

### Expected Output (Server Not Running)

```
No Agent Brain server is running for this project.
```

## Output

Format the result as follows:

**Server Stopped Successfully:**
- Confirm the server was stopped
- Report the PID that was terminated
- Confirm the port is now available

**Server Not Running:**
- Inform the user no server was found
- Suggest running `/agent-brain:agent-brain-status` to verify

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| No server running | Server already stopped or never started | No action needed |
| Permission denied | Process owned by different user | Run with appropriate permissions |
| PID file missing | Unclean shutdown | Check for orphaned processes with `agent-brain list` |
| Failed to terminate | Process unresponsive | May need to manually kill the process |

### Recovery Commands

```bash
# Check if any instances are still running
agent-brain list

# Force kill if process is unresponsive (use PID from list)
kill -9 <pid>

# Verify cleanup
agent-brain status
```

## Notes

- The stop command only affects the server for the current project
- Other project instances remain running
- The document index is preserved; only the server process is stopped
- Restart with `/agent-brain:agent-brain-start` when needed
