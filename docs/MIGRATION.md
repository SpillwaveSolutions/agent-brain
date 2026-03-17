---
last_validated: 2026-03-16
---

# Migration Guide: doc-serve to Agent Brain

**Version**: 1.1.x to 1.2.0
**Last Updated**: 2026-01-30

## Table of Contents

- [Overview](#overview)
- [What's Changing](#whats-changing)
- [What's NOT Changing](#whats-not-changing)
- [Step-by-Step Migration](#step-by-step-migration)
- [Command Reference](#command-reference)
- [Deprecation Timeline](#deprecation-timeline)
- [FAQ](#faq)
- [Troubleshooting](#troubleshooting)
- [Getting Help](#getting-help)

---

## Overview

Starting with v1.2.0, the project is rebranding from "doc-serve" to "agent-brain" to align with the PyPI package names (`agent-brain-rag`, `agent-brain-cli`).

**Why the change?** PyPI rejected `doc-serve` as too similar to an existing package. We chose `agent-brain` for uniqueness and are now aligning all component names for consistency.

**Impact on existing users:** Minimal. The old command names continue to work in v1.2.x and v1.3.x with deprecation warnings. You have until v2.0.0 to update your scripts and workflows.

---

## What's Changing

| Component | Old Name | New Name | Status in v1.2.0 |
|-----------|----------|----------|------------------|
| CLI command | `agent-brain` | `agent-brain` | Deprecated (works until v2.0) |
| Server command | `doc-serve` | `agent-brain-serve` | Deprecated (works until v2.0) |
| Skill name | `doc-serve` | `using-agent-brain` | Renamed |
| Repository | doc-serve-skill | agent-brain | Renamed |

### Command Name Changes

**CLI Tool:**
```bash
# Old (deprecated)
agent-brain <command>

# New (recommended)
agent-brain <command>
```

**Server:**
```bash
# Old (deprecated)
doc-serve

# New (recommended)
agent-brain-serve
```

---

## What's NOT Changing

The following remain unchanged to minimize disruption:

- **PyPI package names**: Still `agent-brain-rag` and `agent-brain-cli`
- **Data directories**: Still `.claude/doc-serve/` (migration planned for future release)
- **API endpoints**: All REST endpoints unchanged (`/health`, `/query`, `/index`, etc.)
- **Configuration files**: All environment variables unchanged
- **Indexed data**: Your documents remain indexed and accessible
- **Port numbers**: Default port 8000 unchanged
- **Internal module names**: Python imports unchanged

---

## Step-by-Step Migration

### Step 1: Update Your Packages

Ensure you have the latest version:

```bash
pip install --upgrade agent-brain-rag agent-brain-cli
```

Or if using pipx:

```bash
pipx upgrade agent-brain-cli
```

### Step 2: Verify New Commands Work

Test that the new commands are available:

```bash
agent-brain --version
agent-brain-serve --version
```

### Step 3: Update Your Commands

Replace deprecated commands with new ones:

**Before (deprecated):**
```bash
agent-brain init
agent-brain start --daemon
agent-brain status
agent-brain query "search term"
agent-brain index ./docs
agent-brain stop
doc-serve
```

**After (recommended):**
```bash
agent-brain init
agent-brain start --daemon
agent-brain status
agent-brain query "search term"
agent-brain index ./docs
agent-brain stop
agent-brain-serve
```

### Step 4: Update Your Scripts

If you have automation scripts, shell aliases, or CI/CD pipelines using the old commands, update them:

**Shell scripts:**
```bash
#!/bin/bash
# Old
agent-brain query "search term" --mode hybrid

# New
agent-brain query "search term" --mode hybrid
```

**Aliases (in ~/.bashrc or ~/.zshrc):**
```bash
# Old
alias docq='agent-brain query'

# New
alias docq='agent-brain query'
```

**CI/CD pipelines:**
```yaml
# Old
- run: agent-brain index ./docs

# New
- run: agent-brain index ./docs
```

### Step 5: Update Skill Reference (if applicable)

If you reference the skill in your Claude Code configuration:

```yaml
# Old
skills:
  - doc-serve

# New
skills:
  - using-agent-brain
```

---

## Command Reference

All commands remain functionally identical. Only the base command name changes.

| Old Command | New Command | Description |
|-------------|-------------|-------------|
| `agent-brain init` | `agent-brain init` | Initialize project |
| `agent-brain start` | `agent-brain start` | Start server |
| `agent-brain stop` | `agent-brain stop` | Stop server |
| `agent-brain list` | `agent-brain list` | List instances |
| `agent-brain status` | `agent-brain status` | Check status |
| `agent-brain query` | `agent-brain query` | Search documents |
| `agent-brain index` | `agent-brain index` | Index documents |
| `agent-brain reset` | `agent-brain reset` | Clear index |
| `doc-serve` | `agent-brain-serve` | Run server directly |

---

## Deprecation Timeline

| Version | Old Commands | New Commands | Notes |
|---------|--------------|--------------|-------|
| v1.2.0 | Work with warning | Primary | Current release |
| v1.3.x | Work with warning | Primary | Continued support |
| v2.0.0 | **Removed** | Only option | Breaking change |

**Key dates:**
- **v1.2.0 (Current)**: Deprecation warnings introduced
- **v2.0.0 (Future)**: Old commands removed entirely

We recommend updating your scripts as soon as convenient to avoid issues when v2.0.0 is released.

---

## FAQ

### Q: Do I need to re-index my documents?

**No.** Your indexed data persists in `.claude/doc-serve/` and continues to work with both old and new commands. The data format is unchanged.

### Q: Will my existing scripts break?

**Not immediately.** The old commands (`agent-brain`, `doc-serve`) continue to work in v1.2.x and v1.3.x with deprecation warnings. Update your scripts before v2.0.0.

### Q: Why the name change?

PyPI rejected `doc-serve` as too similar to an existing package. We chose `agent-brain` for uniqueness and are now aligning all component names.

### Q: What about the repository URL?

GitHub automatically redirects from the old URL to the new one. Your existing clones will continue to work.

### Q: Can I suppress the deprecation warnings?

Yes, but we recommend updating your commands instead. If you must suppress warnings temporarily:

```bash
# Python warning filter
PYTHONWARNINGS="ignore::DeprecationWarning" agent-brain status

# Or redirect stderr
agent-brain status 2>/dev/null
```

### Q: What if I have both old and new commands in my PATH?

Both commands work and execute the same underlying code. The old commands simply show a deprecation warning before running.

### Q: Will the data directory name change?

**Not in v1.2.0.** The `.claude/doc-serve/` directory name is unchanged. A future release may introduce a migration to `.claude/agent-brain/`, but this will include automated migration tooling.

### Q: Are the Python package imports changing?

**No.** The internal Python module names (`agent_brain_server`, `agent_brain_cli`) are unchanged. Only the CLI entry points are being renamed.

---

## Troubleshooting

### Warning: 'agent-brain' is deprecated

This is expected behavior. The warning reminds you to update to the new command name. To resolve:

1. Update your command from `agent-brain` to `agent-brain`
2. Update any scripts or aliases using the old name

### Command 'agent-brain' not found

Ensure you have the latest version installed:

```bash
pip install --upgrade agent-brain-cli
```

Or reinstall:

```bash
pip uninstall agent-brain-cli
pip install agent-brain-cli
```

### Server won't start after upgrade

1. Check if an old instance is still running: `agent-brain list`
2. Stop any running instances: `agent-brain stop`
3. Start fresh: `agent-brain start`

### Data appears missing after upgrade

Your data is still in `.claude/doc-serve/`. Verify:

```bash
ls -la .claude/doc-serve/
agent-brain status
```

---

## Getting Help

- **Issues**: https://github.com/SpillwaveSolutions/agent-brain/issues
- **Documentation**: https://github.com/SpillwaveSolutions/agent-brain#readme
- **User Guide**: [docs/USER_GUIDE.md](USER_GUIDE.md)
- **Developer Guide**: [docs/DEVELOPERS_GUIDE.md](DEVELOPERS_GUIDE.md)

If you encounter problems during migration, please open an issue with:
1. Your current version (`agent-brain --version`)
2. The exact error message
3. Steps to reproduce
