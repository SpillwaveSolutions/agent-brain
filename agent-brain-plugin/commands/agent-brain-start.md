---
name: agent-brain-start
description: Start the Agent Brain server for this project
parameters:
  - name: daemon
    description: Run in background (default true)
    required: false
    default: true
skills:
  - using-agent-brain
---

# Agent Brain Start

## Purpose

Starts the Agent Brain server for the current project. The server provides:
- Document indexing and storage
- Hybrid, semantic, and keyword search
- Multi-instance support with automatic port allocation

## Usage

```
/agent-brain:agent-brain-start 
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| daemon | No | true | Run server in background |

## Execution

### Pre-flight Check

Verify the project is initialized:

```bash
# Check for .agent-brain/ directory
ls -la .agent-brain/
```

If not initialized:
```bash
agent-brain init
```

### Start Server

```bash
# Start in background (recommended)
agent-brain start

# Start in foreground (for debugging)
agent-brain start
```

### Verify Server Started

```bash
agent-brain status
```

## Output

### Successful Start

```
Starting Agent Brain server...

Server started successfully!
  URL:      http://127.0.0.1:49321
  Port:     49321
  Mode:     project
  Project:  my-project
  PID:      12345

Runtime config saved to: .agent-brain/runtime.json

To check status:  /agent-brain:agent-brain-status
To stop server:   /agent-brain:agent-brain-stop
```

### Runtime Configuration

The server creates a runtime file at `.agent-brain/runtime.json`:

```json
{
  "mode": "project",
  "port": 49321,
  "base_url": "http://127.0.0.1:49321",
  "pid": 12345,
  "project_id": "my-project",
  "started_at": "2026-01-31T10:30:00Z"
}
```

This file enables automatic server discovery for CLI commands.

## Error Handling

### Project Not Initialized

```
Error: Project not initialized for Agent Brain

Run 'agent-brain init' first to initialize this project.
```

**Resolution**:
```bash
agent-brain init
agent-brain start
```

### Server Already Running

```
Error: Agent Brain server already running on port 49321
PID: 12345

To restart: agent-brain stop && agent-brain start
```

**Resolution**:
- Use existing server, or
- Stop and restart: `agent-brain stop && agent-brain start`

### Port Conflict

```
Error: Port 8000 already in use

Agent Brain will automatically find an available port.
Starting on port 49322...
```

Agent Brain automatically allocates an available port when the default is busy.

### Missing API Keys

```
Warning: OPENAI_API_KEY not set
Server will start, but semantic search will be unavailable.

To enable semantic search:
  export OPENAI_API_KEY="sk-proj-..."
```

**Resolution**: Set the API key via config file or environment variable and restart.

**Option 1: Config file** (`~/.agent-brain/config.yaml`):
```yaml
embedding:
  provider: "openai"
  api_key: "sk-proj-..."
```

**Option 2: Environment variable**:
```bash
export OPENAI_API_KEY="sk-proj-..."
```

Then restart:
```bash
agent-brain stop
agent-brain start
```

### Permission Denied

```
Error: Permission denied when creating runtime directory
```

**Resolution**:
```bash
mkdir -p .agent-brain
chmod 755 .agent-brain
agent-brain start
```

## Post-Start Tasks

### 1. Verify Server Health

```bash
agent-brain status
```

### 2. Index Documents (if first time)

```bash
# Index documentation
agent-brain index docs/

# Index code files
agent-brain index src/ --include-code
```

### 3. Test Search

```bash
agent-brain query "test query" --mode hybrid
```

## Server Modes

### Project Mode (Default)

- Server runs for a single project
- Data stored in `.agent-brain/`
- Automatic port allocation
- Isolated from other projects

### Shared Mode

```bash
AGENT_BRAIN_MODE=shared agent-brain start
```

- Server serves multiple projects
- Data stored in `~/.agent-brain/`
- Fixed port (default 8000)
- Shared index across projects

## Related Commands

| Command | Description |
|---------|-------------|
| `/agent-brain:agent-brain-init` | Initialize project for Agent Brain |
| `/agent-brain:agent-brain-status` | Check server status |
| `/agent-brain:agent-brain-stop` | Stop the server |
| `/agent-brain:agent-brain-list` | List all running instances |

## Troubleshooting

### Server Won't Start

1. Check for existing processes:
   ```bash
   ps aux | grep agent-brain
   ```

2. Check port availability:
   ```bash
   lsof -i :8000
   ```

3. Check logs:
   ```bash
   cat .agent-brain/server.log
   ```

### Server Crashes on Start

1. Verify Python environment:
   ```bash
   which python
   python --version  # Should be 3.10+
   ```

2. Verify installation:
   ```bash
   pip show agent-brain-rag agent-brain-cli
   ```

3. Check for dependency issues:
   ```bash
   pip check
   ```
