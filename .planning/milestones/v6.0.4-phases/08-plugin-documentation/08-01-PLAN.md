---
phase: 08-plugin-documentation
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - agent-brain-plugin/commands/agent-brain-config.md
  - agent-brain-plugin/commands/agent-brain-setup.md
  - agent-brain-plugin/agents/setup-assistant.md
  - agent-brain-plugin/.claude-plugin/plugin.json
autonomous: true
must_haves:
  truths:
    - "/agent-brain-config guides storage backend selection and writes storage.backend + storage.postgres configuration"
    - "/agent-brain-setup detects Docker and offers to start PostgreSQL via Docker Compose when backend is postgres"
    - "Setup assistant recognizes PostgreSQL-specific errors and suggests fixes"
    - "Plugin metadata version is updated to v5.0.0"
  artifacts:
    - path: "agent-brain-plugin/commands/agent-brain-config.md"
      provides: "Storage backend selection flow and YAML examples"
      min_lines: 40
    - path: "agent-brain-plugin/commands/agent-brain-setup.md"
      provides: "Docker detection and postgres setup guidance"
      min_lines: 20
    - path: "agent-brain-plugin/agents/setup-assistant.md"
      provides: "PostgreSQL error patterns and recovery steps"
      min_lines: 15
    - path: "agent-brain-plugin/.claude-plugin/plugin.json"
      provides: "Plugin metadata version bump"
      contains: "\"version\": \"5.0.0\""
  key_links:
    - from: "agent-brain-plugin/commands/agent-brain-config.md"
      to: "storage.backend"
      via: "AskUserQuestion backend choice"
      pattern: "storage\.backend"
    - from: "agent-brain-plugin/commands/agent-brain-setup.md"
      to: "agent-brain-plugin/templates/docker-compose.postgres.yml"
      via: "Docker Compose start instructions"
      pattern: "docker-compose\.postgres\.yml"
    - from: "agent-brain-plugin/agents/setup-assistant.md"
      to: "PostgreSQL error handling"
      via: "error_pattern triggers"
      pattern: "postgres|pgvector|pool|connection refused"
---

<objective>
Update the plugin configuration and setup flows to support PostgreSQL backend selection, dockerized setup, and targeted troubleshooting while bumping plugin metadata to v5.0.0.

Purpose: Ensure users can configure and bootstrap PostgreSQL without guessing or missing required steps.
Output: Updated plugin command guides, setup assistant, and plugin metadata.
</objective>

<execution_context>
@/Users/richardhightower/.config/opencode/get-shit-done/workflows/execute-plan.md
@/Users/richardhightower/.config/opencode/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/08-plugin-documentation/08-RESEARCH.md
@agent-brain-plugin/commands/agent-brain-config.md
@agent-brain-plugin/commands/agent-brain-setup.md
@agent-brain-plugin/agents/setup-assistant.md
@agent-brain-plugin/.claude-plugin/plugin.json
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add storage backend selection to /agent-brain-config</name>
  <files>agent-brain-plugin/commands/agent-brain-config.md</files>
  <action>
Insert a new step after provider selection that uses AskUserQuestion to pick storage backend (ChromaDB or PostgreSQL). Document the backend resolution order (AGENT_BRAIN_STORAGE_BACKEND env override, then YAML config, default ChromaDB) and add a YAML snippet that writes storage.backend plus a full storage.postgres block (host, port, database, user, password, pool_size, pool_max_overflow, language, hnsw_m, hnsw_ef_construction, debug). Include a note that DATABASE_URL overrides only the connection string and that there is no auto-migration (users must re-index). Keep existing provider configuration and indexing exclude steps intact.
  </action>
  <verify>rg -n "storage\.backend|storage\.postgres|DATABASE_URL" agent-brain-plugin/commands/agent-brain-config.md</verify>
  <done>Config command flow includes storage backend selection and a complete postgres YAML example.</done>
</task>

<task type="auto">
  <name>Task 2: Extend /agent-brain-setup with Docker + postgres bootstrap</name>
  <files>agent-brain-plugin/commands/agent-brain-setup.md</files>
  <action>
Add a postgres setup step that runs when storage backend is postgres: detect Docker and Docker Compose availability, offer to start the provided docker-compose.postgres.yml template, and include commands to verify readiness (docker compose ps, pg_isready). Clarify that PostgreSQL setup is optional unless backend is postgres, and reference the template path under agent-brain-plugin/templates. Keep the existing install/config/init/start/verify sequence but insert the postgres step before starting the server.
  </action>
  <verify>rg -n "docker compose|postgres|pgvector|docker-compose\.postgres\.yml" agent-brain-plugin/commands/agent-brain-setup.md</verify>
  <done>/agent-brain-setup documents dockerized postgres startup and readiness checks when postgres backend is selected.</done>
</task>

<task type="auto">
  <name>Task 3: Add postgres troubleshooting patterns and bump plugin version</name>
  <files>agent-brain-plugin/agents/setup-assistant.md, agent-brain-plugin/.claude-plugin/plugin.json</files>
  <action>
Add setup assistant error triggers for postgres-specific failures (connection refused, pgvector extension missing, pool exhaustion, embedding dimension mismatch) and include concrete fixes for each (start Docker Compose, ensure pgvector image, increase pool_size/pool_max_overflow, run agent-brain reset after embedding changes). Update plugin.json version to 5.0.0 and keep other metadata unchanged.
  </action>
  <verify>rg -n "pgvector|pool|dimension|postgres" agent-brain-plugin/agents/setup-assistant.md && rg -n "\"version\": \"5.0.0\"" agent-brain-plugin/.claude-plugin/plugin.json</verify>
  <done>Setup assistant recognizes postgres errors with fixes and plugin metadata reflects v5.0.0.</done>
</task>

</tasks>

<verification>
- Confirm /agent-brain-config includes storage backend selection and postgres YAML.
- Confirm /agent-brain-setup includes Docker detection + compose startup steps.
- Confirm setup-assistant adds postgres error patterns and plugin.json version is 5.0.0.
</verification>

<success_criteria>
- Users can follow plugin docs to configure postgres backend without missing required storage settings.
- Setup flow provides a dockerized postgres path and clear readiness checks.
- Postgres-specific errors are mapped to clear remediation guidance.
- Plugin metadata reflects the v5.0.0 release.
</success_criteria>

<output>
After completion, create `.planning/phases/08-plugin-documentation/08-01-SUMMARY.md`
</output>
