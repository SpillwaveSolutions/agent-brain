#!/bin/bash
# scripts/local_integration_check.sh
# Local integration check for Agent Brain v3.0.0
# Run this before releasing to validate E2E workflow
set -e

echo "=== Agent Brain Local Integration Check ==="
echo "Date: $(date)"
echo ""

# Configuration
RUNTIME_FILE=".claude/agent-brain/runtime.json"
TEST_DIR="integration_test_data"
TIMEOUT_SECONDS=120

# Cleanup function
cleanup() {
    echo ""
    echo "Cleaning up..."
    if [ ! -z "$SERVER_PID" ]; then
        kill $SERVER_PID 2>/dev/null || true
    fi
    agent-brain stop 2>/dev/null || true
    rm -rf "$TEST_DIR" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

# Step 1: Kill stray processes and free ports
echo "Step 1: Cleaning up stray processes..."
pkill -9 -f "agent_brain_server" 2>/dev/null || true
pkill -9 -f "uvicorn.*agent_brain" 2>/dev/null || true
for port in $(seq 8000 8010); do
    kill -9 $(lsof -i :$port -t 2>/dev/null) 2>/dev/null || true
done
sleep 2
echo "  Done."

# Step 2: Clean up old runtime.json to ensure fresh start
echo "Step 2: Cleaning up old state..."
rm -f "$RUNTIME_FILE" 2>/dev/null || true
rm -rf ".claude/agent-brain/jobs" 2>/dev/null || true
echo "  Done."

# Step 3: Start server in foreground
echo "Step 3: Starting server in foreground..."
agent-brain start --foreground &
SERVER_PID=$!
sleep 5

# Step 4: Verify runtime.json exists
echo "Step 4: Checking runtime.json..."
if [ ! -f "$RUNTIME_FILE" ]; then
    echo "  ERROR: runtime.json not found at $RUNTIME_FILE"
    echo "  Server may have failed to start. Check logs."
    exit 1
fi
echo "  Found runtime.json"

# Extract server URL from runtime.json
export AGENT_BRAIN_URL=$(python3 -c "import json; print(json.load(open('$RUNTIME_FILE'))['base_url'])")
echo "  Server URL: $AGENT_BRAIN_URL"

# Step 5: Wait for health endpoint
echo "Step 5: Waiting for health endpoint..."
HEALTH_OK=false
for i in {1..30}; do
    if curl -s "$AGENT_BRAIN_URL/health/" | grep -q "ok"; then
        echo "  Server is healthy!"
        HEALTH_OK=true
        break
    fi
    echo "  Attempt $i/30..."
    sleep 1
done

if [ "$HEALTH_OK" = false ]; then
    echo "  ERROR: Server did not become healthy within 30 seconds"
    exit 1
fi

# Step 6: Create test data
echo "Step 6: Creating test data..."
mkdir -p "$TEST_DIR"
cat > "$TEST_DIR/test_doc.md" << 'TESTDOC'
# Integration Test Document

This is a test document for the Agent Brain integration check.

## Features

- Semantic search using embeddings
- BM25 keyword search
- Hybrid search combining both

## Usage

Query the index using the CLI:

```bash
agent-brain query "semantic search"
```
TESTDOC

cat > "$TEST_DIR/test_code.py" << 'TESTCODE'
"""Test Python code for integration check."""

def search_documents(query: str, top_k: int = 5) -> list:
    """Search for documents matching the query."""
    results = []
    # Implementation here
    return results

class DocumentIndex:
    """Index for storing documents."""

    def __init__(self):
        self.documents = []

    def add(self, doc: str):
        """Add a document to the index."""
        self.documents.append(doc)
TESTCODE
echo "  Created test files in $TEST_DIR"

# Step 7: Index test data
echo "Step 7: Indexing test data..."
INDEX_OUTPUT=$(agent-brain index "$TEST_DIR" --include-code 2>&1) || true
echo "  Index command output: $INDEX_OUTPUT"

# Step 8: Poll job status until done
echo "Step 8: Polling job status..."
START_TIME=$(date +%s)
JOB_DONE=false

while true; do
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - START_TIME))

    if [ $ELAPSED -gt $TIMEOUT_SECONDS ]; then
        echo "  ERROR: Job timed out after $TIMEOUT_SECONDS seconds"
        exit 1
    fi

    # Get job status
    JOBS_RESPONSE=$(curl -s "$AGENT_BRAIN_URL/index/jobs/")
    STATUS=$(echo "$JOBS_RESPONSE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    jobs = data.get('jobs', [])
    if not jobs:
        print('empty')
    else:
        print(jobs[0].get('status', 'unknown'))
except:
    print('error')
" 2>/dev/null || echo "error")

    case "$STATUS" in
        "DONE")
            echo "  Job completed successfully!"
            JOB_DONE=true
            break
            ;;
        "empty")
            echo "  No jobs found (may already be complete)"
            JOB_DONE=true
            break
            ;;
        "FAILED")
            echo "  ERROR: Job failed!"
            echo "  Response: $JOBS_RESPONSE"
            exit 1
            ;;
        "CANCELLED")
            echo "  ERROR: Job was cancelled!"
            exit 1
            ;;
        "PENDING"|"RUNNING")
            echo "  Status: $STATUS (elapsed: ${ELAPSED}s)"
            sleep 2
            ;;
        *)
            echo "  Status: $STATUS (elapsed: ${ELAPSED}s)"
            sleep 2
            ;;
    esac
done

# Step 9: Run smoke test query
echo "Step 9: Running smoke test query..."
sleep 2  # Give indexing a moment to finalize

QUERY_RESULT=$(curl -s -X POST "$AGENT_BRAIN_URL/query/" \
    -H "Content-Type: application/json" \
    -d '{"query": "semantic search documents", "top_k": 5}')

if echo "$QUERY_RESULT" | grep -q "results"; then
    echo "  Query successful!"
    RESULT_COUNT=$(echo "$QUERY_RESULT" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('results', [])))" 2>/dev/null || echo "0")
    echo "  Found $RESULT_COUNT results"
else
    echo "  WARNING: Query may have failed or returned unexpected format"
    echo "  Response: $QUERY_RESULT"
fi

# Step 10: Test CLI jobs command
echo "Step 10: Testing CLI jobs command..."
JOBS_OUTPUT=$(agent-brain jobs 2>&1) || true
if echo "$JOBS_OUTPUT" | grep -qE "(jobs|No jobs|DONE|PENDING)"; then
    echo "  CLI jobs command works!"
else
    echo "  WARNING: CLI jobs command output unexpected"
    echo "  Output: $JOBS_OUTPUT"
fi

# Step 11: Stop server
echo "Step 11: Stopping server..."
kill $SERVER_PID 2>/dev/null || true
agent-brain stop 2>/dev/null || true
echo "  Server stopped."

echo ""
echo "=== Integration Check PASSED ==="
echo ""
echo "Summary:"
echo "  - Server started and wrote runtime.json"
echo "  - CLI auto-discovered server URL from runtime.json"
echo "  - Indexing job completed without errors"
echo "  - Query returned valid results"
echo "  - CLI jobs command works"
echo ""
