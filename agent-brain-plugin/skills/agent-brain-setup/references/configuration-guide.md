# Agent Brain Configuration Guide

## Overview

This guide covers all configuration options for Agent Brain, including API keys, environment variables, and project settings.

## API Keys

### OpenAI API Key (Required)

The OpenAI API key is **required** for vector and hybrid search modes. Without it, only BM25 keyword search will work.

**Set as Environment Variable:**
```bash
export OPENAI_API_KEY="sk-proj-..."
```

**Persistent Configuration (Shell Profile):**
```bash
# For Bash
echo 'export OPENAI_API_KEY="sk-proj-..."' >> ~/.bashrc
source ~/.bashrc

# For Zsh
echo 'export OPENAI_API_KEY="sk-proj-..."' >> ~/.zshrc
source ~/.zshrc
```

**Get Your API Key:**
1. Go to https://platform.openai.com/account/api-keys
2. Click "Create new secret key"
3. Copy the key (starts with `sk-proj-` or `sk-`)
4. Store securely - you cannot view it again

**Verify Key is Set:**
```bash
echo "OpenAI key: ${OPENAI_API_KEY:+CONFIGURED}"
```

**Test Key is Valid:**
```bash
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json"
```

### Anthropic API Key (Optional)

The Anthropic API key enables code summarization features but is not required for basic functionality.

**Set as Environment Variable:**
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

**Get Your API Key:**
1. Go to https://console.anthropic.com/
2. Create a new API key
3. Copy and store securely

**Verify Key is Set:**
```bash
echo "Anthropic key: ${ANTHROPIC_API_KEY:+CONFIGURED}"
```

## Environment Variables

### Complete Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes* | - | OpenAI API key for embeddings |
| `ANTHROPIC_API_KEY` | No | - | Anthropic key for summarization |
| `DOC_SERVE_URL` | No | Auto-detect | Override server URL |
| `DOC_SERVE_STATE_DIR` | No | `.claude/agent-brain` | State directory path |
| `DOC_SERVE_MODE` | No | `project` | Instance mode: `project` or `shared` |
| `EMBEDDING_MODEL` | No | `text-embedding-3-large` | OpenAI embedding model |
| `CLAUDE_MODEL` | `claude-haiku-4-5-20251001` | Claude model for summaries |
| `API_HOST` | No | `127.0.0.1` | Server bind address |
| `API_PORT` | No | `8000` | Server port (legacy mode) |
| `DEBUG` | No | `false` | Enable debug logging |

*Required for vector/hybrid search; BM25-only works without it.

### Setting Multiple Variables

**Temporary (Current Session):**
```bash
export OPENAI_API_KEY="sk-proj-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export DEBUG=true
```

**Persistent (Shell Profile):**
```bash
# Add to ~/.bashrc or ~/.zshrc
cat >> ~/.bashrc << 'EOF'
export OPENAI_API_KEY="sk-proj-..."
export ANTHROPIC_API_KEY="sk-ant-..."
EOF
source ~/.bashrc
```

### Using a .env File

Create a `.env` file in your project root (add to `.gitignore`!):

```bash
# .env file
OPENAI_API_KEY=sk-proj-...
ANTHROPIC_API_KEY=sk-ant-...
DEBUG=false
```

**Load .env file:**
```bash
# Manual loading
export $(cat .env | xargs)

# Or use direnv for automatic loading
```

## Project Configuration

### Initialize Project

```bash
cd /path/to/your/project
agent-brain init
```

This creates `.claude/agent-brain/` with:

```
.claude/agent-brain/
├── config.json      # Project settings
└── runtime.json     # Server state (created on start)
```

### config.json

The project configuration file:

```json
{
  "mode": "project",
  "project_id": "my-project",
  "state_dir": ".claude/agent-brain",
  "default_search_mode": "hybrid",
  "default_threshold": 0.7,
  "default_top_k": 5
}
```

### runtime.json

Created when server starts (do not edit manually):

```json
{
  "mode": "project",
  "port": 49321,
  "base_url": "http://127.0.0.1:49321",
  "pid": 12345,
  "instance_id": "abc123",
  "project_id": "my-project",
  "started_at": "2026-01-27T10:30:00Z"
}
```

## Server Configuration

### Start Server

```bash
# Default: auto-port allocation
agent-brain start --daemon

# Specific port (legacy mode)
agent-brain start --port 8080
```

### Configuration Precedence

Settings are resolved in order (first wins):

1. Command-line flags
2. Environment variables
3. Project config (`.claude/agent-brain/config.json`)
4. Global config (`~/.agent-brain/config.json`)
5. Built-in defaults

### Multi-Instance Mode

Each project gets its own isolated server:

```bash
# Project A
cd /path/to/project-a && agent-brain start --daemon
# Started on port 49321

# Project B
cd /path/to/project-b && agent-brain start --daemon
# Started on port 49322 (no conflict)
```

List all running instances:
```bash
agent-brain list
```

## Search Configuration

### Default Search Mode

Set via environment:
```bash
export DOC_SERVE_DEFAULT_MODE="hybrid"
```

Or command line:
```bash
agent-brain query "search" --mode hybrid
```

### Threshold Configuration

Default threshold is 0.7 (70% similarity).

**Lower threshold for more results:**
```bash
agent-brain query "search" --threshold 0.3
```

**Higher threshold for precision:**
```bash
agent-brain query "search" --threshold 0.9
```

### Hybrid Alpha Configuration

Controls vector vs BM25 balance (0.0-1.0):

```bash
# More semantic (80% vector)
agent-brain query "search" --alpha 0.8

# More keyword (20% vector)
agent-brain query "search" --alpha 0.2

# Balanced (default)
agent-brain query "search" --alpha 0.5
```

## Security Best Practices

### Never Commit API Keys

Add to `.gitignore`:
```
.env
.env.local
.env.*.local
secrets.json
```

### Use Environment Variables

Always use environment variables for API keys, not config files.

### Rotate Keys Periodically

Regenerate API keys periodically and update configurations.

### Restrict Key Permissions

Use project-scoped OpenAI keys when possible.

## Troubleshooting Configuration

### Issue: API Key Not Working

```bash
# Verify key format
echo $OPENAI_API_KEY | head -c 10
# Should start with sk-proj- or sk-

# Test API directly
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

### Issue: Wrong Server URL

```bash
# Check runtime.json for actual port
cat .claude/agent-brain/runtime.json | jq '.base_url'

# Override if needed
export DOC_SERVE_URL="http://127.0.0.1:49321"
```

### Issue: Configuration Not Loading

```bash
# Check config file exists
ls -la .claude/agent-brain/config.json

# Verify JSON is valid
cat .claude/agent-brain/config.json | jq .
```

## Next Steps

After configuration:
1. Start server: `agent-brain start --daemon`
2. Index documents: `agent-brain index /path/to/docs`
3. Search: `agent-brain query "your search"`
