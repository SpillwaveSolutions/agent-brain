# Agent Brain Release Skill

Automates the release process for Agent Brain packages, including version bumping, changelog generation, git tagging, and GitHub release creation.

## Version Resolution

Before running any install commands, resolve the latest version:

```bash
# Get latest from PyPI (recommended)
LATEST=$(curl -sf https://pypi.org/pypi/agent-brain-rag/json | python3 -c "import sys,json; print(json.load(sys.stdin)['info']['version'])")
echo "Latest version: $LATEST"
```

**Current PyPI Versions:**
- Check: https://pypi.org/project/agent-brain-rag/
- Check: https://pypi.org/project/agent-brain-cli/

## Package Installation

Agent Brain consists of two PyPI packages that work together:

### Basic Installation

```bash
# Resolve latest version first
LATEST=$(curl -sf https://pypi.org/pypi/agent-brain-rag/json | python3 -c "import sys,json; print(json.load(sys.stdin)['info']['version'])")

# Install with pinned version
pip install agent-brain-rag==$LATEST agent-brain-cli==$LATEST
```

### With Optional Features

```bash
# With GraphRAG support (knowledge graph retrieval)
pip install "agent-brain-rag[graphrag]==$LATEST"

# With all optional features
pip install "agent-brain-rag[graphrag-all]==$LATEST"
```

### Package Details

| Package | Description | PyPI |
|---------|-------------|------|
| `agent-brain-rag` | RAG server with FastAPI, embeddings, and search | [PyPI](https://pypi.org/project/agent-brain-rag/) |
| `agent-brain-cli` | CLI tool for managing Agent Brain instances | [PyPI](https://pypi.org/project/agent-brain-cli/) |

## Quick Start After Installation

### 1. Set Environment Variables

```bash
export OPENAI_API_KEY=your-openai-key
export ANTHROPIC_API_KEY=your-anthropic-key
```

### 2. Start the Server

```bash
# Using CLI (recommended)
agent-brain init          # Initialize project config
agent-brain start         # Start server for current project

# Or run server directly
agent-brain-serve         # Start on http://127.0.0.1:8000
```

### 3. Index Documents

```bash
agent-brain index ./docs ./src    # Index documentation and source code
```

### 4. Query Your Knowledge Base

```bash
agent-brain query "How does authentication work?"
```

### 5. Stop the Server

```bash
agent-brain stop
```

## Trigger Patterns

- `/agent-brain-release <bump>` - Create a release with specified version bump
- `/agent-brain-release <bump> --dry-run` - Preview release without making changes

Where `<bump>` is one of:

- `major` - Breaking changes (X.0.0 → X+1.0.0)
- `minor` - New features (X.Y.0 → X.Y+1.0)
- `patch` - Bug fixes (X.Y.Z → X.Y.Z+1)

## Process Overview

The release skill performs these steps:

1. **Validate Pre-conditions**
   - Working directory is clean (no uncommitted changes)
   - On `main` branch
   - Local branch is synced with remote

2. **Calculate New Version**
   - Parse current version from `agent-brain-server/pyproject.toml`
   - Apply bump type to calculate new version

3. **Update Version Files** (4 files total)
   - `agent-brain-server/pyproject.toml`
   - `agent-brain-server/agent_brain_server/__init__.py`
   - `agent-brain-cli/pyproject.toml`
   - `agent-brain-cli/agent_brain_cli/__init__.py`

4. **Generate Release Notes**
   - Collect commits since last tag
   - Group by conventional commit type (feat, fix, docs, etc.)
   - Format with PyPI links and documentation references

5. **Create Git Commit**
   - Commit message: `chore(release): bump version to X.Y.Z`

6. **Create Git Tag**
   - Tag format: `vX.Y.Z`

7. **Push to Remote**
   - Push branch and tag to origin

8. **Create GitHub Release**
   - Use `gh release create` with generated notes
   - This triggers the `publish-to-pypi.yml` workflow

## Dry Run Mode

Use `--dry-run` to preview all changes without executing:

```text
/agent-brain-release minor --dry-run

[DRY RUN] Would perform the following actions:
  Current version: X.Y.Z
  New version: X.Y+1.0

  Files to update:
    - agent-brain-server/pyproject.toml
    - agent-brain-server/agent_brain_server/__init__.py
    - agent-brain-cli/pyproject.toml
    - agent-brain-cli/agent_brain_cli/__init__.py

  Commits since vX.Y.Z: <count>

  No changes made.
```

## Implementation Steps

When `/agent-brain-release` is invoked, Claude should:

### Step 1: Parse Arguments

```bash
# Extract bump type and dry-run flag from command arguments
BUMP_TYPE="minor"  # or major/patch from $ARGUMENTS
DRY_RUN=false      # true if --dry-run present
```

### Step 2: Validate Pre-conditions

```bash
# Check for clean working directory
git status --porcelain

# Check current branch
git branch --show-current  # must be "main"

# Check remote sync
git fetch origin
git status -sb  # should show "## main...origin/main"
```

### Step 3: Get Current Version

```bash
# Extract version from pyproject.toml
grep '^version = ' agent-brain-server/pyproject.toml | cut -d'"' -f2
```

### Step 4: Calculate New Version

```python
# Version calculation logic
def bump_version(current: str, bump_type: str) -> str:
    major, minor, patch = map(int, current.split('.'))
    if bump_type == 'major':
        return f"{major + 1}.0.0"
    elif bump_type == 'minor':
        return f"{major}.{minor + 1}.0"
    else:  # patch
        return f"{major}.{minor}.{patch + 1}"
```

### Step 5: Update Version Files

```bash
# Update all 4 version files using sed or Edit tool
# See references/version-management.md for exact locations
```

### Step 6: Generate Release Notes

```bash
# Get commits since last tag
git log $(git describe --tags --abbrev=0)..HEAD --oneline

# Group by conventional commit prefix
```

### Step 7: Commit, Tag, and Push

```bash
# Commit version changes
git add -A
git commit -m "chore(release): bump version to $NEW_VERSION"

# Create tag
git tag -a "v$NEW_VERSION" -m "Release v$NEW_VERSION"

# Push
git push origin main
git push origin "v$NEW_VERSION"
```

### Step 8: Create GitHub Release

```bash
gh release create "v$NEW_VERSION" \
  --title "v$NEW_VERSION" \
  --notes-file release-notes.md
```

## Release Notes Template

```markdown
## What's Changed

### Features
- feat: description (#PR)

### Bug Fixes
- fix: description (#PR)

### Documentation
- docs: description (#PR)

### Other Changes
- chore/refactor/test: description (#PR)

## About Agent Brain

Agent Brain (formerly doc-serve) provides intelligent document indexing and semantic search for AI agents:

- **Semantic Search**: Natural language queries via OpenAI embeddings
- **Keyword Search (BM25)**: Traditional keyword matching with TF-IDF
- **GraphRAG**: Knowledge graph retrieval for relationship-aware queries
- **Hybrid Search**: Best of vector + keyword approaches
- **Pluggable Providers**: Choose your embedding and summarization providers

## PyPI Packages

- **agent-brain-rag**: https://pypi.org/project/agent-brain-rag/X.Y.Z/
- **agent-brain-cli**: https://pypi.org/project/agent-brain-cli/X.Y.Z/

## Installation

pip install agent-brain-rag==X.Y.Z agent-brain-cli==X.Y.Z

# With GraphRAG support
pip install agent-brain-rag[graphrag]==X.Y.Z

## Documentation

- [User Guide](https://github.com/SpillwaveSolutions/agent-brain/wiki/User-Guide)
- [Developer Guide](https://github.com/SpillwaveSolutions/agent-brain/wiki/Developer-Guide)
- [All Releases](https://github.com/SpillwaveSolutions/agent-brain/releases)

**Full Changelog**: [vPREV...vNEW](https://github.com/SpillwaveSolutions/agent-brain/compare/vPREV...vNEW)
```

## Post-Release Reminders

After creating a release, remind the user to:

1. **Monitor PyPI Publish**: Check GitHub Actions for the `publish-to-pypi` workflow status
2. **Verify PyPI Pages**: Confirm packages appear at:
   - <https://pypi.org/project/agent-brain-rag/>
   - <https://pypi.org/project/agent-brain-cli/>
3. **Update Wiki**: If API changes were made, update documentation at:
   - <https://github.com/SpillwaveSolutions/agent-brain/wiki>
4. **Announce**: Post release announcement if significant changes

## Error Handling

Common issues and solutions:

| Error | Solution |
|-------|----------|
| Dirty working directory | Commit or stash changes first |
| Not on main branch | Switch to main: `git checkout main` |
| Behind remote | Pull latest: `git pull origin main` |
| Tag already exists | Version already released, use different bump |
| gh not authenticated | Run `gh auth login` |

## References

- [Version Management](references/version-management.md) - Version file locations
- [PyPI Setup Guide](references/pypi-setup.md) - OIDC configuration
