# Phase 19: Plugin and Skill Updates for Embedding Cache Management - Research

**Researched:** 2026-03-12
**Domain:** Claude Code plugin markdown authoring — slash commands, skills, agent markdown files
**Confidence:** HIGH

## Summary

Phase 19 is a pure documentation/plugin phase. The backend is fully implemented and tested (Phase 16 complete). There is no Python code to write, no servers to modify, and no new dependencies to add. Every deliverable is a markdown file.

The work is pattern-matching against the six existing plugin artifacts to add the embedding cache surface (two CLI commands, two REST endpoints) to the end-user layer. The existing plugin files provide direct templates: `agent-brain-reset.md` for a destructive confirmation-guarded command, `agent-brain-status.md` for status display, `agent-brain-help.md` for command registry, and the skills/agents for prose guidance patterns.

**Primary recommendation:** Copy the exact YAML front-matter structure and section layout from `agent-brain-reset.md` (for the `clear` subcommand pattern) and `agent-brain-status.md` (for the `status` subcommand pattern) to produce `agent-brain-cache.md`. Then thread cache awareness into the five existing files with minimal, targeted additions.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Create `agent-brain-cache.md` in `agent-brain-plugin/commands/`
- Must support two subcommands: `status` and `clear`
- Status should show: entries (disk), entries (memory), hit rate, hits, misses, size
- Clear should confirm before clearing, support `--yes` to skip confirmation
- Implementation: shell out to `agent-brain cache status` and `agent-brain cache clear` CLI commands
- Add "Cache Commands" category to `agent-brain-help.md`
- Include `agent-brain-cache` in the command reference table
- Add detailed help for `/agent-brain-help --command cache`
- Document `GET /index/cache` endpoint in `api_reference.md`
- Document `DELETE /index/cache` endpoint in `api_reference.md`
- Include request/response schemas and example JSON
- Update `SKILL.md` to mention cache management capabilities
- Teach agents when to check cache status (after indexing, troubleshooting slow queries)
- Teach agents when to clear cache (after changing embedding provider/model, corruption)
- Update `search-assistant.md` to be cache-aware
- Agent should suggest checking cache hit rate when queries seem slow
- Agent should suggest clearing cache when provider config changes
- Embedding cache env vars documented in setup skill: `EMBEDDING_CACHE_MAX_MEM_ENTRIES` (default: 1000), `EMBEDDING_CACHE_MAX_DISK_MB` (default: 500)
- Cache is automatic (no setup needed), but config is available for tuning

### Claude's Discretion
- Exact wording and formatting of plugin command markdown
- Level of detail in API reference examples
- Whether to add cache info to troubleshooting guides

### Deferred Ideas (OUT OF SCOPE)
- Cache warm-up command (pre-populate cache from existing index)
- Cache export/import for sharing between instances
- Per-document cache invalidation (currently only full clear)
</user_constraints>

---

## Standard Stack

### Core
| Library / Tool | Version | Purpose | Why Standard |
|---------------|---------|---------|--------------|
| Markdown (Claude Code plugin format) | N/A | Plugin slash commands, skills, agents | The only format the Claude Code plugin system consumes |
| YAML front-matter | N/A | Metadata block in every plugin file | Required header structure; Claude Code parses it for name, description, parameters, skills |

### Supporting
| Library / Tool | Version | Purpose | When to Use |
|---------------|---------|---------|-------------|
| agent-brain CLI (existing) | v7.0+ | Shell commands invoked inside plugin execution blocks | Shell out to `agent-brain cache status` and `agent-brain cache clear` |
| REST API (existing) | v8.0 | Raw HTTP layer documented in api_reference.md | When documenting the server endpoints for direct API consumers |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Two separate command files (agent-brain-cache-status.md + agent-brain-cache-clear.md) | Single agent-brain-cache.md with subcommand parameter | Single file matches the pattern used for `agent-brain-reset.md`; subcommand parameter is simpler for users |

**Installation:** No installation required. Files are markdown only.

---

## Architecture Patterns

### Existing Plugin File Structure
```
agent-brain-plugin/
├── commands/
│   ├── agent-brain-cache.md          ← CREATE (new)
│   ├── agent-brain-help.md           ← UPDATE (add Cache Commands category)
│   ├── agent-brain-reset.md          ← REFERENCE template (destructive + confirmation)
│   ├── agent-brain-status.md         ← REFERENCE template (status display)
│   └── ...                           (24 other command files)
├── skills/
│   ├── using-agent-brain/
│   │   ├── SKILL.md                  ← UPDATE (add cache management section)
│   │   └── references/
│   │       └── api_reference.md      ← UPDATE (add /index/cache endpoints)
│   └── configuring-agent-brain/
│       └── SKILL.md                  ← UPDATE (add cache env vars to reference table)
└── agents/
    └── search-assistant.md           ← UPDATE (add cache-awareness hints)
```

### Pattern 1: Plugin Command Front-Matter
**What:** Every command file opens with a YAML block defining name, description, parameters list, and skills list.
**When to use:** All new command markdown files.
**Example (from agent-brain-reset.md):**
```yaml
---
name: agent-brain-reset
description: Clear the document index (requires confirmation)
parameters:
  - name: yes
    description: Skip confirmation prompt
    required: false
    default: false
skills:
  - using-agent-brain
---
```

### Pattern 2: Subcommand Parameter
**What:** A `subcommand` parameter (required) discriminates between `status` and `clear`.
**When to use:** Commands that expose multiple operations under one slash command.
**Example (adapted for agent-brain-cache.md):**
```yaml
parameters:
  - name: subcommand
    description: "Operation to perform: status or clear"
    required: true
    allowed: [status, clear]
  - name: yes
    description: Skip confirmation prompt (only for clear)
    required: false
    default: false
```

### Pattern 3: Execution Sections with Shell Commands
**What:** Numbered step sections with fenced bash blocks showing the exact CLI call.
**When to use:** All execution flows inside command files.
**Example (from agent-brain-reset.md, Step 3):**
```bash
agent-brain reset --yes
```
For cache:
```bash
agent-brain cache status
agent-brain cache clear --yes
```

### Pattern 4: Confirmation Gate (destructive operations)
**What:** Before executing a destructive operation, show current state and request explicit user confirmation unless `--yes` is passed.
**When to use:** Any command that permanently deletes data.
**Example pattern (from agent-brain-reset.md):**
```
Before running, MUST:
1. Show the user what will be cleared
2. Ask for explicit confirmation
3. Only proceed if the user confirms
```

### Pattern 5: API Reference Section Format
**What:** Each endpoint has: method+path header, description paragraph, optional request body table, response JSON block with field annotations, and error status table.
**When to use:** Every new endpoint added to api_reference.md.
**Example (existing DELETE /index pattern):**
```markdown
### DELETE /index

Clear all indexed documents.

**Response:**
```json
{
  "job_id": "reset",
  "status": "completed",
  "message": "Index cleared successfully"
}
```
```

### Pattern 6: Skill Section Addition
**What:** New ## section appended before "When Not to Use" with use-case guidance, trigger conditions, and bash examples.
**When to use:** When adding a new capability to an existing skill.

### Pattern 7: Environment Variable Table Row
**What:** New rows in the `| Variable | Required | Default | Description |` table in configuring-agent-brain/SKILL.md.
**When to use:** Any new env var that users can tune.

### Anti-Patterns to Avoid
- **Creating separate files per subcommand:** `agent-brain-cache-status.md` + `agent-brain-cache-clear.md` — breaks consistency; all existing multi-operation patterns use a single file with a subcommand parameter.
- **Documenting internal implementation details:** Plugin files are user-facing. Do not describe SQLite WAL mode or struct.pack float32 encoding in plugin docs.
- **Duplicating content between skill and command:** The command file owns execution steps; the skill owns "when to use" guidance. Do not repeat full usage tables in both places.
- **Omitting `--url` option documentation:** Every CLI command that contacts the server documents the `--url` / `AGENT_BRAIN_URL` option. The cache commands follow this same pattern.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cache status display logic | Custom Rich table rendering inside the plugin | Shell out to `agent-brain cache status` | CLI already renders a Rich table with all 6 metrics; plugin just calls it |
| Cache clear confirmation logic | Custom prompt in plugin execution steps | `agent-brain cache clear` (without `--yes` prompts natively) | CLI Confirm.ask already handles this |
| API client for cache | httpx calls in plugin bash blocks | CLI commands | CLI encapsulates error handling, retries, and JSON formatting |

**Key insight:** The CLI is the abstraction layer. Plugin commands are thin wrappers that invoke the CLI and present results. They do not re-implement logic.

---

## Common Pitfalls

### Pitfall 1: Forgetting the `--url` / `AGENT_BRAIN_URL` pattern
**What goes wrong:** Command file documents `agent-brain cache status` without noting the `--url` override or `AGENT_BRAIN_URL` env var.
**Why it happens:** It's easy to copy the simple form of the command.
**How to avoid:** Check `cache.py` — both `cache_status` and `cache_clear` accept `--url` (envvar `AGENT_BRAIN_URL`). Document this in the Parameters table and Error Handling section.
**Warning signs:** Other command files (reset, status) all include the `--url` pattern; if yours doesn't, it's inconsistent.

### Pitfall 2: Mis-stating the API endpoint path
**What goes wrong:** Documenting the endpoint as `GET /cache` or `GET /cache/status` instead of the correct `GET /index/cache`.
**Why it happens:** The cache router is mounted at `/index/cache` in the main app, not at a top-level `/cache` prefix.
**How to avoid:** Verified from `agent_brain_server/api/routers/cache.py` — canonical paths are `GET /index/cache/` and `DELETE /index/cache/`. The no-slash aliases (`/index/cache`) also work.
**Warning signs:** Any doc that says `/cache` without the `/index/` prefix is wrong.

### Pitfall 3: Missing the trailing-slash / no-slash alias note
**What goes wrong:** Clients get 307 redirects from `/index/cache` (no trailing slash).
**Why it happens:** FastAPI redirects non-slash URLs to the slash version by default.
**How to avoid:** The router already registers both `""` and `"/"` aliases. Document that both `/index/cache` and `/index/cache/` are accepted — clients should use no-slash form (`/index/cache`) for simplicity.

### Pitfall 4: Omitting the 503 error case
**What goes wrong:** API reference only documents 200 responses.
**Why it happens:** Happy-path documentation instinct.
**How to avoid:** The cache router raises 503 if `get_embedding_cache()` returns None (cache not initialized). Document this in the error table.

### Pitfall 5: skill `description` trigger phrases not updated
**What goes wrong:** The `using-agent-brain` SKILL.md front-matter description doesn't include cache-related trigger phrases, so the skill doesn't activate for cache queries.
**Why it happens:** The YAML description block is easy to miss when editing the body.
**How to avoid:** Add cache trigger phrases to the `description:` field in the YAML front-matter: `"cache management"`, `"clear embedding cache"`, `"cache hit rate"`, `"cache status"`.

### Pitfall 6: Agent-brain-help.md command reference table omission
**What goes wrong:** The new Cache Commands category is added to the human-readable display section but the `## Command Reference` table at the bottom (lines 131-153) is not updated.
**Why it happens:** The table is a separate duplicate of the category display; easy to edit one and forget the other.
**How to avoid:** The help file has TWO places to update: (1) the text display output block and (2) the `| Command | Category | Description |` table. Update both.

---

## Code Examples

Verified patterns from source files:

### Cache Status CLI Output (from cache.py)
```
Metric            Value
──────────────── ──────
Entries (disk)    1,234
Entries (memory)    500
Hit Rate          87.3%
Hits            5,432
Misses              800
Size             14.81 MB
```

### Cache Status API Response (GET /index/cache)
```json
{
  "hits": 5432,
  "misses": 800,
  "hit_rate": 0.8712,
  "mem_entries": 500,
  "entry_count": 1234,
  "size_bytes": 15531008
}
```
Source: `agent_brain_server/api/routers/cache.py` `_cache_status_impl` — combines `cache.get_stats()` (session counters: hits, misses, hit_rate, mem_entries) with `cache.get_disk_stats()` (entry_count, size_bytes).

### Cache Clear API Response (DELETE /index/cache)
```json
{
  "count": 1234,
  "size_bytes": 15531008,
  "size_mb": 14.81
}
```
Source: `agent_brain_server/api/routers/cache.py` `_clear_cache_impl`.

### Cache Clear CLI Output (from cache.py)
```
Cleared 1,234 cached embeddings (14.8 MB freed)
```

### Confirmation Prompt (cache clear without --yes)
```
This will flush 1,234 cached embeddings. Continue? [y/N]:
```

### Cache Status Subcommand Execution Block
```bash
agent-brain cache status
```

### Cache Clear Subcommand Execution Block (with confirmation)
```bash
agent-brain cache clear
```

### Cache Clear Skip Confirmation
```bash
agent-brain cache clear --yes
```

### Cache Status JSON (for scripting)
```bash
agent-brain cache status --json
```

---

## Exact File Changes Required

### 1. CREATE: `agent-brain-plugin/commands/agent-brain-cache.md`

New file. YAML front-matter: name=`agent-brain-cache`, description, parameters for `subcommand` (required, status|clear) and `yes` (optional, bool). Skills: `using-agent-brain`.

Sections:
- Purpose
- Usage (syntax table for both subcommands)
- Execution: Step-by-step for `status` path and separate step-by-step for `clear` path (with confirmation gate)
- Output: show the exact CLI table format for status; confirmation + success message for clear
- Error Handling table (server not running, cache not initialized/503, already empty)
- Related Commands (agent-brain-status, agent-brain-reset)

### 2. UPDATE: `agent-brain-plugin/commands/agent-brain-help.md`

Two changes:
1. Add `CACHE COMMANDS` category block in the human-readable display section between "INDEXING COMMANDS" and "HELP"
2. Add `agent-brain-cache` row to the `## Command Reference` table with Category=Cache

### 3. UPDATE: `agent-brain-plugin/skills/using-agent-brain/references/api_reference.md`

Add a new `## Cache Endpoints` section after the existing `## Index Endpoints` section. Include:
- `GET /index/cache` — with response JSON and field descriptions
- `DELETE /index/cache` — with response JSON and field descriptions
- Notes on trailing-slash aliases and 503 error case
Also add `agent-brain cache status` and `agent-brain cache clear [--yes]` entries to the `## CLI Commands Reference` section.

### 4. UPDATE: `agent-brain-plugin/skills/using-agent-brain/SKILL.md`

Two changes:
1. Add `"cache management"` and related phrases to the YAML `description:` front-matter trigger list.
2. Add `## Cache Management` section before `## When Not to Use`. Content: when to check status (after indexing, slow queries), when to clear (provider/model change, suspected corruption), example commands.
3. Add `Cache Management` to the `## Contents` table of contents.
4. Add cache guide reference row to the `## Reference Documentation` table pointing at `api_reference.md`.

### 5. UPDATE: `agent-brain-plugin/agents/search-assistant.md`

Two targeted additions:
1. Add a new trigger pattern for slow query / cache performance queries.
2. Add a `### 6. Check Cache Performance (optional)` step after the Execute Search step — suggests `agent-brain cache status` when queries seem slow and explains when to `agent-brain cache clear`.

### 6. UPDATE: `agent-brain-plugin/skills/configuring-agent-brain/SKILL.md`

Add two rows to the `## Environment Variables Reference` table:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `EMBEDDING_CACHE_MAX_MEM_ENTRIES` | No | 1000 | Max in-memory LRU entries (~12 MB at 3072 dims per 1000 entries) |
| `EMBEDDING_CACHE_MAX_DISK_MB` | No | 500 | Max disk size for the SQLite embedding cache |

Also add a brief "Embedding Cache Tuning" note in the Provider Configuration section — cache is automatic, no setup required, but these env vars allow tuning for large indexes or memory-constrained environments.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No cache visibility in plugin | `/agent-brain-cache` slash command | Phase 19 | Users can check and clear embedding cache without dropping to terminal |
| Cache env vars undocumented in skills | Documented in configuring-agent-brain SKILL.md | Phase 19 | Users can tune cache for large indexes |
| API reference missing /index/cache | Documented in api_reference.md | Phase 19 | Direct API consumers can integrate cache management |

**Deprecated/outdated:**
- Nothing deprecated — these are purely additive changes.

---

## Open Questions

1. **`--json` flag on `agent-brain-cache status`**
   - What we know: The CLI `cache_status` command accepts `--json` / `json_output` flag (verified in cache.py line 27).
   - What's unclear: Whether the command file should document the `--json` parameter in its YAML front-matter. Other commands (status.md) include `--json` as a parameter.
   - Recommendation: Include `--json` as an optional parameter in the new command file's YAML front-matter, consistent with `agent-brain-status.md`.

2. **Troubleshooting guide update**
   - What we know: `using-agent-brain/references/troubleshooting-guide.md` exists (referenced in SKILL.md).
   - What's unclear: Whether the CONTEXT.md "Claude's Discretion" intent includes adding a cache troubleshooting section there.
   - Recommendation: Add a brief "Embedding Cache" troubleshooting section covering "queries slower than expected → check hit rate" and "dimension mismatch error after model change → clear cache". This is low-risk additive content.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (agent-brain-server and agent-brain-cli) |
| Config file | `agent-brain-server/pyproject.toml` and `agent-brain-cli/pyproject.toml` |
| Quick run command | `cd agent-brain-server && poetry run pytest tests/test_embedding_cache.py -x` |
| Full suite command | `task before-push` |

### Phase Requirements → Test Map

This phase produces only markdown files. There is no Python code to test. Validation is structural/content review of the markdown files.

| Deliverable | Validation Type | Check |
|-------------|-----------------|-------|
| agent-brain-cache.md created | Manual review | File exists, YAML front-matter valid, both subcommand flows present |
| agent-brain-help.md updated | Manual review | Cache Commands category present in display block AND command reference table |
| api_reference.md updated | Manual review | GET /index/cache and DELETE /index/cache sections present with correct paths |
| using-agent-brain/SKILL.md updated | Manual review | Cache Management section present, trigger phrases added to YAML description |
| search-assistant.md updated | Manual review | Cache performance check step present |
| configuring-agent-brain/SKILL.md updated | Manual review | EMBEDDING_CACHE_MAX_MEM_ENTRIES and EMBEDDING_CACHE_MAX_DISK_MB in env vars table |

### Sampling Rate
- **Per task commit:** Review markdown file for required sections before committing
- **Per wave merge:** `task before-push` (format/lint/type/test pass — no code change means this is a formality)
- **Phase gate:** All 6 files created/updated and content review passes before close

### Wave 0 Gaps
None — existing test infrastructure covers all code; this phase adds no code.

---

## Sources

### Primary (HIGH confidence)
- `/agent-brain-plugin/commands/agent-brain-reset.md` — destructive command template (confirmation pattern, error handling table)
- `/agent-brain-plugin/commands/agent-brain-status.md` — status display command template
- `/agent-brain-plugin/commands/agent-brain-help.md` — help command structure (category groups + reference table)
- `/agent-brain-plugin/skills/using-agent-brain/SKILL.md` — skill YAML front-matter structure and section patterns
- `/agent-brain-plugin/agents/search-assistant.md` — agent trigger pattern and assistance flow format
- `/agent-brain-plugin/skills/using-agent-brain/references/api_reference.md` — endpoint documentation pattern
- `/agent-brain-plugin/skills/configuring-agent-brain/SKILL.md` — env vars reference table format
- `/agent-brain-cli/agent_brain_cli/commands/cache.py` — exact CLI commands, flags, output format (authoritative source)
- `/agent-brain-server/agent_brain_server/api/routers/cache.py` — exact API endpoint paths, response schemas (authoritative source)
- `.planning/phases/19-plugin-and-skill-updates-for-embedding-cache-management/19-CONTEXT.md` — locked decisions

### Secondary (MEDIUM confidence)
- `.planning/REQUIREMENTS.md` — XCUT-03 requirement: Plugin skills and commands updated for new CLI features (cache, watch_mode)
- `.planning/STATE.md` — Phase 19 context and v8.0 decisions

### Tertiary (LOW confidence)
- None.

---

## Metadata

**Confidence breakdown:**
- File list and scope: HIGH — directly read all source files, CONTEXT.md locks exact deliverables
- Template patterns: HIGH — directly inspected five existing plugin files
- API response schemas: HIGH — read the actual router implementation
- CLI command flags: HIGH — read the actual Click command implementation
- Env var defaults: HIGH — stated in CONTEXT.md (locked decision), consistent with Phase 16 decisions in STATE.md

**Research date:** 2026-03-12
**Valid until:** Stable — markdown/plugin format changes infrequently. Re-verify if Claude Code plugin spec changes.
