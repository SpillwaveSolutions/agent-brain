# Research: Agent Brain Naming Unification

**Feature**: 112-agent-brain-naming
**Date**: 2026-01-29

## Research Tasks

### 1. GitHub Repository Rename

**Question**: How does GitHub handle repository renames and what are the implications?

**Decision**: GitHub supports repository renames with automatic redirects

**Rationale**:
- GitHub automatically creates redirects from the old URL to the new URL
- Redirects work for clones, web access, and API calls
- Redirects are permanent and persist indefinitely
- Existing clones continue to work (remote URL redirect)

**Alternatives Considered**:
- Creating a new repository and archiving old one: Rejected - loses history and stars
- Keeping old name: Rejected - perpetuates confusion

**Implementation Notes**:
1. Settings → General → Repository name
2. Change `doc-serve-skill` → `agent-brain`
3. Update local remotes: `git remote set-url origin git@github.com:SpillwaveSolutions/agent-brain.git`
4. Update documentation URLs after rename

---

### 2. Poetry Entry Points

**Question**: How to add multiple entry points (commands) to a single Poetry package?

**Decision**: Poetry supports multiple scripts in `[tool.poetry.scripts]` section

**Rationale**:
- Each script entry creates a separate console script
- Both old and new commands can coexist in the same package
- No additional dependencies required
- Standard Poetry/setuptools feature

**Implementation**:
```toml
[tool.poetry.scripts]
agent-brain = "doc_svr_ctl.cli:cli"     # Primary (new)
doc-svr-ctl = "doc_svr_ctl.cli:cli"     # Alias (deprecated)
```

**Alternatives Considered**:
- Separate packages for new names: Rejected - unnecessary complexity
- Shell aliases only: Rejected - not portable, user must configure

---

### 3. Deprecation Warnings

**Question**: Best practices for CLI deprecation notices in Python?

**Decision**: Use `warnings.warn()` with `DeprecationWarning` category, shown once per session

**Rationale**:
- Python standard library approach
- Users see the warning but can continue working
- Can be filtered/silenced if needed
- Clear message about migration path

**Implementation**:
```python
import sys
import warnings

def show_deprecation_notice():
    """Show deprecation warning for old command names."""
    command_name = Path(sys.argv[0]).name

    deprecated_commands = {
        'doc-svr-ctl': 'agent-brain',
        'doc-serve': 'agent-brain-serve',
    }

    if command_name in deprecated_commands:
        new_command = deprecated_commands[command_name]
        warnings.warn(
            f"'{command_name}' is deprecated and will be removed in v2.0. "
            f"Use '{new_command}' instead.",
            DeprecationWarning,
            stacklevel=2
        )
```

**Alternatives Considered**:
- Hard error with message: Rejected - breaks existing scripts
- Silent operation: Rejected - users never learn about new names
- Print to stderr only: Rejected - less standard than warnings

---

### 4. Skill Directory Naming Convention

**Question**: What naming convention should the skill follow?

**Decision**: Use `using-agent-brain` prefix pattern

**Rationale**:
- Matches Claude Code skill naming conventions
- `using-` prefix indicates it's a skill for using a tool
- Aligns with other skills like `using-spacy-nlp`, `using-claude-code-cli`
- Distinguishes from the tool itself (agent-brain) vs the skill for using it

**Alternatives Considered**:
- `agent-brain-skill`: Rejected - redundant (it's already a skill)
- `agent-brain`: Rejected - conflicts with CLI command name
- `doc-serve`: Rejected - original name, doesn't match PyPI branding

---

## Summary

All research questions resolved. No blockers identified.

| Topic | Decision | Risk Level |
|-------|----------|------------|
| Repository rename | GitHub auto-redirects | Low |
| Entry points | Multiple Poetry scripts | Low |
| Deprecation | Python warnings module | Low |
| Skill naming | using-agent-brain | Low |

**Ready for Implementation**: Yes
