# Low-Hanging Fruit Triage & Cross-Referenced Issue Tracking

## Context

`.planning/STATE.md` is pinned at **v9.6.0 / Phase 46**, but the repo has shipped **v10.0.6** (releases v9.3.0 → v10.0.6 happened between then and now). Ten todos sit in `.planning/todos/pending/` — **six are demonstrably resolved** in shipped code, **one is partially done**, and **three are still real bugs/UX gaps**.

The goal of this work:
1. Close the planning-artifact drift (archive stale todos, sync STATE.md)
2. Promote the remaining three items into trackable GitHub issues with bidirectional cross-references (todo → issue → commit)
3. Implement the three items in low-to-high risk order, each in its own commit referencing its issue

This converts ad-hoc markdown notes into a queryable, linked work graph and clears noise so the next milestone (Phase 47) starts from a true picture of the project.

## Phase Plan

### Step 0 — Clean feature branch
- Branch from `main`: `git checkout -b chore/triage-pending-todos-v10`
- Verify clean tree before starting.

### Step 1 — Archive 6 stale todos

For each file in `.planning/todos/pending/` that maps to shipped work, prepend a `## Closed` block (release tag, commit SHA, brief evidence), then move to `.planning/todos/done/`.

| Pending file | Closed by |
|---|---|
| `2026-03-19-migrate-gemini-provider-from-deprecated-google-generativeai-to-google-genai-package.md` | commit `b19ab35` (Phase 41) — pyproject.toml `google-genai ^1.0.0` |
| `2026-03-19-suppress-or-fix-chromadb-telemetry-posthog-capture-argument-error-on-startup.md` | `agent-brain-server/agent_brain_server/api/main.py` sets `ANONYMIZED_TELEMETRY=False` |
| `2026-03-19-fix-agent-brain-start-timeout-too-short-for-sentence-transformers-reranker-first-init.md` | start command default param now `120` (was 30) |
| `2026-03-19-fix-indexing-jobs-failing-with-broken-pipe-under-concurrent-ollama-load.md` | retry logic in `providers/embedding/ollama.py` for `BrokenPipeError`/`ConnectionResetError` |
| `2026-03-19-add-ast-for-code-plus-langextract-for-docs-as-first-class-graphrag-option-in-agent-brain-config-wizard.md` | v9.3.0 — option listed in `agent-brain-plugin/commands/agent-brain-config.md` Step 7 |
| `2026-03-19-auto-discover-available-port-in-agent-brain-config-step-12-deployment-wizard-to-prevent-multi-project-port-conflicts.md` | port scan pattern present in `agent-brain-start.md` (8000–8100) |
| `2026-03-18-review-and-merge-object-pascal-support-pr-115.md` | merged — Phase 42 commits (`feat(42): add object-pascal preset alias`, `.dpk` extension) |

### Step 2 — Sync `.planning/STATE.md`

Replace the milestone-summary block + "Current Position" + "Pending Todos" sections to reflect:
- Shipped: v9.6.0, v9.7.0+ (verify versions from `git tag --sort=-creatordate`), v10.0.0–v10.0.6
- Stopped At / Next Action: realistic next-phase prompt (or "ready for v10.1 milestone planning")
- Pending Todos: only the 3 items that move to GitHub issues
- Update `last_updated`

### Step 3 — Create 3 GitHub issues with cross-references

Use `gh issue create` against `SpillwaveSolutions/agent-brain`. Each issue body must include:
- Symptom + reproduction (copied from the todo file)
- Affected files (concrete paths)
- Acceptance criteria
- `Source todo: .planning/todos/pending/<file>.md`

Then **edit each pending todo file** to prepend a `Tracked in: #NNN` line — the bidirectional link.

| Issue | Title | Source todo |
|---|---|---|
| A | `fix(server): resolve chroma/cache dirs relative to AGENT_BRAIN_STATE_DIR, not CWD` | `2026-03-19-fix-chroma-db-and-cache-dirs-resolving-relative-to-cwd...md` |
| B | `feat(plugin): pre-authorize setup-assistant agent on 6 setup commands to eliminate approval fatigue` | `2026-03-19-eliminate-approval-fatigue-in-agent-brain-plugin-setup-commands...md` |
| C | `chore(plugin): close permission scope gaps in setup-assistant (Bash + Write/Edit paths)` | `2026-03-19-fix-two-permission-gaps-in-setup-assistant-agent-scoped-bash-and-write-edit...md` |

Issues A, B, C must each link to each other (`Related: #B, #C`) so reviewers see the cluster.

### Step 4 — Implement Issue C (permission scope gaps, smallest)

Verify that the setup-assistant agent definition at `agent-brain-plugin/agents/setup-assistant.md` (or similar) has:
- `Bash(~/.claude/plugins/agent-brain/scripts/*)`
- `Write/Edit(~/.agent-brain/**)`
- `Write/Edit(~/.config/agent-brain/**)` (per memory note about config migration)

If anything missing → add it. If all present → close issue C as "already implemented in last_validated 2026-03-16" with link to the commit that added them.

Commit message: `chore(plugin): verify setup-assistant permission scopes (closes #C)`

### Step 5 — Implement Issue B (pre-authorize 6 setup commands)

For each command file in `agent-brain-plugin/commands/`:
- `agent-brain-config.md`
- `agent-brain-install.md`
- `agent-brain-setup.md`
- `agent-brain-init.md`
- `agent-brain-start.md`
- `agent-brain-verify.md`

Verify and (if missing) add YAML frontmatter binding to the pre-authorized agent. The pattern to use is the one already established in this repo — check `agent-brain-plugin/commands/agent-brain-config.md` first to see the current frontmatter shape; mirror it for consistency. **Do not invent a new convention** — reuse what other commands in this plugin already use.

⚠️ **Memory note** (`feedback_auto_mode_agent_config_edits.md`): edits under `.claude/agents/` and `.claude/commands/` can be blocked by auto-mode even with plan approval. These edits target `agent-brain-plugin/commands/` (not `.claude/commands/`), so should be fine — but if blocked, fall back to single-message batched edits.

Commit message: `feat(plugin): bind setup-assistant to setup commands (closes #B)`

### Step 6 — Implement Issue A (Chroma/cache path resolution, highest risk)

Concrete change:
- `agent-brain-server/agent_brain_server/config/settings.py:34-35` — replace `./chroma_db` / `./bm25_index` defaults so they resolve via `AGENT_BRAIN_STATE_DIR` (which already defaults to `~/.agent-brain/<project>/`).
- Validate the lifespan/resolution path. The `test_lifespan_path_resolution.py` test (if it exists per agent report) is the regression anchor — add cases if missing.
- Affected files (representative): `config/settings.py`, `storage/vector_store.py`, BM25 index init in `services/`.

**Migration concern**: existing users may have `./chroma_db` next to their `pyproject.toml` from prior runs. Approach:
- On startup, if old `./chroma_db` exists at CWD **and** new path is empty, log a warning with a one-liner migration command. Do **not** auto-move (silent data motion is dangerous).
- Document in CHANGELOG.

Commit message: `fix(server): resolve chroma/bm25 dirs under AGENT_BRAIN_STATE_DIR (closes #A)`

### Step 7 — Validation (MANDATORY, per CLAUDE.md)

Run from repo root:
1. `task before-push` — must exit 0 (Black, Ruff, mypy strict, pytest)
2. `task pr-qa-gate` — must exit 0
3. Spot-check: start a fresh `agent-brain-server`, confirm Chroma writes under `~/.agent-brain/<project>/data/chroma_db`, not `./chroma_db`
4. Spot-check: run `/agent-brain:agent-brain-config` and confirm no permission prompts on commands that were bound

### Step 8 — PR

Single PR titled: `chore: triage stale todos, track remaining as issues, close 3 (#A, #B, #C)`

Body includes:
- Table of triaged todos with closing release links
- The three issue numbers with one-line descriptions
- Test plan checklist

After PR is open, copy this plan to `docs/plans/2026-05-27-low-hanging-fruit-triage.md` per repo convention (CLAUDE.md planning rule).

## Critical Files

- `.planning/todos/pending/*.md` — 7 files moving, 3 getting `Tracked in: #NNN` headers
- `.planning/todos/done/` — destination for archived files
- `.planning/STATE.md` — milestone summary refresh
- `agent-brain-server/agent_brain_server/config/settings.py` — Chroma/BM25 path defaults
- `agent-brain-server/agent_brain_server/api/main.py` — verify lifespan path resolution (read-only check)
- `agent-brain-plugin/commands/agent-brain-{config,install,setup,init,start,verify}.md` — frontmatter additions
- `agent-brain-plugin/agents/setup-assistant.md` (or wherever the agent lives) — permission scope verification

## Reuse Notes

- Existing path-resolution patterns: the server already resolves `AGENT_BRAIN_STATE_DIR` somewhere (per Phase 109 multi-instance architecture). Find and reuse — do not introduce a parallel resolver.
- Existing pre-auth frontmatter: copy whatever shape is already used by the first command that has it.
- Existing migration-warning helpers: search for prior "old path detected" warnings before adding a new one.

## Verification

End-to-end check after all 3 commits land locally, before pushing:

```bash
# 1. All quality gates green
task before-push && task pr-qa-gate

# 2. Storage path verification
rm -rf /tmp/ab-verify && mkdir /tmp/ab-verify && cd /tmp/ab-verify
agent-brain init && agent-brain start
agent-brain index ./README.md  # any test file
ls ~/.agent-brain/*/data/chroma_db  # should exist
ls ./chroma_db 2>/dev/null         # should NOT exist

# 3. Permission prompt check (manual)
# In a fresh Claude Code session, run /agent-brain:agent-brain-config and
# confirm no Bash/Write approval prompts on the 6 setup commands.

# 4. Optional: scripts/quick_start_guide.sh end-to-end
./scripts/quick_start_guide.sh
```

Only push after all four pass.
