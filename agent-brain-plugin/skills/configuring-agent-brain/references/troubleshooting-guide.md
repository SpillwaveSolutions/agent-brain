---
last_validated: 2026-03-16
---

# Agent Brain Troubleshooting Guide

## Overview

This guide covers common issues and their solutions when using Agent Brain for document indexing and search.

## Quick Diagnostics

Run these commands to diagnose common issues:

```bash
# Check server status
agent-brain status

# Check API keys are set
echo "OpenAI: ${OPENAI_API_KEY:+SET}"
echo "Anthropic: ${ANTHROPIC_API_KEY:+SET}"

# Check Python environment
which python
python --version

# Test basic connectivity
agent-brain query "test" --mode bm25
```

---

## Server Issues

### Server Won't Start

**Symptoms:**
- `agent-brain start` fails
- Error messages about missing modules
- Port already in use errors

**Solutions:**

**Module Import Errors:**
```bash
# Reinstall packages
pip install --force-reinstall agent-brain-rag agent-brain-cli
```

**Port Already in Use:**
```bash
# Find what's using the port
lsof -i :8000

# Kill the process
kill -9 <PID>

# Or use auto-port (recommended)
agent-brain start
```

**Permission Errors:**
```bash
# Check directory permissions
ls -la .agent-brain/

# Fix permissions
chmod 755 .agent-brain/
```

### Connection Refused Errors

**Symptoms:**
- Commands fail with connection errors
- "Unable to connect to server" messages

**Solutions:**

**Start the Server:**
```bash
agent-brain start
agent-brain status
```

**Check Runtime File:**
```bash
cat .agent-brain/runtime.json | jq '.base_url'
```

**Override URL if Needed:**
```bash
export DOC_SERVE_URL="http://localhost:49321"
agent-brain status
```

### PostgreSQL Backend Issues

**Connection refused (PostgreSQL):**

- Confirm the container is running:
```bash
docker compose -f docker-compose.postgres.yml ps
```
- Check readiness:
```bash
docker compose -f docker-compose.postgres.yml exec postgres \
  pg_isready -U agent_brain -d agent_brain
```

**pgvector extension missing:**

- Use the pgvector image (`pgvector/pgvector:pg16`).
- If using another image, install the pgvector extension before start.

**Pool exhaustion / too many connections:**

- Increase `pool_size` and `pool_max_overflow` under `storage.postgres`.
- Ensure PostgreSQL `max_connections` is high enough for your workload.

**Embedding dimension mismatch:**

- If you change embedding models, reset and re-index:
```bash
agent-brain reset --yes
agent-brain index /path/to/docs
```

### Stale Server State

**Symptoms:**
- `runtime.json` exists but server not responding
- Previous server crashed without cleanup

**Solutions:**

```bash
# Manual cleanup
rm .agent-brain/runtime.json
rm .agent-brain/lock.json
rm .agent-brain/pid

# Start fresh
agent-brain start
```

---

## API Key Issues

### Missing OpenAI API Key

**Symptoms:**
- Hybrid/vector queries fail with authentication errors
- Error: "No API key found for OpenAI"
- BM25 works but hybrid/vector don't

**Solutions:**

**Set API Key:**
```bash
export OPENAI_API_KEY="sk-proj-your-key-here"
```

**Persistent Setup:**
```bash
echo 'export OPENAI_API_KEY="sk-proj-..."' >> ~/.bashrc
source ~/.bashrc
```

**Get API Key:**
- Visit: https://platform.openai.com/account/api-keys

### Invalid API Key Errors

**Symptoms:**
- Authentication failed messages
- 401 Unauthorized responses

**Solutions:**

**Test Key Validity:**
```bash
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

**Verify Key Format:**
```bash
# Should start with sk-proj- or sk-
echo $OPENAI_API_KEY | head -c 10
```

**Check Account Credits:**
- Visit: https://platform.openai.com/account/usage
- Ensure account has credits

**Regenerate Key if Needed:**
- Visit: https://platform.openai.com/account/api-keys
- Delete old key, create new one

---

## Search Issues

### No Documents Indexed

**Symptoms:**
- `agent-brain status` shows 0 documents
- All queries return empty results

**Solutions:**

**Check Status:**
```bash
agent-brain status
# Should show: Documents: > 0
```

**Run Indexing:**
```bash
agent-brain index /path/to/your/docs
# Wait for completion
```

**Verify Document Path:**
```bash
ls -la /path/to/your/docs
# Should contain .md, .txt, .pdf files
```

**Check Supported Formats:**
- Supported: Markdown (.md), Text (.txt), PDF (.pdf), Code files
- Not Supported: Word docs (.docx), images

### No Search Results Found

**Symptoms:**
- Queries return empty results
- Documents are indexed but no matches

**Solutions:**

**Lower Threshold:**
```bash
# Default is 0.7, try lower values
agent-brain query "your search" --threshold 0.3
```

**Try Different Modes:**
```bash
# BM25 for exact matches
agent-brain query "exact term" --mode bm25 --threshold 0.1

# Vector for semantic search
agent-brain query "concept" --mode vector --threshold 0.5
```

**Verify Content Exists:**
```bash
# Search for common words
agent-brain query "the" --mode bm25 --threshold 0.01
```

### BM25 Index Not Ready

**Symptoms:**
- BM25 queries fail with "index not initialized"
- Hybrid queries fail but vector works

**Solutions:**

**Wait for Indexing:**
```bash
agent-brain status
# Wait until indexing shows complete
```

**Re-index:**
```bash
agent-brain reset --yes
agent-brain index /path/to/docs
```

---

## Performance Issues

### Slow Query Performance

**Symptoms:**
- Queries take longer than expected
- Hybrid/vector queries > 2 seconds

**Solutions:**

**Use BM25 for Speed:**
```bash
# Fastest option, no API calls
agent-brain query "exact terms" --mode bm25
```

**Reduce Result Count:**
```bash
agent-brain query "search" --top-k 3
```

**Check Network:**
```bash
# Test OpenAI connectivity
curl -H "Authorization: Bearer $OPENAI_API_KEY" \
  https://api.openai.com/v1/models
```

### Memory Issues

**Symptoms:**
- Server crashes with out of memory
- System becomes unresponsive

**Solutions:**

**Restart with Clean State:**
```bash
agent-brain stop
agent-brain reset --yes
agent-brain start
agent-brain index /path/to/docs
```

**Monitor Resources:**
```bash
ps aux | grep agent-brain
```

---

## Installation Issues

### Command Not Found

**Symptoms:**
- `agent-brain: command not found`

**Solutions:**

**Check Installation:**
```bash
pip list | grep agent-brain
```

**Add to PATH:**
```bash
export PATH="$HOME/.local/bin:$PATH"
```

**Reinstall:**
```bash
pip install --force-reinstall agent-brain-cli
```

### Module Not Found

**Symptoms:**
- `ModuleNotFoundError` when running

**Solutions:**

**Reinstall Packages:**
```bash
pip install --force-reinstall agent-brain-rag agent-brain-cli
```

**Check Python Environment:**
```bash
which python
pip list | grep agent-brain
```

---

## File Permission Issues

**Symptoms:**
- Cannot read documents during indexing
- Permission denied errors

**Solutions:**

**Check Permissions:**
```bash
ls -la /path/to/docs
chmod 644 /path/to/docs/*.md
```

**Check Index Directory:**
```bash
ls -la .agent-brain/
chmod 755 .agent-brain/
```

---

## Diagnostic Commands Reference

### Full System Check

```bash
# 1. Check installation
agent-brain --version

# 2. Check API keys
echo "OpenAI: ${OPENAI_API_KEY:+SET}"
echo "Anthropic: ${ANTHROPIC_API_KEY:+SET}"

# 3. Check server status
agent-brain status

# 4. Check runtime file
cat .agent-brain/runtime.json 2>/dev/null || echo "No runtime file"

# 5. Test BM25 (no API needed)
agent-brain query "test" --mode bm25 --threshold 0.01

# 6. Test vector (needs API)
agent-brain query "test" --mode vector --threshold 0.3
```

### Environment Check

```bash
# Python environment
which python
python --version

# Package versions
pip show agent-brain-rag
pip show agent-brain-cli

# Network connectivity
ping -c 3 api.openai.com
```

---

## Getting Help

If these solutions don't resolve your issue:

1. **Run diagnostics** and capture output
2. **Include error messages** (full text)
3. **Describe your setup**: OS, Python version, installation method
4. **Report issues**: https://github.com/SpillwaveSolutions/agent-brain-plugin/issues

---

## File Watcher Issues (v8.0+)

### Watcher Not Triggering Re-index

**Symptoms:**
- Files changed but no re-index job appears
- `agent-brain jobs` shows no auto-triggered jobs

**Solutions:**

```bash
# Verify folder has watch mode enabled
agent-brain folders list
# Look for "Watch: auto" column

# Re-add folder with watch mode
agent-brain folders add ./src --watch auto --include-code

# Check debounce interval (default 30s, changes within window are batched)
# Lower debounce for faster response
agent-brain folders add ./src --watch auto --debounce 10
```

### Watcher Ignoring Certain Files

The watcher excludes: `.git/`, `node_modules/`, `__pycache__/`, `dist/`, `build/`, `.next/`, `.nuxt/`, `coverage/`, `htmlcov/`

These directories are intentionally excluded to avoid indexing build artifacts.

---

## Embedding Cache Issues (v8.0+)

### Low Cache Hit Rate

**Symptoms:**
- `agent-brain cache status` shows low hit rate
- Re-indexing is slow despite no content changes

**Solutions:**

```bash
# Check cache status
agent-brain cache status

# If switching embedding providers, clear old cache
agent-brain cache clear --yes

# Re-index to rebuild cache
agent-brain index /path/to/docs
```

### Cache Disk Space

```bash
# Check cache size
agent-brain cache status --json | jq '.size_bytes'

# Clear if too large
agent-brain cache clear --yes
```

**Configuration:** Set `EMBEDDING_CACHE_MAX_DISK_MB` (default: 500MB) to limit disk usage.

---

## Multi-Runtime Install Issues (v9.0+)

### Install-Agent Not Finding Plugin Directory

**Symptoms:**
- `agent-brain install-agent --agent claude` fails with "plugin directory not found"

**Solutions:**

```bash
# Ensure agent-brain-plugin directory exists
ls agent-brain-plugin/commands/

# Or install from an existing Claude plugin installation
ls ~/.claude/plugins/agent-brain/commands/
```

### Uninstall Not Removing Files

```bash
# Uninstall for specific runtime
agent-brain uninstall --agent claude

# Manual cleanup if needed
rm -rf .claude/plugins/agent-brain
```

---

## Prevention Tips

- Always verify `agent-brain status` before searching
- Keep API keys secure and never commit them
- Run `agent-brain stop` when done to free resources
- Use BM25 mode when you don't need semantic search
- Lower threshold values when getting no results
- Re-index after major document changes
- Use `agent-brain cache status` to monitor embedding cache health
- Enable file watcher (`--watch auto`) for automatic re-indexing
