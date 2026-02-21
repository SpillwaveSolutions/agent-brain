---
created: 2026-02-20T19:24:12.153Z
title: Make asyncpg and sqlalchemy non-optional for PostgreSQL support
area: general
files:
  - agent-brain-server/pyproject.toml:57-64
  - agent-brain-cli/pyproject.toml:30
  - .claude/skills/installing-local/install.sh:157-161
  - agent-brain-plugin/commands/agent-brain-install.md:126-128
---

## Problem

`asyncpg` and `sqlalchemy[asyncio]` are declared as **optional extras** in `agent-brain-rag` under `[tool.poetry.extras] postgres = ["asyncpg", "sqlalchemy"]`. However, none of the three install paths activate these extras:

1. **install.sh (local dev):** `uv tool install $CLI_WHEEL` — no `--with asyncpg`
2. **Plugin `/agent-brain-install`:** `pipx install agent-brain-cli==$VERSION` — no postgres awareness at all
3. **Plugin `/agent-brain-config`:** Selects postgres backend but doesn't warn about missing asyncpg

Every user who selects PostgreSQL as storage backend hits `No module named 'asyncpg'` at runtime. The workaround is `uv tool install agent-brain-cli --with asyncpg --with "sqlalchemy[asyncio]"` but this is undocumented and fragile.

## Solution

**Recommended approach:** Make `asyncpg` and `sqlalchemy` **non-optional** dependencies in `agent-brain-server/pyproject.toml`.

Changes needed:
1. Move `asyncpg` and `sqlalchemy` from optional to required in `agent-brain-server/pyproject.toml` (lines 57-58 → move to main `[tool.poetry.dependencies]`)
2. Remove or keep the `[tool.poetry.extras] postgres` entry for backward compatibility
3. Run `poetry lock` to update lockfile
4. Run `task before-push` to validate
5. Bump version to 6.0.3
6. Create fix branch, commit, and release

**Why non-optional:** These packages are ~2MB combined. The "optional" savings is not worth the UX breakage — every postgres user hits this error. The coordination cost of keeping them optional across 3 install paths (install.sh, plugin install, plugin config) is high and fragile.

**Alternative (rejected):** Update all 3 install paths to pass `--with asyncpg` when postgres is selected. This is fragile because it requires coordination between install and config commands, and any new install path would need to remember this.
