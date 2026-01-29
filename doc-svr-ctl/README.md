# doc-svr-ctl

Command-line interface for managing the Doc-Serve document indexing and search server.

## Installation

```bash
pip install doc-serve-cli
```

## Quick Start

```bash
doc-svr-ctl init          # Initialize project
doc-svr-ctl start         # Start server
doc-svr-ctl index ./docs  # Index documents
doc-svr-ctl query "search term"
```

## Development Installation

```bash
cd doc-svr-ctl
poetry install
```

## Usage

```bash
# Check server status
doc-svr-ctl status

# Search documents
doc-svr-ctl query "how to use python"

# Index documents from a folder
doc-svr-ctl index ./docs

# Reset/clear the index
doc-svr-ctl reset --yes
```

## Configuration

Set the server URL via environment variable:

```bash
export DOC_SERVE_URL=http://localhost:8000
```

Or use the `--url` flag:

```bash
doc-svr-ctl --url http://localhost:8000 status
```

## Commands

| Command | Description |
|---------|-------------|
| `status` | Check server health and indexing status |
| `query` | Search indexed documents |
| `index` | Start indexing documents from a folder |
| `reset` | Clear all indexed documents |

## Options

All commands support:
- `--url` - Server URL (or `DOC_SERVE_URL` env var)
- `--json` - Output as JSON for scripting
