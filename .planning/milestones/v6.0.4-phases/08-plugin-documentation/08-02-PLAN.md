---
phase: 08-plugin-documentation
plan: 02
type: execute
wave: 2
depends_on: ["08-01"]
files_modified:
  - docs/POSTGRESQL_SETUP.md
  - docs/PERFORMANCE_TRADEOFFS.md
  - docs/PLUGIN_GUIDE.md
  - docs/CONFIGURATION.md
  - agent-brain-plugin/skills/configuring-agent-brain/references/configuration-guide.md
  - agent-brain-plugin/skills/configuring-agent-brain/references/troubleshooting-guide.md
  - agent-brain-plugin/skills/using-agent-brain/references/troubleshooting-guide.md
autonomous: true
must_haves:
  truths:
    - "Documentation includes a Docker Compose setup guide for pgvector PostgreSQL"
    - "Backend selection and postgres configuration are documented with YAML + env override guidance"
    - "Performance tradeoffs between ChromaDB and PostgreSQL are described with selection guidance"
  artifacts:
    - path: "docs/POSTGRESQL_SETUP.md"
      provides: "Docker Compose pgvector setup guide"
      min_lines: 40
    - path: "docs/PERFORMANCE_TRADEOFFS.md"
      provides: "ChromaDB vs PostgreSQL tradeoff guide"
      min_lines: 30
    - path: "docs/CONFIGURATION.md"
      provides: "Storage backend configuration reference"
      contains: "storage"
    - path: "agent-brain-plugin/skills/configuring-agent-brain/references/configuration-guide.md"
      provides: "Storage backend YAML examples for plugin users"
      min_lines: 20
    - path: "agent-brain-plugin/skills/configuring-agent-brain/references/troubleshooting-guide.md"
      provides: "Postgres troubleshooting section"
      min_lines: 15
  key_links:
    - from: "docs/PLUGIN_GUIDE.md"
      to: "docs/POSTGRESQL_SETUP.md"
      via: "Reference Documentation section"
      pattern: "POSTGRESQL_SETUP"
    - from: "docs/CONFIGURATION.md"
      to: "storage.backend"
      via: "Storage Configuration section"
      pattern: "storage\.backend"
    - from: "docs/PERFORMANCE_TRADEOFFS.md"
      to: "ChromaDB vs PostgreSQL"
      via: "Comparison table or bullets"
      pattern: "ChromaDB|PostgreSQL"
---

<objective>
Publish updated documentation that explains PostgreSQL setup, backend configuration, and performance tradeoffs for the new dual-backend system.

Purpose: Ensure users can choose, configure, and operate the right backend with clear guidance.
Output: New setup/tradeoff docs and updated configuration/troubleshooting references.
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
@docs/CONFIGURATION.md
@docs/PLUGIN_GUIDE.md
@agent-brain-plugin/skills/configuring-agent-brain/references/configuration-guide.md
@agent-brain-plugin/skills/configuring-agent-brain/references/troubleshooting-guide.md
@agent-brain-plugin/skills/using-agent-brain/references/troubleshooting-guide.md
@agent-brain-plugin/templates/docker-compose.postgres.yml
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create PostgreSQL setup and performance tradeoff docs</name>
  <files>docs/POSTGRESQL_SETUP.md, docs/PERFORMANCE_TRADEOFFS.md, docs/PLUGIN_GUIDE.md</files>
  <action>
Create docs/POSTGRESQL_SETUP.md with Docker Compose instructions using agent-brain-plugin/templates/docker-compose.postgres.yml, required environment variables, readiness checks (docker compose ps, pg_isready), pgvector requirement, and a reminder that there is no auto-migration (re-index required). Create docs/PERFORMANCE_TRADEOFFS.md with a concise comparison between ChromaDB and PostgreSQL (setup complexity, scalability, tuning, operational tooling, and dataset size guidance). Update docs/PLUGIN_GUIDE.md to link to the new setup and tradeoff docs from the Reference Documentation or Quick Setup sections without removing existing links.
  </action>
  <verify>rg -n "POSTGRESQL_SETUP|PERFORMANCE_TRADEOFFS|pgvector" docs/PLUGIN_GUIDE.md docs/POSTGRESQL_SETUP.md docs/PERFORMANCE_TRADEOFFS.md</verify>
  <done>New setup and tradeoff docs exist and are linked from the plugin guide.</done>
</task>

<task type="auto">
  <name>Task 2: Update configuration and troubleshooting references for storage backend</name>
  <files>docs/CONFIGURATION.md, agent-brain-plugin/skills/configuring-agent-brain/references/configuration-guide.md, agent-brain-plugin/skills/configuring-agent-brain/references/troubleshooting-guide.md, agent-brain-plugin/skills/using-agent-brain/references/troubleshooting-guide.md</files>
  <action>
Add a storage backend configuration section that documents storage.backend values, a storage.postgres YAML block, AGENT_BRAIN_STORAGE_BACKEND env override, and DATABASE_URL connection string override (pool settings stay in YAML). Add postgres troubleshooting guidance (connection refused, pgvector extension missing, pool exhaustion, embedding dimension mismatch) with concrete remediation steps including Docker Compose usage and agent-brain reset for dimension changes. Keep existing provider configuration content intact while adding storage guidance.
  </action>
  <verify>rg -n "storage\.backend|storage\.postgres|DATABASE_URL|pgvector|pool" docs/CONFIGURATION.md agent-brain-plugin/skills/configuring-agent-brain/references/configuration-guide.md agent-brain-plugin/skills/configuring-agent-brain/references/troubleshooting-guide.md agent-brain-plugin/skills/using-agent-brain/references/troubleshooting-guide.md</verify>
  <done>Configuration and troubleshooting references include postgres backend setup and failure recovery steps.</done>
</task>

</tasks>

<verification>
- Confirm new setup and tradeoff docs exist and are linked from plugin guide.
- Confirm configuration references document storage backend selection and postgres YAML.
- Confirm troubleshooting guides include postgres-specific error patterns and fixes.
</verification>

<success_criteria>
- Users can follow docs to start pgvector PostgreSQL locally with Docker Compose.
- Users can configure storage backend selection with correct precedence and overrides.
- Users can choose between ChromaDB and PostgreSQL based on clear tradeoffs.
</success_criteria>

<output>
After completion, create `.planning/phases/08-plugin-documentation/08-02-SUMMARY.md`
</output>
