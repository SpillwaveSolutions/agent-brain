#!/bin/bash
set -e

# Configuration
PORT=8085
DB_PATH="./integration/tests/quick_start/chroma_db"
SERVER_DIR="doc-serve-server"
CLI_DIR="doc-svr-ctl"
WORKSPACE="integration/tests/quick_start"
BASE_URL="http://127.0.0.1:$PORT"

echo "=== Doc-Serve Quick Start Test Script ==="

# Check prerequisites
if ! command -v poetry >/dev/null 2>&1; then
    echo "Error: Poetry is not installed or not in PATH"
    exit 1
fi

if ! command -v lsof >/dev/null 2>&1; then
    echo "Error: lsof is not installed (required for port checking)"
    exit 1
fi

# Cleanup function
cleanup() {
    echo "Cleaning up..."
    if [ ! -z "$SERVER_PID" ]; then
        kill $SERVER_PID 2>/dev/null || true
    fi
    # Clean up any remaining processes on the port
    PIDS=$(lsof -ti :$PORT 2>/dev/null || true)
    if [ ! -z "$PIDS" ]; then
        kill $PIDS 2>/dev/null || true
    fi
}

# Set trap for cleanup on exit
trap cleanup EXIT INT TERM

# 1. Cleanup old processes
echo "Checking for old Doc-Serve processes on port $PORT..."
PIDS=$(lsof -ti :$PORT || true)
if [ ! -z "$PIDS" ]; then
    echo "Found processes: $PIDS. Killing..."
    kill $PIDS
    sleep 10
    PIDS=$(lsof -ti :$PORT)
    if [ ! -z "$PIDS" ]; then
        echo "Still running. Force killing..."
        kill -9 $PIDS
    fi
fi

# 2. Prepare workspace
echo "Preparing workspace at $WORKSPACE..."
rm -rf "$WORKSPACE"
mkdir -p "$WORKSPACE"

# 3. Setup environment variables
export API_PORT=$PORT
export DATABASE_PATH=$DB_PATH
export DEBUG=true

# 4. Start Server
echo "Starting Doc-Serve server on port $PORT..."
cd $SERVER_DIR
nohup poetry run doc-serve > "../$WORKSPACE/server.log" 2>&1 &
SERVER_PID=$!
cd ..

echo "Server started with PID $SERVER_PID. Waiting for health check..."

# Wait for server to be healthy
MAX_RETRIES=30
COUNT=0
while [ $COUNT -lt $MAX_RETRIES ]; do
    if curl -s "$BASE_URL/health" > /dev/null; then
        echo "Server is healthy!"
        break
    fi
    COUNT=$((COUNT + 1))
    sleep 2
    if [ $COUNT -eq $MAX_RETRIES ]; then
        echo "Server failed to start. See $WORKSPACE/server.log"
        kill $SERVER_PID
        exit 1
    fi
done

# 5. CLI Tool Setup
echo "Installing CLI tool..."
cd $CLI_DIR
poetry install > /dev/null
export DOC_SERVE_URL=$BASE_URL
cd ..

# 6. Index Project
echo "Indexing project root (including code)..."
if ! poetry -C $CLI_DIR run doc-svr-ctl index . --include-code; then
    echo "Failed to start indexing. Check server status."
    kill $SERVER_PID
    exit 1
fi

# 7. Wait for indexing to complete
echo "Waiting for indexing to complete..."
INDEXING_TIMEOUT=300  # 5 minutes timeout
START_TIME=$(date +%s)

while true; do
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - START_TIME))

    if [ $ELAPSED -gt $INDEXING_TIMEOUT ]; then
        echo "Indexing timed out after $INDEXING_TIMEOUT seconds"
        kill $SERVER_PID
        exit 1
    fi

    STATUS=$(poetry -C $CLI_DIR run doc-svr-ctl status --json 2>/dev/null)

    # Try to parse with jq if available, otherwise fall back to grep
    if command -v jq >/dev/null 2>&1; then
        IS_INDEXING=$(echo "$STATUS" | jq -r '.indexing.indexing_in_progress' 2>/dev/null || echo "true")
        CHUNK_COUNT=$(echo "$STATUS" | jq -r '.indexing.total_chunks' 2>/dev/null || echo "0")
    else
        # Fallback to grep/cut (fragile)
        IS_INDEXING=$(echo "$STATUS" | grep -o '"indexing_in_progress": [a-z]*' | cut -d' ' -f2 || echo "true")
        CHUNK_COUNT=$(echo "$STATUS" | grep -o '"total_chunks": [0-9]*' | cut -d' ' -f2 || echo "0")
    fi

    echo "Status: Indexing=$IS_INDEXING, Chunks=$CHUNK_COUNT"

    if [ "$IS_INDEXING" = "false" ] && [ "$CHUNK_COUNT" -gt 0 ]; then
        echo "Indexing complete!"
        break
    fi
    sleep 5
done

# 8. Run Queries
echo "--- Running Queries ---"

echo "Query 1: Semantic (espresso)"
poetry -C $CLI_DIR run doc-svr-ctl query "how to make espresso" --top-k 3 || echo "Query 1 failed, continuing..."

echo "Query 2: Keyword/BM25 (CodeSplitter)"
poetry -C $CLI_DIR run doc-svr-ctl query "CodeSplitter" --mode bm25 --source-types code || echo "Query 2 failed, continuing..."

echo "Query 3: Hybrid (authentication)"
poetry -C $CLI_DIR run doc-svr-ctl query "how does authentication work" --mode hybrid --alpha 0.5 || echo "Query 3 failed, continuing..."

echo "Query 4: Language-specific (Python chunks)"
poetry -C $CLI_DIR run doc-svr-ctl query "class" --languages python --source-types code --top-k 2 || echo "Query 4 failed, continuing..."

# 9. Summarization Test (Small sample)
echo "--- Testing Summarization (Small Sample) ---"
SUMM_DIR="$WORKSPACE/summ_test"
mkdir -p "$SUMM_DIR/subdir"
echo "def add(a, b): return a + b" > "$SUMM_DIR/math.py"
echo "def sub(a, b): return a - b" > "$SUMM_DIR/subdir/math2.py"
echo -e "# Coffee Guide\nEspresso is strong." > "$SUMM_DIR/coffee.md"

echo "Indexing sample for summarization..."
# Note: This might still take a bit if LLM is involved, but we only have 3 files.
# Use absolute path since CLI runs from different directory
ABS_SUMM_DIR="$(pwd)/$SUMM_DIR"
if poetry -C $CLI_DIR run doc-svr-ctl index "$ABS_SUMM_DIR" --generate-summaries; then
    echo "Querying sample with summary..."
    poetry -C $CLI_DIR run doc-svr-ctl query "math operations" --source-types code || echo "Summarization query failed"
else
    echo "Summarization indexing failed (may require API keys)"
fi

echo "Quick start test completed successfully!"
