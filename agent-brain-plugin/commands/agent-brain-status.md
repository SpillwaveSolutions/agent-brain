---
name: agent-brain-status
description: Show Agent Brain server status (port, documents, health)
parameters:
  - name: json
    description: Output in JSON format
    required: false
    default: false
skills:
  - using-agent-brain
---

# Agent Brain Status

## Purpose

Displays the current status of the Agent Brain server, including:
- Server health and connectivity
- Port and URL information
- Document count in the index
- Indexing status (idle, running, completed)
- Instance mode (project or shared)

Use this command to verify the server is running before performing searches.

## Usage

```
/agent-brain:agent-brain-status [--json]
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| json | No | false | Output in JSON format for scripting |

## Execution

### Basic Status Check

```bash
agent-brain status
```

### JSON Output

```bash
agent-brain status --json
```

## Output

### Human-Readable Format

```
Agent Brain Status
==================

Server:     http://127.0.0.1:49321
Status:     healthy
Mode:       project
Project:    my-project

Index:
  Documents:  142
  Status:     idle
  Last indexed: 2026-01-31 10:30:00

Health:
  API:        OK
  Vector DB:  OK
  BM25 Index: OK
```

### JSON Format

```json
{
  "server": {
    "url": "http://127.0.0.1:49321",
    "port": 49321,
    "status": "healthy",
    "mode": "project",
    "project_id": "my-project"
  },
  "index": {
    "document_count": 142,
    "status": "idle",
    "last_indexed": "2026-01-31T10:30:00Z"
  },
  "health": {
    "api": "ok",
    "vector_db": "ok",
    "bm25_index": "ok"
  }
}
```

### Status Indicators

| Status | Meaning |
|--------|---------|
| `healthy` | Server running and responsive |
| `unhealthy` | Server running but issues detected |
| `not_running` | Server not started |
| `indexing` | Currently indexing documents |
| `idle` | Ready for queries |

## Error Handling

### Server Not Running

```
Error: Agent Brain server is not running

To start the server:
  agent-brain start
```

**Resolution**: Start the server:
```bash
agent-brain start
```

### Connection Refused

```
Error: Could not connect to server at http://127.0.0.1:8000
Connection refused
```

**Resolution**:
1. Check if server is running: `ps aux | grep agent-brain`
2. Start the server: `agent-brain start`
3. Check if port is blocked by firewall

### Runtime File Missing

```
Warning: No runtime.json found
Using default URL: http://127.0.0.1:8000
```

**Resolution**: Initialize the project:
```bash
agent-brain init
agent-brain start
```

### Health Check Failed

```
Status: unhealthy

Issues detected:
  - Vector DB: connection failed
  - BM25 Index: not initialized
```

**Resolution**:
1. Check ChromaDB is accessible
2. Re-index documents: `agent-brain index /path/to/docs`
3. Restart server: `agent-brain stop && agent-brain start`

## Use Cases

### Before Searching

Always check status before performing searches:

```bash
# Check server is ready
agent-brain status

# If healthy and documents indexed, proceed with search
agent-brain query "search term" --mode hybrid
```

### Troubleshooting

Use JSON output for scripting and diagnostics:

```bash
# Check document count
agent-brain status --json | jq '.index.document_count'

# Check server port
agent-brain status --json | jq '.server.port'
```

### CI/CD Integration

```bash
# Wait for server to be healthy
until agent-brain status --json | jq -e '.server.status == "healthy"'; do
  sleep 1
done
```

## Related Commands

| Command | Description |
|---------|-------------|
| `/agent-brain:agent-brain-start` | Start the server |
| `/agent-brain:agent-brain-stop` | Stop the server |
| `/agent-brain:agent-brain-list` | List all running instances |
