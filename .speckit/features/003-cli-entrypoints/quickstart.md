# Quickstart: CLI Entry Points Installation

**Feature**: 003-cli-entrypoints
**Prerequisites**: Python 3.10+, pip or Poetry

## Overview

This guide shows how to install the Doc-Serve CLI tools so they're available directly from your terminal.

## Installation Options

### Option 1: Using pip (Recommended for most users)

```bash
# From the project root directory

# Install doc-svr-ctl (CLI tool)
pip install -e ./doc-svr-ctl

# Install doc-serve-server (API server)
pip install -e ./doc-serve-server
```

### Option 2: Using Poetry (For development)

```bash
# Install doc-svr-ctl
cd doc-svr-ctl
poetry install
cd ..

# Install doc-serve-server
cd doc-serve-server
poetry install
cd ..
```

## Verification

After installation, verify the commands are available:

```bash
# Check doc-svr-ctl
doc-svr-ctl --help
doc-svr-ctl --version

# Check doc-serve (starts the server)
doc-serve
# Press Ctrl+C to stop
```

## Available Commands

### doc-svr-ctl

```bash
doc-svr-ctl status              # Check server health
doc-svr-ctl query "your query"  # Search indexed documents
doc-svr-ctl index ./docs        # Index documents from a directory
doc-svr-ctl reset --yes         # Clear all indexed documents
```

### doc-serve

```bash
doc-serve                       # Start the API server
# Server runs at http://127.0.0.1:8000 by default
# API docs at http://127.0.0.1:8000/docs
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DOC_SERVE_URL` | `http://127.0.0.1:8000` | Server URL for CLI |
| `API_HOST` | `127.0.0.1` | Server bind host |
| `API_PORT` | `8000` | Server bind port |
| `DEBUG` | `false` | Enable debug mode |

## Troubleshooting

### Command not found after installation

Ensure your Python environment's `bin` directory is in your PATH:

```bash
# Check where pip installs scripts
pip show doc-svr-ctl | grep Location

# Or use pip's script location directly
python -m site --user-base
# Add {output}/bin to your PATH
```

### Poetry environment not activated

If using Poetry, either activate the environment or use `poetry run`:

```bash
# Option 1: Activate environment
poetry shell
doc-svr-ctl --help

# Option 2: Use poetry run
poetry run doc-svr-ctl --help
```

### Server won't start - port in use

```bash
# Check what's using port 8000
lsof -i :8000

# Use a different port
API_PORT=8001 doc-serve
```
