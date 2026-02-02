# Integration Guide

Patterns for integrating Agent Brain into scripts, applications, and CI/CD pipelines.

## Contents

- [CLI Scripting](#cli-scripting)
- [Python API Integration](#python-api-integration)
- [CI/CD Integration](#cicd-integration)
- [Multi-Project Workflow](#multi-project-workflow)

---

## CLI Scripting

```bash
# Basic query with JSON output
RESULT=$(agent-brain query "$QUERY" --mode hybrid --json)
echo "$RESULT" | jq '.results[0].text'

# Check if results found
if agent-brain query "search term" --mode bm25 --threshold 0.1 > /dev/null 2>&1; then
    echo "Found matching documents"
fi

# Iterate over results
agent-brain query "error handling" --json | jq -r '.results[].source'
```

---

## Python API Integration

```python
import json
import subprocess
from pathlib import Path
import requests

def get_server_url():
    """Get server URL from runtime.json or default."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True
        )
        project_root = Path(result.stdout.strip())
        runtime_path = project_root / ".claude" / "doc-serve" / "runtime.json"
        if runtime_path.exists():
            state = json.loads(runtime_path.read_text())
            return state.get("base_url", "http://localhost:8000")
    except Exception:
        pass
    return "http://localhost:8000"


def query_docs(query: str, mode: str = "hybrid", top_k: int = 5) -> list:
    """Query Agent Brain and return results."""
    server_url = get_server_url()
    response = requests.post(
        f'{server_url}/query/',
        json={'query': query, 'mode': mode, 'top_k': top_k}
    )
    response.raise_for_status()
    return response.json().get('results', [])


# Usage
results = query_docs("authentication guide", mode="hybrid")
for r in results:
    print(f"{r['source']}: {r['score']:.2f}")
```

---

## CI/CD Integration

```bash
#!/bin/bash
# Documentation validation in CI pipeline

set -e

# Initialize and start server
agent-brain init
agent-brain start --daemon

# Wait for server readiness
for i in {1..10}; do
    if agent-brain status > /dev/null 2>&1; then
        break
    fi
    sleep 1
done

# Index documentation
agent-brain index ./docs

# Run validation queries
echo "Checking for deprecated features..."
if agent-brain query "deprecated" --mode bm25 --threshold 0.1 --json | jq -e '.total_results > 0' > /dev/null; then
    echo "Warning: Found deprecated content"
fi

echo "Verifying API documentation..."
agent-brain query "API endpoint" --mode hybrid --threshold 0.5

# Cleanup
agent-brain stop

echo "Documentation validation complete"
```

---

## Multi-Project Workflow

```bash
# Work with multiple projects simultaneously
cd /project-a && agent-brain start --daemon  # Auto-port (e.g., 54321)
cd /project-b && agent-brain start --daemon  # Different port (e.g., 54322)

# List all running instances
agent-brain list
# Instance   Project          Port   Status
# a1b2c3d4   /project-a       54321  running
# e5f6g7h8   /project-b       54322  running

# Query specific project (from its directory)
cd /project-a && agent-brain query "auth module"
cd /project-b && agent-brain query "database schema"

# Cleanup
cd /project-a && agent-brain stop
cd /project-b && agent-brain stop
```

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DOC_SERVE_URL` | Override server URL | Auto-discovered |
| `OPENAI_API_KEY` | Required for vector/hybrid modes | - |
| `ANTHROPIC_API_KEY` | Optional for summarization | - |
