#!/usr/bin/env bash
# ab-setup-check.sh — Agent Brain pre-flight detection
# Usage: bash /path/to/ab-setup-check.sh
# Output: JSON object with current environment state

# Use set -uo pipefail without -e to avoid aborting on tool-not-found
set -uo pipefail

# --- Agent Brain installation ---
AB_VERSION=$(agent-brain --version 2>/dev/null | head -1 | tr -d '\n' || true)
if [ -n "$AB_VERSION" ]; then
  AB_INSTALLED="true"
else
  AB_INSTALLED="false"
fi

# --- Config file detection (XDG + legacy) ---
CONFIG_FILE=""
CONFIG_FOUND="false"
for candidate in ".claude/agent-brain/config.yaml" \
    "${XDG_CONFIG_HOME:-$HOME/.config}/agent-brain/config.yaml" \
    "$HOME/.agent-brain/config.yaml"; do
  if [ -f "$candidate" ]; then
    CONFIG_FILE="$candidate"
    CONFIG_FOUND="true"
    break
  fi
done

# --- Ollama detection ---
OLLAMA_RUNNING="false"
OLLAMA_MODELS="[]"

# Method 1: curl root endpoint
if curl -s --connect-timeout 3 http://localhost:11434/ 2>/dev/null | grep -q "Ollama" 2>/dev/null; then
  OLLAMA_RUNNING="true"
fi

# Method 2: lsof port check (if method 1 failed)
if [ "$OLLAMA_RUNNING" = "false" ]; then
  if lsof -i :11434 -sTCP:LISTEN >/dev/null 2>&1; then
    OLLAMA_RUNNING="true"
  fi
fi

# Method 3: ollama list (if method 1+2 failed)
if [ "$OLLAMA_RUNNING" = "false" ]; then
  if ollama list >/dev/null 2>&1; then
    OLLAMA_RUNNING="true"
  fi
fi

# Collect model names if Ollama is running
if [ "$OLLAMA_RUNNING" = "true" ]; then
  # Build JSON array of model names
  MODELS=$(ollama list 2>/dev/null | tail -n +2 | awk '{print $1}' | \
    python3 -c "import sys,json; print(json.dumps([l.strip() for l in sys.stdin if l.strip()]))" 2>/dev/null || true)
  if [ -n "$MODELS" ]; then
    OLLAMA_MODELS="$MODELS"
  fi
fi

# --- Docker detection ---
DOCKER_AVAILABLE="false"
DOCKER_COMPOSE_AVAILABLE="false"
if docker --version >/dev/null 2>&1; then
  DOCKER_AVAILABLE="true"
fi
if docker compose version >/dev/null 2>&1; then
  DOCKER_COMPOSE_AVAILABLE="true"
fi

# --- Python version ---
PYTHON_VERSION=$(python3 --version 2>/dev/null | cut -d' ' -f2 || true)

# --- API key presence (boolean only — never print key values) ---
if [ -n "${OPENAI_API_KEY:-}" ]; then
  OPENAI_KEY_SET="true"
else
  OPENAI_KEY_SET="false"
fi
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
  ANTHROPIC_KEY_SET="true"
else
  ANTHROPIC_KEY_SET="false"
fi
if [ -n "${GOOGLE_API_KEY:-}" ]; then
  GOOGLE_KEY_SET="true"
else
  GOOGLE_KEY_SET="false"
fi

# --- PostgreSQL port scan (5432-5442) ---
AVAILABLE_POSTGRES_PORT=""
for port in $(seq 5432 5442); do
  if ! lsof -i :"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    AVAILABLE_POSTGRES_PORT=$port
    break
  fi
done

# --- Large directory detection ---
# Check for common cache/dependency directories in current working directory
LARGE_DIRS="[]"
LARGE_DIR_LIST=""
for dir in node_modules .venv venv __pycache__ .git dist build target .next .nuxt coverage .pytest_cache .mypy_cache .tox vendor packages Pods .gradle .m2; do
  if [ -d "$dir" ]; then
    SIZE=$(du -sh "$dir" 2>/dev/null | cut -f1 || echo "?")
    COUNT=$(find "$dir" -type f 2>/dev/null | wc -l | tr -d ' ' || echo "0")
    entry="{\"path\":\"$dir\",\"size\":\"$SIZE\",\"file_count\":$COUNT}"
    if [ -z "$LARGE_DIR_LIST" ]; then
      LARGE_DIR_LIST="$entry"
    else
      LARGE_DIR_LIST="$LARGE_DIR_LIST,$entry"
    fi
  fi
done
if [ -n "$LARGE_DIR_LIST" ]; then
  LARGE_DIRS="[$LARGE_DIR_LIST]"
fi

# --- Output JSON ---
# Construct manually (no jq dependency required for output)
cat <<JSON
{
  "agent_brain_installed": $AB_INSTALLED,
  "agent_brain_version": "$AB_VERSION",
  "config_file_found": $CONFIG_FOUND,
  "config_file_path": "$CONFIG_FILE",
  "ollama_running": $OLLAMA_RUNNING,
  "ollama_models": $OLLAMA_MODELS,
  "docker_available": $DOCKER_AVAILABLE,
  "docker_compose_available": $DOCKER_COMPOSE_AVAILABLE,
  "python_version": "$PYTHON_VERSION",
  "api_keys": {
    "openai": $OPENAI_KEY_SET,
    "anthropic": $ANTHROPIC_KEY_SET,
    "google": $GOOGLE_KEY_SET
  },
  "available_postgres_port": "$AVAILABLE_POSTGRES_PORT",
  "large_dirs": $LARGE_DIRS
}
JSON
