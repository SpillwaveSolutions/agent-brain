# Version Management Reference

This document describes all version file locations and update patterns for Agent Brain releases.

## Version File Locations

Agent Brain uses synchronized versioning across 4 files:

| File | Format | Pattern |
|------|--------|---------|
| `agent-brain-server/pyproject.toml` | TOML | `version = "X.Y.Z"` |
| `agent-brain-server/agent_brain_server/__init__.py` | Python | `__version__ = "X.Y.Z"` |
| `agent-brain-cli/pyproject.toml` | TOML | `version = "X.Y.Z"` |
| `agent-brain-cli/agent_brain_cli/__init__.py` | Python | `__version__ = "X.Y.Z"` |

## Version Update Commands

### Using sed (portable)

```bash
NEW_VERSION="1.3.0"

# Server pyproject.toml
sed -i '' "s/^version = \".*\"/version = \"$NEW_VERSION\"/" agent-brain-server/pyproject.toml

# Server __init__.py
sed -i '' "s/__version__ = \".*\"/__version__ = \"$NEW_VERSION\"/" agent-brain-server/agent_brain_server/__init__.py

# CLI pyproject.toml
sed -i '' "s/^version = \".*\"/version = \"$NEW_VERSION\"/" agent-brain-cli/pyproject.toml

# CLI __init__.py
sed -i '' "s/__version__ = \".*\"/__version__ = \"$NEW_VERSION\"/" agent-brain-cli/agent_brain_cli/__init__.py
```

### Using Claude Edit Tool

For each file, use the Edit tool with:

**pyproject.toml files:**
```
old_string: version = "1.2.0"
new_string: version = "1.3.0"
```

**__init__.py files:**
```
old_string: __version__ = "1.2.0"
new_string: __version__ = "1.3.0"
```

## Version Extraction

To get the current version:

```bash
# From pyproject.toml
grep '^version = ' agent-brain-server/pyproject.toml | cut -d'"' -f2

# From __init__.py
grep '__version__' agent-brain-server/agent_brain_server/__init__.py | cut -d'"' -f2

# From git tags (latest)
git describe --tags --abbrev=0 | sed 's/^v//'
```

## Version Validation

Versions must follow semantic versioning (SemVer):

- Format: `MAJOR.MINOR.PATCH`
- All components must be non-negative integers
- No leading zeros (except for 0 itself)

Regex pattern: `^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$`

## Version Bump Logic

```python
def bump_version(current: str, bump_type: str) -> str:
    """
    Bump version according to SemVer rules.

    Args:
        current: Current version string (e.g., "1.2.3")
        bump_type: One of "major", "minor", "patch"

    Returns:
        New version string
    """
    parts = current.split('.')
    major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])

    if bump_type == 'major':
        return f"{major + 1}.0.0"
    elif bump_type == 'minor':
        return f"{major}.{minor + 1}.0"
    else:  # patch
        return f"{major}.{minor}.{patch + 1}"
```

## Version Consistency Check

To verify all version files are in sync:

```bash
#!/bin/bash
# Check version consistency across all files

SERVER_TOML=$(grep '^version = ' agent-brain-server/pyproject.toml | cut -d'"' -f2)
SERVER_INIT=$(grep '__version__' agent-brain-server/agent_brain_server/__init__.py | cut -d'"' -f2)
CLI_TOML=$(grep '^version = ' agent-brain-cli/pyproject.toml | cut -d'"' -f2)
CLI_INIT=$(grep '__version__' agent-brain-cli/agent_brain_cli/__init__.py | cut -d'"' -f2)

if [ "$SERVER_TOML" = "$SERVER_INIT" ] && [ "$SERVER_TOML" = "$CLI_TOML" ] && [ "$SERVER_TOML" = "$CLI_INIT" ]; then
    echo "✓ All versions match: $SERVER_TOML"
else
    echo "✗ Version mismatch detected:"
    echo "  agent-brain-server/pyproject.toml: $SERVER_TOML"
    echo "  agent-brain-server/__init__.py:    $SERVER_INIT"
    echo "  agent-brain-cli/pyproject.toml:    $CLI_TOML"
    echo "  agent-brain-cli/__init__.py:       $CLI_INIT"
    exit 1
fi
```

## Git Tag Naming

- Format: `vX.Y.Z` (e.g., `v1.3.0`)
- Always prefix with lowercase `v`
- Must match version in files exactly (minus the `v` prefix)

## PyPI Package Names

When released, packages are published as:

| Package Name | PyPI URL |
|--------------|----------|
| `agent-brain-rag` | https://pypi.org/project/agent-brain-rag/ |
| `agent-brain-cli` | https://pypi.org/project/agent-brain-cli/ |

The PyPI package names are defined in `pyproject.toml`:
- Server: `name = "agent-brain-rag"`
- CLI: `name = "agent-brain-cli"`
