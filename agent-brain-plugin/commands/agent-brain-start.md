---
name: agent-brain-start
description: Start the Agent Brain server for this project
parameters:
  - name: path
    description: Project path (default auto-detect project root)
    required: false
  - name: host
    description: Server bind host (overrides config)
    required: false
  - name: port
    description: Server port (overrides config)
    required: false
  - name: foreground
    description: Run in foreground instead of daemonizing
    required: false
    default: false
  - name: timeout
    description: Startup timeout in seconds
    required: false
    default: 30
  - name: strict
    description: Fail on critical provider configuration errors
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

# Agent Brain Start

## Purpose

Starts the Agent Brain server for the current project. The server provides:
- Document indexing and storage
- Hybrid, semantic, and keyword search
- Multi-instance support with automatic port allocation

## Usage

```
/agent-brain:agent-brain-start [--path <dir>] [--host <host>] [--port <port>] [--foreground] [--strict] [--json]
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| --path, -p | No | auto-detect | Project path |
| --host | No | 127.0.0.1 | Server bind host (overrides config) |
| --port | No | auto-select (8000-8100) | Server port (overrides config) |
| --foreground, -f | No | false | Run in foreground (don't daemonize) |
| --timeout | No | 30 | Startup timeout in seconds |
| --strict | No | false | Fail on critical provider config errors |
| --json | No | false | Output as JSON |

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
# Start in background (default, recommended)
agent-brain start

# Start on a specific port
agent-brain start --port 8080

# Start in foreground for debugging
agent-brain start --foreground

# Start with strict mode (fail on missing API keys)
agent-brain start --strict

# Start for a specific project path
agent-brain start --path /my/project

# JSON output for scripting
agent-brain start --json
```

### Verify Server Started

```bash
agent-brain status
```

## Output

### Successful Start

```
Agent Brain Server Running
URL: http://127.0.0.1:8000
PID: 12345
Project: /home/user/my-project
Log: /home/user/my-project/.agent-brain/logs/server.log

Next steps:
  - Query: agent-brain query 'search term' --url http://127.0.0.1:8000
  - Stop: agent-brain stop
```

### JSON Output

```json
{
  "status": "started",
  "base_url": "http://127.0.0.1:8000",
  "pid": 12345,
  "project_root": "/home/user/my-project",
  "log_file": "/home/user/my-project/.agent-brain/logs/server.log"
}
```

### Runtime Configuration

The server creates a runtime file (in the state directory) with:

```json
{
  "schema_version": "1.0",
  "mode": "project",
  "project_root": "/home/user/my-project",
  "instance_id": "a1b2c3d4e5f6",
  "base_url": "http://127.0.0.1:8000",
  "bind_host": "127.0.0.1",
  "port": 8000,
  "pid": 12345,
  "started_at": "2026-01-31T10:30:00+00:00"
}
```

This file enables automatic server discovery for CLI commands.

## Error Handling

### Project Not Initialized

```
Error: Project not initialized at /home/user/my-project
Run 'agent-brain init' to initialize the project.
```

**Resolution**:
```bash
agent-brain init
agent-brain start
```

### Server Already Running

If a server is already running for this project, the command reports the existing URL instead of starting a new one:

```
Server Running
Server already running!
URL: http://127.0.0.1:8000
PID: 12345
Project: /home/user/my-project
```

**Resolution**:
- Use the existing server, or
- Stop and restart: `agent-brain stop && agent-brain start`

### No Available Port

```
Error: No available port in range 8000-8100
```

**Resolution**: Specify a port explicitly or stop other instances:
```bash
agent-brain start --port 9000
# or
agent-brain list --all
agent-brain stop
```

### Missing API Keys

The server starts even without API keys, but provider-dependent features will be unavailable. Use `--strict` to force failure on missing keys.

**Resolution**: Set the API key via config file or environment variable and restart.

**Option 1: Config file** (`.agent-brain/config.yaml` or `~/.config/agent-brain/config.yaml`):
```yaml
embedding:
  provider: "openai"
  api_key_env: "OPENAI_API_KEY"
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
Permission Error: [Errno 13] Permission denied: ...
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

# Index code with type preset
agent-brain index src/ --include-type python
```

### 3. Test Search

```bash
agent-brain query "test query" --mode hybrid
```

## Server Behavior

### Project Root Resolution

The server auto-detects the project root by:
1. Git repository root (`git rev-parse --show-toplevel`)
2. Walking up looking for `.agent-brain/` directory
3. Walking up looking for `.claude/` directory
4. Walking up looking for `pyproject.toml`
5. Falling back to current working directory

### Port Allocation

By default, `auto_port` is enabled and the server finds an available port in the 8000-8100 range. Override with `--port` or disable auto-port in `config.json`.

### Stale State Cleanup

If a previous server died without cleanup, `agent-brain start` automatically detects and cleans up stale state before starting.

### Registry

Each started server is registered in the global registry (`~/.local/state/agent-brain/registry.json`) so `agent-brain list` can discover all instances.

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
   cat .agent-brain/logs/server.log
   cat .agent-brain/logs/server.err
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
