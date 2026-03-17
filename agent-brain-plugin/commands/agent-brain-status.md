---
name: agent-brain-status
description: Show Agent Brain server status (health, documents, cache, watcher)
parameters:
  - name: url
    description: Server URL (default from config or http://127.0.0.1:8000)
    required: false
  - name: json
    description: Output in JSON format
    required: false
    default: false
  - name: verbose
    description: Show additional detail (cache size, memory entries)
    required: false
    default: false
skills:
  - using-agent-brain
---

# Agent Brain Status

## Purpose

Displays the current status of the Agent Brain server, including:
- Server health and version
- Document and chunk counts
- Indexing progress (if in progress)
- Indexed folders list
- File watcher status
- Embedding cache statistics
- Graph index status (if enabled)

Use this command to verify the server is running before performing searches.

## Usage

```
/agent-brain:agent-brain-status [--url <url>] [--json] [--verbose]
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| --url | No | from config or http://127.0.0.1:8000 | Server URL (env: AGENT_BRAIN_URL) |
| --json | No | false | Output in JSON format for scripting |
| --verbose, -v | No | false | Show additional detail (cache size, memory stats) |

## Execution

### Basic Status Check

```bash
agent-brain status
```

### Verbose Status

```bash
agent-brain status --verbose
```

### JSON Output

```bash
agent-brain status --json
```

## Output

### Human-Readable Format

```
          Server Status
           HEALTHY

Metric             Value
Server Version     9.0.0
Total Documents    142
Total Chunks       750
Indexing           Idle
Indexed Folders    ./docs
                   ./src
File Watcher       running (2 watched folder(s))
Embedding Cache    1,200 entries, 85.3% hit rate (1,024 hits, 176 misses)
Graph Index        Enabled - 45 entities, 120 rels
```

### JSON Format

```json
{
  "health": {
    "status": "healthy",
    "message": "Server is running",
    "version": "9.0.0"
  },
  "indexing": {
    "total_documents": 142,
    "total_chunks": 750,
    "indexing_in_progress": false,
    "progress_percent": 0.0,
    "indexed_folders": ["./docs", "./src"],
    "file_watcher": {
      "running": true,
      "watched_folders": 2
    },
    "embedding_cache": {
      "entry_count": 1200,
      "hit_rate": 0.853,
      "hits": 1024,
      "misses": 176
    }
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
