# Phase 22: Restore Setup Wizard with Full Configuration Prompts — Research

**Researched:** 2026-03-12
**Domain:** Claude Code plugin slash commands and skill markdown files
**Confidence:** HIGH

---

## Summary

Phase 22 restores the interactive setup wizard that guides users through all Agent Brain configuration choices. The wizard exists in the plugin as Claude Code slash commands (`/agent-brain-setup`, `/agent-brain-init`, `/agent-brain-config`) backed by the `configuring-agent-brain` skill. A deep git history review confirms these files have never contained full interactive wizard prompts — the commands were originally shipped as execution scripts with no `AskUserQuestion` calls for storage backend, query mode, or index type choices.

The current `/agent-brain-config` command was substantially improved during the v6.0 (PostgreSQL) and pluggable-providers milestones and does contain provider selection wizardry (Steps 3 and 5 use `AskUserQuestion` for provider and storage backend). However it does not ask about: default query mode (hybrid/semantic/BM25/graph/multi), which index types to enable (BM25, vector, graph), embedding cache settings, watch mode defaults, or reranking. The `/agent-brain-setup` command delegates to `/agent-brain-config` for provider setup but does not itself ask configuration questions — it orchestrates and verifies.

**The primary gap:** No single "wizard" command asks the complete set of configuration questions up front, writes a comprehensive `config.yaml`, and then runs init/start. The spec for this phase is to build that wizard either as an enhancement to `/agent-brain-setup` or as a new `/agent-brain-wizard` command, and to add regression-prevention spec tests (markdown linting checks that required wizard steps are present).

**Primary recommendation:** Extend `/agent-brain-setup` to be a true interactive wizard that asks all configuration questions before executing any CLI commands, then writes a complete `config.yaml` before running `agent-brain init`. Add a regression test file (e.g., `tests/test_plugin_wizard_spec.py` or a shell-based checker) that validates required `AskUserQuestion` blocks are present in the command files.

---

## Standard Stack

### Core (Plugin Layer — Markdown only, no Python packages)

| Component | Version | Purpose | Why Standard |
|-----------|---------|---------|--------------|
| Claude Code plugin commands | n/a (markdown) | Slash command definitions in `agent-brain-plugin/commands/` | Project convention established in Phase 11/8/114 |
| Claude Code skills | n/a (markdown) | Reusable skill documents in `agent-brain-plugin/skills/` | Loaded by commands via `skills:` frontmatter |
| AskUserQuestion directive | n/a (prose convention) | Ask interactive questions inside command markdown | Used in `/agent-brain-config` Steps 3 and 5 |
| config.yaml | YAML | User-level and project-level Agent Brain configuration | Introduced in Phase 2 (pluggable-providers) |

### Supporting (Regression Prevention)

| Component | Version | Purpose | When to Use |
|-----------|---------|---------|-------------|
| pytest | existing | Validate plugin markdown files contain required sections | Add `tests/test_plugin_spec.py` in agent-brain-server tests |
| Python stdlib `re` / `pathlib` | stdlib | Parse markdown wizard specs | Lightweight, no new deps |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Extending `/agent-brain-setup` | New `/agent-brain-wizard` command | Extending keeps `/agent-brain-setup` as the canonical entry point; avoids user confusion from two similar commands |
| pytest spec file | Shell script test | pytest integrates with `task before-push`; shell scripts do not |

**Installation:**
No new Python packages needed. Plugin changes are markdown file edits only.

---

## Architecture Patterns

### Recommended Plugin File Structure (no changes to layout)

```
agent-brain-plugin/
  commands/
    agent-brain-setup.md       # EXTEND: add wizard steps 1-N
    agent-brain-config.md      # EXISTS: has provider + storage wizard
    agent-brain-init.md        # EXISTS: no wizard needed (just runs init)
  skills/
    configuring-agent-brain/
      SKILL.md                 # UPDATE: add wizard configuration coverage
      references/
        configuration-guide.md # UPDATE: add query mode + index type sections
agent-brain-server/
  tests/
    test_plugin_wizard_spec.py # NEW: regression prevention tests
```

### Pattern 1: Interactive Wizard in Command Markdown

**What:** A command markdown file uses `AskUserQuestion` blocks to collect user choices before running any shell commands. Each question maps to one or more `config.yaml` fields.

**When to use:** Any time a command must configure a persistent setting the user hasn't expressed a preference for.

**Example (from existing `/agent-brain-config`):**
```markdown
### Step 3: Use AskUserQuestion for Provider Selection

Which provider setup would you like for Agent Brain?

Options:
1. Ollama (Local) - FREE, no API keys required. Uses nomic-embed-text + llama3.2
2. OpenAI + Anthropic - Best quality cloud providers. Requires OPENAI_API_KEY and ANTHROPIC_API_KEY
3. Google Gemini - Google's models. Requires GOOGLE_API_KEY
4. Custom Mix - Choose different providers for embedding vs summarization
5. Ollama + Mistral - FREE, uses nomic-embed-text + mistral-small3.2
```

This pattern is already established and working; the wizard phases needs to apply it to additional configuration dimensions.

### Pattern 2: Wizard Writes Comprehensive config.yaml

**What:** After collecting all answers, the wizard writes a single, complete `config.yaml` with all user choices embedded. This is the output artifact.

**When to use:** End of wizard flow, before running `agent-brain init`.

**Example of target config.yaml output:**
```yaml
# ~/.agent-brain/config.yaml — generated by /agent-brain-setup wizard
embedding:
  provider: "openai"
  model: "text-embedding-3-large"
  api_key_env: "OPENAI_API_KEY"

summarization:
  provider: "anthropic"
  model: "claude-haiku-4-5-20251001"
  api_key_env: "ANTHROPIC_API_KEY"

storage:
  backend: "chroma"   # or "postgres"

graphrag:
  enabled: false       # or true
  store_type: "simple"

query:
  default_mode: "hybrid"  # vector | bm25 | hybrid | graph | multi
```

### Pattern 3: Regression-Prevention Spec Test

**What:** A pytest file that reads the command markdown files and asserts required wizard sections are present. If someone edits `/agent-brain-setup.md` and removes an `AskUserQuestion` block, the test fails before merge.

**When to use:** After the wizard is shipped — run as part of `task before-push`.

```python
# Source: agent-brain-server/tests/test_plugin_wizard_spec.py (to be created)
import re
from pathlib import Path

PLUGIN_COMMANDS = Path(__file__).parent.parent.parent / "agent-brain-plugin" / "commands"

def test_setup_wizard_asks_provider():
    content = (PLUGIN_COMMANDS / "agent-brain-setup.md").read_text()
    assert "AskUserQuestion" in content or "provider" in content.lower()

def test_setup_wizard_asks_storage_backend():
    content = (PLUGIN_COMMANDS / "agent-brain-setup.md").read_text()
    assert "storage" in content.lower() or "ChromaDB" in content

def test_setup_wizard_asks_query_mode():
    content = (PLUGIN_COMMANDS / "agent-brain-setup.md").read_text()
    assert "query mode" in content.lower() or "hybrid" in content.lower()

def test_config_wizard_has_provider_selection():
    content = (PLUGIN_COMMANDS / "agent-brain-config.md").read_text()
    assert "AskUserQuestion" in content

def test_config_wizard_has_storage_backend_selection():
    content = (PLUGIN_COMMANDS / "agent-brain-config.md").read_text()
    assert "ChromaDB" in content and "PostgreSQL" in content
```

### Anti-Patterns to Avoid

- **Wizard inside init command:** `/agent-brain-init` runs `agent-brain init` — it should remain idempotent and non-interactive. Put wizard questions in `/agent-brain-setup` and `/agent-brain-config` only.
- **Scripting config.yaml writes in bash heredoc without error handling:** Use Python one-liner or `python -c` to safely write YAML, not bare `cat >> file` which concatenates without deduplication.
- **Asking questions the server ignores:** Only ask about settings that are actually consumed by `config.yaml` or env vars. Do not invent new YAML keys that the server does not read.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YAML writing in wizard | Custom bash YAML serializer | `python3 -c "import yaml; ..."` one-liner | bash heredoc is fragile with special chars in API keys |
| Port availability scan | Custom port scanner | Existing bash loop already in `/agent-brain-config` Step 5 (PostgreSQL section) | Pattern already proven, copy it |
| Provider validation | Custom curl-based provider tester | `agent-brain verify` CLI command | Already exists and handles all providers |

**Key insight:** The wizard is markdown, not Python. Every execution step already exists as a CLI command (`agent-brain verify`, `agent-brain init`, `agent-brain start`). The wizard only needs to collect answers and write config.yaml before invoking those commands.

---

## Common Pitfalls

### Pitfall 1: Editing the Wrong config.yaml

**What goes wrong:** User has both `~/.agent-brain/config.yaml` and `.claude/agent-brain/config.yaml`. Wizard writes to user-level, server reads project-level (which takes precedence). Configuration appears to have no effect.

**Why it happens:** Config search order: project > user > XDG. Wizard must detect which config exists and write to the highest-priority one that exists.

**How to avoid:** Step 1 of `/agent-brain-config` already does `ls ~/.agent-brain/config.yaml .claude/agent-brain/config.yaml 2>/dev/null` detection. Wizard must inherit and use this same detection logic. If project-level config exists, ALWAYS write there.

**Warning signs:** User runs `agent-brain status` and provider does not match what they selected.

### Pitfall 2: GraphRAG Questions Without Prerequisite Check

**What goes wrong:** Wizard asks "enable GraphRAG?" but GraphRAG requires `kuzu` or `simple` store. If user says yes but `ENABLE_GRAPH_INDEX=true` is written without explaining the `include-code` flag requirement, indexing silently produces no graph nodes.

**Why it happens:** GraphRAG needs AST-parsed code — it does not work on plain text documents. Enabling it without indexing code files with `--include-code` produces an empty graph.

**How to avoid:** When wizard enables GraphRAG, also surface: "To use graph mode, index with `agent-brain index ./src --include-code`."

**Warning signs:** `agent-brain query "class relationships" --mode graph` returns no results.

### Pitfall 3: Query Mode Default Doesn't Match Enabled Indexes

**What goes wrong:** User sets `default_mode: graph` but `ENABLE_GRAPH_INDEX` is false. Every query silently falls back or errors.

**Why it happens:** The wizard allows any query mode selection but does not validate consistency with enabled indexes.

**How to avoid:** In the wizard's query mode question, dynamically show only modes that match previously selected index types. If graph is not enabled, do not offer `graph` or `multi` as default modes.

**Warning signs:** Queries error with "graph index not enabled" on a fresh install.

### Pitfall 4: config.yaml Written Without API Key Security Notice

**What goes wrong:** User stores raw API key in `config.yaml` without `chmod 600`, then commits it to git.

**Why it happens:** Wizard writes the key into the file without ensuring file permissions are set.

**How to avoid:** After writing `config.yaml` with any `api_key` field, immediately run `chmod 600 ~/.agent-brain/config.yaml`. Show explicit warning: "Never commit this file — add to .gitignore."

**Warning signs:** `git diff` shows API key in tracked files.

### Pitfall 5: Wizard Regression — Steps Silently Removed

**What goes wrong:** A future refactor simplifies `/agent-brain-setup.md` by removing the storage backend question, and nobody notices because there is no automated check.

**Why it happens:** Plugin command files are markdown — no linter enforces their content structure.

**How to avoid:** Add `tests/test_plugin_wizard_spec.py` that asserts required sections exist. Run as part of `task before-push`.

**Warning signs:** CI passes but users report setup no longer asks about PostgreSQL.

---

## Code Examples

### Complete Wizard Question Catalog

These are the questions the restored wizard MUST ask, mapped to config.yaml fields:

```
QUESTION 1 — Embedding Provider
  AskUserQuestion: "Which embedding provider?"
  Options: Ollama (free), OpenAI (cloud), Cohere (multi-language), Gemini
  Writes: embedding.provider, embedding.model, embedding.base_url (Ollama only)
  API Key prompt: If cloud selected → ask for api_key or api_key_env reference

QUESTION 2 — Summarization Provider
  AskUserQuestion: "Which summarization provider?"
  Options: Ollama (free), Anthropic, OpenAI, Gemini, Grok
  Writes: summarization.provider, summarization.model
  API Key prompt: If cloud selected → ask for api_key or api_key_env reference

QUESTION 3 — Storage Backend
  AskUserQuestion: "Which storage backend?"
  Options: ChromaDB (default, zero-ops), PostgreSQL (larger datasets)
  Writes: storage.backend
  If postgres: trigger port discovery + docker compose setup (existing flow in /agent-brain-config Step 5)

QUESTION 4 — Enable GraphRAG (only if code indexing is relevant)
  AskUserQuestion: "Enable GraphRAG for code relationship queries?"
  Options: No (default), Yes — simple store (in-memory), Yes — Kuzu (persistent)
  Writes: graphrag.enabled, graphrag.store_type, graphrag.use_code_metadata
  Note: Show warning about needing --include-code on index command

QUESTION 5 — Default Query Mode
  AskUserQuestion: "Which query mode should be default?"
  Constrained by: If GraphRAG not enabled → offer only: hybrid, semantic, bm25
  If GraphRAG enabled → offer all: hybrid, semantic, bm25, graph, multi
  Writes: query.default_mode (if server supports this YAML key) OR just document as recommendation
  Note: Server resolves mode per-request, but SKILL.md should record user's preference

QUESTION 6 — File Watch Mode (optional / advanced)
  AskUserQuestion: "Enable automatic background re-indexing when files change?"
  Options: Off (default), On — auto (watch and re-index)
  Writes: Tells user to use --watch auto on agent-brain folders add
  Note: watch_mode is per-folder, not global config.yaml — wizard documents the right CLI flag
```

### config.yaml Generation Pattern (safe Python one-liner)

```bash
# Source: derived from existing /agent-brain-config patterns
python3 -c "
import yaml, sys
config = {
  'embedding': {'provider': 'PROVIDER', 'model': 'MODEL'},
  'summarization': {'provider': 'PROVIDER', 'model': 'MODEL'},
  'storage': {'backend': 'BACKEND'},
  'graphrag': {'enabled': False}
}
with open('CONFIG_PATH', 'w') as f:
    yaml.safe_dump(config, f, default_flow_style=False)
print('Config written.')
"
chmod 600 CONFIG_PATH
```

### Regression Test Pattern

```python
# Source: project test convention — see agent-brain-server/tests/
import re
from pathlib import Path

PLUGIN_ROOT = Path(__file__).parents[3] / "agent-brain-plugin"

REQUIRED_WIZARD_SECTIONS = {
    "agent-brain-setup.md": [
        "provider",          # Must ask about embedding provider
        "storage",           # Must ask about storage backend
    ],
    "agent-brain-config.md": [
        "AskUserQuestion",   # Must have interactive questions
        "ChromaDB",          # Must mention ChromaDB
        "PostgreSQL",        # Must mention PostgreSQL
        "Ollama",            # Must mention Ollama as free option
    ],
}

def test_wizard_sections_present():
    for filename, required_terms in REQUIRED_WIZARD_SECTIONS.items():
        content = (PLUGIN_ROOT / "commands" / filename).read_text()
        for term in required_terms:
            assert term in content, (
                f"{filename} is missing required wizard term: '{term}'. "
                f"Wizard regression detected — restore the setup flow."
            )
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| OpenAI-only config (just API keys) | Multi-provider wizard with Ollama, OpenAI, Gemini, Grok, Cohere | v3.0 / Phase 2 (2026-02-09) | Users no longer must pay for cloud APIs |
| Manual storage backend env var | Storage backend selection wizard in `/agent-brain-config` Step 5 | v6.0 / Phase 8 (2026-02-12) | PostgreSQL setup fully guided |
| No query mode guidance in setup | Need to add: query mode selection in wizard | Phase 22 (this phase) | Users discover correct mode for their use case |
| No regression tests for wizard content | Need to add: `test_plugin_wizard_spec.py` | Phase 22 (this phase) | Prevents silent regression |
| GraphRAG setup in separate docs only | Need to add: GraphRAG yes/no question in wizard | Phase 22 (this phase) | Users enable graph mode at setup time |

**Deprecated/outdated:**
- `--daemon` flag: Early versions of `/agent-brain-setup` used `agent-brain start --daemon`. This flag no longer exists — just `agent-brain start`. All wizard steps must use current CLI syntax.
- DOC_SERVE_URL / DOC_SERVE_STATE_DIR: Original env vars from pre-rename. Current vars are `AGENT_BRAIN_URL` / `AGENT_BRAIN_STATE_DIR`. Wizard must use current names.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| WIZARD-01 | `/agent-brain-setup` asks user about embedding provider (Ollama/OpenAI/Cohere/Gemini) | Existing `/agent-brain-config` Step 3 pattern; setup delegates but does not currently ask inline |
| WIZARD-02 | `/agent-brain-setup` asks user about summarization provider (Ollama/Anthropic/OpenAI/Gemini/Grok) | Same pattern as WIZARD-01; currently deferred to `/agent-brain-config` |
| WIZARD-03 | `/agent-brain-setup` asks user about storage backend (ChromaDB vs PostgreSQL) | Existing `/agent-brain-config` Step 5 has this; wizard must ensure setup also triggers it |
| WIZARD-04 | `/agent-brain-setup` asks whether to enable GraphRAG and which store type | New question; maps to `ENABLE_GRAPH_INDEX` + `graphrag.store_type` in config.yaml |
| WIZARD-05 | `/agent-brain-setup` asks user to choose default query mode (constrained to enabled indexes) | New question; modes: vector, bm25, hybrid, graph, multi — graph/multi only if GraphRAG enabled |
| WIZARD-06 | `/agent-brain-setup` asks about API keys for selected providers and writes `config.yaml` | Partial: `/agent-brain-config` does this; wizard must aggregate into single comprehensive config write |
| WIZARD-07 | `/agent-brain-setup` runs `agent-brain verify` after all choices to validate connectivity | Existing `agent-brain verify` command; currently in setup as Step 6 |
| WIZARD-08 | Wizard detects existing config and offers to update rather than overwrite | New: prevents wiping existing config when wizard re-run; detect and merge |
| WIZARD-09 | `tests/test_plugin_wizard_spec.py` asserts all required `AskUserQuestion` prompts are present in command files | New regression test; runs in `task before-push` |
| WIZARD-10 | `configuring-agent-brain` SKILL.md updated to document all wizard choices and corresponding config.yaml keys | Update to existing skill; planner maps to SKILL.md edit |
</phase_requirements>

---

## Open Questions

1. **Does `config.yaml` support a `query.default_mode` key today?**
   - What we know: The server's `QueryRequest` model has `mode: QueryMode = Field(default=QueryMode.HYBRID)` — this is a per-request default, not a global setting. `Settings` class has no `DEFAULT_QUERY_MODE` field.
   - What's unclear: Should the wizard write a `query.default_mode` key to config.yaml (requiring a server-side change to load it), or simply document the user's preference in a comment?
   - Recommendation: For Phase 22 (plugin/skill only, no server changes), document the preference as a comment in the generated config.yaml. Server-side default_mode support can be a future phase. WIZARD-05 should set the user's preference as a commented-out field with instructions.

2. **Is `/agent-brain-setup` the right vehicle for the full wizard, or should there be `/agent-brain-wizard`?**
   - What we know: `/agent-brain-setup` already exists and users know it. It currently has 5 steps. Expanding it to 8-10 steps with interactive questions makes it significantly longer.
   - What's unclear: Will a very long setup command become confusing?
   - Recommendation: Extend `/agent-brain-setup` — keep it as the canonical entry point. The new questions are additional steps, not replacements.

3. **Watch mode in wizard vs per-folder at index time?**
   - What we know: `watch_mode` is set per folder via `agent-brain folders add ./src --watch auto`, not in `config.yaml`. There is no global watch_mode setting.
   - What's unclear: Should the wizard mention watch mode at all if it can't configure it globally?
   - Recommendation: Include an informational step (no question) that tells the user: "Use `--watch auto` when adding folders to enable automatic re-indexing." This keeps the wizard complete without inventing new config semantics.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (existing, agent-brain-server) |
| Config file | `agent-brain-server/pyproject.toml` |
| Quick run command | `cd agent-brain-server && poetry run pytest tests/test_plugin_wizard_spec.py -x` |
| Full suite command | `cd agent-brain-server && poetry run pytest` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| WIZARD-09 | Regression: required AskUserQuestion prompts present in command markdown files | unit (file content) | `poetry run pytest tests/test_plugin_wizard_spec.py::test_wizard_sections_present -x` | No — Wave 0 |
| WIZARD-09 | Regression: storage backend section present in agent-brain-setup.md | unit | `poetry run pytest tests/test_plugin_wizard_spec.py::test_setup_asks_storage_backend -x` | No — Wave 0 |
| WIZARD-09 | Regression: provider question present in agent-brain-setup.md | unit | `poetry run pytest tests/test_plugin_wizard_spec.py::test_setup_asks_provider -x` | No — Wave 0 |
| WIZARD-09 | Regression: GraphRAG question present in agent-brain-setup.md | unit | `poetry run pytest tests/test_plugin_wizard_spec.py::test_setup_asks_graphrag -x` | No — Wave 0 |
| WIZARD-09 | Regression: query mode question present in agent-brain-setup.md | unit | `poetry run pytest tests/test_plugin_wizard_spec.py::test_setup_asks_query_mode -x` | No — Wave 0 |

### Sampling Rate

- **Per task commit:** `cd agent-brain-server && poetry run pytest tests/test_plugin_wizard_spec.py -x`
- **Per wave merge:** `cd agent-brain-server && poetry run pytest`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `agent-brain-server/tests/test_plugin_wizard_spec.py` — covers WIZARD-09 (all 5 regression assertions)

*(All other WIZARD-01 through WIZARD-08 requirements are markdown edits with no automated test — WIZARD-09 is the regression prevention mechanism for all of them.)*

---

## Sources

### Primary (HIGH confidence)

- Git history of `agent-brain-plugin/` — full commit log from f526ecf (initial plugin) through present; confirms wizard evolution
- `agent-brain-plugin/commands/agent-brain-config.md` (current) — confirms provider and storage backend wizard exists; confirms query mode and GraphRAG prompts are missing
- `agent-brain-plugin/commands/agent-brain-setup.md` (current) — confirms setup orchestrates but does not ask configuration questions inline
- `agent-brain-server/agent_brain_server/models/query.py` — confirms 5 QueryMode values: VECTOR, BM25, HYBRID, GRAPH, MULTI
- `agent-brain-server/agent_brain_server/config/settings.py` — confirms all configurable settings and their env var names

### Secondary (MEDIUM confidence)

- Git diff f526ecf → a731977 → 2d94700 → current — traces wizard prompt additions/removals across milestones
- `agent-brain-plugin/skills/configuring-agent-brain/references/configuration-guide.md` — confirms YAML schema including storage, graphrag, embedding, summarization sections

### Tertiary (LOW confidence)

- Phase 22 description in ROADMAP.md and STATE.md — asserts "wizard prompts have been lost" but git history shows the original wizard (f526ecf) also lacked most prompts. The regression is that no milestone ever built the full wizard; it grew incrementally and was never completed.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — plugin is markdown, existing patterns confirmed by reading live files and full git history
- Architecture: HIGH — wizard questions catalog derived directly from settings.py enum values and YAML schema
- Pitfalls: HIGH — config.yaml location bug confirmed by reading detection logic; GraphRAG/code-index dependency confirmed by reading SKILL.md
- Regression test approach: HIGH — pytest integration confirmed by reading pyproject.toml and existing test files

**Research date:** 2026-03-12
**Valid until:** 2026-04-12 (stable domain — plugin markdown, no external API dependencies)
