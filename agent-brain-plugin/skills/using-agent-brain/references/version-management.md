# Agent Brain Version Management

Guide for installing, upgrading, and managing Agent Brain versions.

## Current Version

**v2.0.0** (Latest)

### Version History

| Version | Release Date | Key Features |
|---------|--------------|--------------|
| 2.0.0 | 2024-12 | Pluggable providers, GraphRAG, multi-instance |
| 1.4.0 | 2024-11 | Graph search mode, multi-mode fusion |
| 1.3.0 | 2024-10 | AST-aware code ingestion |
| 1.2.0 | 2024-09 | Multi-instance architecture |
| 1.1.0 | 2024-08 | Hybrid search, BM25 integration |
| 1.0.0 | 2024-07 | Initial release |

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

### Latest Stable

```bash
pip install agent-brain-rag agent-brain-cli
```

### Specific Version

```bash
# Install exact version
pip install agent-brain-rag==2.0.0 agent-brain-cli==2.0.0

# Install version 1.4.0
pip install agent-brain-rag==1.4.0 agent-brain-cli==1.4.0
```

### Version Range

```bash
# Compatible with 2.x
pip install "agent-brain-rag>=2.0.0,<3.0.0"

# Minimum version
pip install "agent-brain-rag>=1.4.0"
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
pip install --upgrade agent-brain-rag==2.0.0 agent-brain-cli==2.0.0
```

### Check for Updates

```bash
# Check if updates are available
pip list --outdated | grep agent-brain
```

## Downgrading

To downgrade to a previous version:

```bash
# Downgrade to specific version
pip install agent-brain-rag==1.4.0 agent-brain-cli==1.4.0

# Force reinstall
pip install --force-reinstall agent-brain-rag==1.4.0
```

### Migration Considerations

When downgrading, be aware of:

1. **Index Compatibility**: Newer indexes may not work with older versions
2. **Configuration**: New config options won't be recognized
3. **Features**: New features won't be available

**Recommended Steps:**
```bash
# 1. Stop server
agent-brain stop

# 2. Backup configuration
cp -r .claude/agent-brain .claude/agent-brain.backup

# 3. Reset index (if needed)
agent-brain reset --yes

# 4. Downgrade
pip install agent-brain-rag==1.4.0 agent-brain-cli==1.4.0

# 5. Re-index
agent-brain start --daemon
agent-brain index /path/to/docs
```

## Version Compatibility

### Package Alignment

Always keep `agent-brain-rag` and `agent-brain-cli` on the same major/minor version:

| RAG Version | CLI Version | Compatible |
|-------------|-------------|------------|
| 2.0.0 | 2.0.0 | Yes |
| 2.0.0 | 1.4.0 | No |
| 1.4.0 | 1.4.0 | Yes |

### Python Version Compatibility

| Agent Brain | Python |
|-------------|--------|
| 2.0.x | 3.10, 3.11, 3.12 |
| 1.x | 3.10, 3.11 |

### Index Compatibility

Indexes created with one version may not be compatible with another:

| From Version | To Version | Index Compatible |
|--------------|------------|------------------|
| 1.x | 2.0 | Re-index required |
| 2.0.x | 2.0.y | Usually compatible |
| 2.0 | 1.x | Re-index required |

## Version Pinning

### In requirements.txt

```text
agent-brain-rag==2.0.0
agent-brain-cli==2.0.0
```

### In pyproject.toml

```toml
[project]
dependencies = [
    "agent-brain-rag>=2.0.0,<3.0.0",
    "agent-brain-cli>=2.0.0,<3.0.0",
]
```

### In Poetry

```toml
[tool.poetry.dependencies]
agent-brain-rag = "^2.0.0"
agent-brain-cli = "^2.0.0"
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

### v2.0.0 (Latest)

**New Features:**
- Pluggable embedding providers (OpenAI, Cohere, Ollama)
- Pluggable summarization providers (Anthropic, OpenAI, Gemini, Grok, Ollama)
- Fully local mode with Ollama (no API keys required)
- Enhanced GraphRAG support

**Breaking Changes:**
- Configuration format changed for providers
- New environment variables for provider selection
- Index format updated (re-index required from 1.x)

**Migration from 1.4.0:**
```bash
# 1. Stop server
agent-brain stop

# 2. Upgrade packages
pip install --upgrade agent-brain-rag agent-brain-cli

# 3. Update configuration
# Set EMBEDDING_PROVIDER=openai (or your preferred provider)
# Set SUMMARIZATION_PROVIDER=anthropic (or your preferred provider)

# 4. Re-index documents
agent-brain reset --yes
agent-brain start --daemon
agent-brain index /path/to/docs
```

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
| 2.0.x | Active | Current |
| 1.4.x | Maintenance | 2025-06 |
| 1.3.x | End of Life | - |
| < 1.3 | End of Life | - |

**Active**: Full support, new features
**Maintenance**: Security fixes only
**End of Life**: No support
