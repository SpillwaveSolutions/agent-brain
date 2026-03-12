# Phase 19: Plugin and skill updates for embedding cache management - Context

**Gathered:** 2026-03-12
**Status:** Ready for planning
**Source:** Conversation gap analysis

<domain>
## Phase Boundary

Close the end-user plugin/skill/docs gaps for the embedding cache feature. The backend (server API + CLI) is fully implemented and tested. This phase adds the plugin slash commands, updates help/API docs, and teaches the skills about cache management so users can interact with the cache entirely through Claude Code without dropping to the terminal.

</domain>

<decisions>
## Implementation Decisions

### Plugin Slash Command
- Create `agent-brain-cache.md` in `agent-brain-plugin/commands/`
- Must support two subcommands: `status` and `clear`
- Status should show: entries (disk), entries (memory), hit rate, hits, misses, size
- Clear should confirm before clearing, support `--yes` to skip confirmation
- Implementation: shell out to `agent-brain cache status` and `agent-brain cache clear` CLI commands

### Help Command Updates
- Add "Cache Commands" category to `agent-brain-help.md`
- Include `agent-brain-cache` in the command reference table
- Add detailed help for `/agent-brain-help --command cache`

### API Reference Updates
- Document `GET /index/cache` endpoint in `api_reference.md`
- Document `DELETE /index/cache` endpoint in `api_reference.md`
- Include request/response schemas and example JSON

### Skill Updates (using-agent-brain)
- Update `SKILL.md` to mention cache management capabilities
- Teach agents when to check cache status (after indexing, troubleshooting slow queries)
- Teach agents when to clear cache (after changing embedding provider/model, corruption)

### Search Assistant Agent
- Update `search-assistant.md` to be cache-aware
- Agent should suggest checking cache hit rate when queries seem slow
- Agent should suggest clearing cache when provider config changes

### Setup/Config Awareness
- Embedding cache env vars should be documented in setup skill:
  - `EMBEDDING_CACHE_MAX_MEM_ENTRIES` (default: 1000)
  - `EMBEDDING_CACHE_MAX_DISK_MB` (default: 500)
- Cache is automatic (no setup needed), but config is available for tuning

### Claude's Discretion
- Exact wording and formatting of plugin command markdown
- Level of detail in API reference examples
- Whether to add cache info to troubleshooting guides

</decisions>

<specifics>
## Specific Ideas

### Existing Backend (DO NOT MODIFY)
- Server: `agent_brain_server/api/routers/cache.py` — GET/DELETE at `/index/cache/`
- Server: `agent_brain_server/services/embedding_cache.py` — `EmbeddingCacheService`
- CLI: `agent_brain_cli/commands/cache.py` — `cache status` and `cache clear`
- CLI client: `agent_brain_cli/client/api_client.py` — `cache_status()` and `clear_cache()`
- Tests: `tests/test_cache_command.py` (CLI) and `tests/test_embedding_cache.py` (server)

### Files to Create/Update
1. **CREATE**: `agent-brain-plugin/commands/agent-brain-cache.md` — new slash command
2. **UPDATE**: `agent-brain-plugin/commands/agent-brain-help.md` — add Cache Commands category
3. **UPDATE**: `agent-brain-plugin/skills/using-agent-brain/references/api_reference.md` — add cache endpoints
4. **UPDATE**: `agent-brain-plugin/skills/using-agent-brain/SKILL.md` — cache management section
5. **UPDATE**: `agent-brain-plugin/agents/search-assistant.md` — cache awareness
6. **UPDATE**: `agent-brain-plugin/skills/configuring-agent-brain/SKILL.md` — cache config vars (if not already there)

### Pattern to Follow
- Look at existing commands like `agent-brain-status.md` or `agent-brain-reset.md` for the markdown format
- Look at existing API docs for `/index` endpoints for the documentation pattern
- Cache commands use the same `--url` option pattern as other commands

</specifics>

<deferred>
## Deferred Ideas

- Cache warm-up command (pre-populate cache from existing index)
- Cache export/import for sharing between instances
- Per-document cache invalidation (currently only full clear)

</deferred>

---

*Phase: 19-plugin-and-skill-updates-for-embedding-cache-management*
*Context gathered: 2026-03-12 via conversation gap analysis*
