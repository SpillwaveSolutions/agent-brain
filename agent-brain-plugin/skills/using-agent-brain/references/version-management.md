# Agent Brain Version Management

Guide for installing, upgrading, and managing Agent Brain versions.

## Current Version

Resolve the latest version dynamically from PyPI:

```bash
VERSION=$(curl -sf https://pypi.org/pypi/agent-brain-rag/json | python3 -c "import sys,json; print(json.load(sys.stdin)['info']['version'])")
echo "Latest: $VERSION"
```

### Version History

| Version | Release Date | Key Features |
|---------|--------------|--------------|
| 3.0.0 | 2025-02 | Job queue, async indexing, server-side processing |
| 2.0.0 | 2024-12 | Pluggable providers, GraphRAG, multi-instance |
| 1.4.0 | 2024-11 | Graph search mode, multi-mode fusion |
| 1.3.0 | 2024-10 | AST-aware code ingestion |

## Checking Version

```bash
# CLI version
agent-brain --version

# Server package version
python -c "import agent_brain_server; print(agent_brain_server.__version__)"

# Both packages
pip show agent-brain-rag agent-brain-cli
```

## Installing Specific Versions

### Latest Stable (Recommended)

```bash
# Resolve and install latest
VERSION=$(curl -sf https://pypi.org/pypi/agent-brain-rag/json | python3 -c "import sys,json; print(json.load(sys.stdin)['info']['version'])")
pip install agent-brain-rag==$VERSION agent-brain-cli==$VERSION
```

### Specific Version

```bash
# Install exact version (replace $VERSION with desired version)
pip install agent-brain-rag==$VERSION agent-brain-cli==$VERSION
```

### Version Range

```bash
# Compatible with 3.x
pip install "agent-brain-rag>=3.0.0,<4.0.0"

# Minimum version
pip install "agent-brain-rag>=3.0.0"
```

## Listing Available Versions

```bash
# List all available versions
pip index versions agent-brain-rag

# Alternative with pip
pip install agent-brain-rag==  # Shows error with all versions listed
```

## Upgrading

### Upgrade to Latest

```bash
pip install --upgrade agent-brain-rag agent-brain-cli
```

### Upgrade to Specific Version

```bash
# Resolve latest first
VERSION=$(curl -sf https://pypi.org/pypi/agent-brain-rag/json | python3 -c "import sys,json; print(json.load(sys.stdin)['info']['version'])")
pip install --upgrade agent-brain-rag==$VERSION agent-brain-cli==$VERSION
```

### Check for Updates

```bash
# Check if updates are available
pip list --outdated | grep agent-brain
```

## Downgrading

To downgrade to a previous version:

```bash
# Set target version
TARGET_VERSION="X.Y.Z"  # e.g., 2.0.0

# Downgrade to specific version
pip install agent-brain-rag==$TARGET_VERSION agent-brain-cli==$TARGET_VERSION

# Force reinstall if needed
pip install --force-reinstall agent-brain-rag==$TARGET_VERSION
```

### Migration Considerations

When downgrading, be aware of:

1. **Index Compatibility**: Newer indexes may not work with older versions
2. **Configuration**: New config options won't be recognized
3. **Features**: New features won't be available

**Recommended Steps:**
```bash
# 1. Set target version
TARGET_VERSION="X.Y.Z"

# 2. Stop server
agent-brain stop

# 3. Backup configuration
cp -r .claude/agent-brain .claude/agent-brain.backup

# 4. Reset index (if needed)
agent-brain reset --yes

# 5. Downgrade
pip install agent-brain-rag==$TARGET_VERSION agent-brain-cli==$TARGET_VERSION

# 6. Re-index
agent-brain start
agent-brain index /path/to/docs
```

## Version Compatibility

### Package Alignment

Always keep `agent-brain-rag` and `agent-brain-cli` on the same version:

| RAG Version | CLI Version | Compatible |
|-------------|-------------|------------|
| X.Y.Z | X.Y.Z | Yes |
| X.Y.Z | A.B.C | No - versions must match |

### Python Version Compatibility

| Agent Brain | Python |
|-------------|--------|
| 3.x | 3.10, 3.11, 3.12 |
| 2.x | 3.10, 3.11, 3.12 |
| 1.x | 3.10, 3.11 |

### Index Compatibility

Indexes created with one version may not be compatible with another:

| From Version | To Version | Index Compatible |
|--------------|------------|------------------|
| N.x | N+1.0 | Re-index usually required |
| N.x.y | N.x.z | Usually compatible |

## Version Pinning

### In requirements.txt

```text
# Pin to specific version (resolve latest first)
agent-brain-rag==X.Y.Z
agent-brain-cli==X.Y.Z
```

### In pyproject.toml

```toml
[project]
dependencies = [
    "agent-brain-rag>=3.0.0,<4.0.0",
    "agent-brain-cli>=3.0.0,<4.0.0",
]
```

### In Poetry

```toml
[tool.poetry.dependencies]
agent-brain-rag = "^3.0.0"
agent-brain-cli = "^3.0.0"
```

## Development Versions

### Installing Pre-release

```bash
pip install --pre agent-brain-rag agent-brain-cli
```

### Installing from Git

```bash
# Latest main branch
pip install git+https://github.com/SpillwaveSolutions/agent-brain.git#subdirectory=agent-brain-server
pip install git+https://github.com/SpillwaveSolutions/agent-brain.git#subdirectory=agent-brain-cli

# Specific branch
pip install git+https://github.com/SpillwaveSolutions/agent-brain.git@feature-branch#subdirectory=agent-brain-server
```

## Release Notes

### v3.0.0 (Latest)

**New Features:**
- Server-side job queue for async indexing
- Background job processing
- Job status tracking and cancellation
- Improved performance for large document sets

**Breaking Changes:**
- Job queue API changes
- Index format may require re-indexing

For full release notes, see: https://github.com/SpillwaveSolutions/agent-brain/releases

### v2.0.0

**New Features:**
- Pluggable embedding providers (OpenAI, Cohere, Ollama)
- Pluggable summarization providers (Anthropic, OpenAI, Gemini, Grok, Ollama)
- Fully local mode with Ollama (no API keys required)
- Enhanced GraphRAG support

### v1.4.0

**Features:**
- Graph search mode
- Multi-mode fusion search
- Improved entity extraction

### v1.3.0

**Features:**
- AST-aware code ingestion
- Support for Python, TypeScript, JavaScript, Java, Go, Rust, C, C++
- Improved code summarization

### v1.2.0

**Features:**
- Multi-instance architecture
- Per-project isolation
- Automatic server discovery

## Support Lifecycle

| Version | Status | Support Until |
|---------|--------|---------------|
| 3.0.x | Active | Current |
| 2.0.x | Maintenance | 2025-12 |
| 1.x | End of Life | - |

**Active**: Full support, new features
**Maintenance**: Security fixes only
**End of Life**: No support
