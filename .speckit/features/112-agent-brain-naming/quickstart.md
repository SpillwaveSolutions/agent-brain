# Migration Guide: Doc-Serve → Agent Brain

**Version**: 1.1.0 → 1.2.0
**Date**: 2026-01-29

## Overview

Starting with v1.2.0, the project is rebranding from "doc-serve" to "agent-brain" to align with the PyPI package names (`agent-brain-rag`, `agent-brain-cli`).

## What's Changing

| Component | Old Name | New Name | Status |
|-----------|----------|----------|--------|
| CLI command | `doc-svr-ctl` | `agent-brain` | Deprecated (works until v2.0) |
| Server command | `doc-serve` | `agent-brain-serve` | Deprecated (works until v2.0) |
| Skill name | `doc-serve` | `using-agent-brain` | Renamed |
| Repository | doc-serve-skill | agent-brain | Renamed |

## What's NOT Changing

- **PyPI package names**: Still `agent-brain-rag` and `agent-brain-cli`
- **Data directories**: Still `.claude/doc-serve/` (migration in future release)
- **API endpoints**: All REST endpoints unchanged
- **Configuration**: All environment variables unchanged

## Migration Steps

### Step 1: Update Your Packages

```bash
pip install --upgrade agent-brain-rag agent-brain-cli
```

### Step 2: Update Your Commands

**Before (deprecated)**:
```bash
doc-svr-ctl init
doc-svr-ctl start --daemon
doc-serve
```

**After (recommended)**:
```bash
agent-brain init
agent-brain start --daemon
agent-brain-serve
```

### Step 3: Update Your Scripts

If you have scripts using the old commands, update them:

```bash
# Old
doc-svr-ctl query "search term" --mode hybrid

# New
agent-brain query "search term" --mode hybrid
```

### Step 4: Update Skill Reference (if applicable)

If you reference the skill in your Claude Code configuration:

```yaml
# Old
skills:
  - doc-serve

# New
skills:
  - using-agent-brain
```

## Deprecation Timeline

| Version | Old Commands | New Commands |
|---------|--------------|--------------|
| v1.2.0 | Work with warning | Primary |
| v1.3.0 | Work with warning | Primary |
| v2.0.0 | Removed | Only option |

## FAQ

### Q: Do I need to re-index my documents?

No. Your indexed data persists in `.claude/doc-serve/` and continues to work.

### Q: Will my existing scripts break?

Not immediately. The old commands (`doc-svr-ctl`, `doc-serve`) continue to work in v1.2.0 with a deprecation warning. Update your scripts before v2.0.0.

### Q: Why the name change?

PyPI rejected `doc-serve` as too similar to an existing package. We chose `agent-brain` for uniqueness and are now aligning all component names.

### Q: What about the repository URL?

GitHub automatically redirects from the old URL to the new one. Your existing clones will continue to work.

## Getting Help

- **Issues**: https://github.com/SpillwaveSolutions/agent-brain/issues
- **Documentation**: https://github.com/SpillwaveSolutions/agent-brain#readme
