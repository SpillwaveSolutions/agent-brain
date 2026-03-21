# Phase 34: Config Command Spec — Context

**Gathered:** 2026-03-20
**Status:** Ready for planning
**Source:** Claude assumptions (auto-generated from SPEC.md and existing command file analysis)

<domain>
## Phase Boundary

This phase formalizes the `/agent-brain:agent-brain-config` wizard command by reconciling the **SPEC.md** (contract) with the **existing command implementation** (1078-line `agent-brain-config.md`). The SPEC describes a 12-step wizard; the command file already implements most of it. The deliverable is: ensure spec and implementation are in sync, fill any gaps, and add the file watcher step that was previously missing.

**What this phase delivers:**
1. Audit of spec-vs-implementation drift (SPEC.md vs agent-brain-config.md)
2. Fix any drift found — update the command file to match the spec
3. Ensure the file watcher configuration step (Step 9 in SPEC) is fully implemented in the command
4. Update SPEC.md version info and cross-references if needed
5. Add tests or verification that the wizard steps match the spec

**What this phase does NOT deliver:**
- No new CLI commands or server changes
- No new provider integrations
- No changes to config.yaml schema (only ensuring the wizard writes correct keys)
</domain>

<decisions>
## Implementation Decisions

### Scope: Spec-Command Reconciliation
- The SPEC.md in this phase directory is the source of truth for wizard behavior
- The command file (`agent-brain-plugin/commands/agent-brain-config.md`) is the implementation
- Any drift between the two is a bug — fix the command to match the spec
- The SPEC describes 12 steps; verify all 12 are implemented in the command

### File Watcher Step
- Step 9 in the SPEC covers file watcher configuration
- This step should offer: Disabled (default) or Enabled with configurable debounce
- Global debounce is env-var only (`AGENT_BRAIN_WATCH_DEBOUNCE_SECONDS`), not in config.yaml
- Per-folder watch mode is set at index time via `agent-brain folders add --watch auto`
- The wizard should educate users about both global and per-folder watcher controls

### Validation Approach
- Create a checklist mapping each SPEC step to its command implementation
- Verify config keys written by each step match what the SPEC documents
- Verify AskUserQuestion options in the command match SPEC options
- Verify error states and fallbacks are implemented

### Command File Structure
- The command file is markdown (Claude Code plugin format) — not Python code
- Changes are to markdown instruction content, not to CLI source code
- The command already has Steps 1-12 structure; check completeness of each

### Claude's Discretion
- Exact wording of wizard prompts and help text
- Order of verification (top-down through steps is fine)
- Whether to split the work into one or two plans
- How to structure the drift audit (table vs checklist)
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Spec and Implementation
- `.planning/phases/34-config-command-spec/SPEC.md` — The 12-step wizard specification (source of truth)
- `agent-brain-plugin/commands/agent-brain-config.md` — Current command implementation (1078 lines)

### Related Documentation
- `docs/CONFIGURATION_REFERENCE.md` — User-facing config documentation (must stay consistent)
- `docs/SETUP_PLAYGROUND.md` — Setup flow that references the config wizard

### Plugin Structure
- `agent-brain-plugin/plugin.json` — Plugin manifest (for command registration)
- `agent-brain-plugin/scripts/ab-setup-check.sh` — Pre-flight detection script referenced by Step 2
</canonical_refs>

<specifics>
## Specific Ideas

- The SPEC title says "9-step wizard" but the SPEC body describes 12 steps — the roadmap text is outdated (it says "9-step wizard formalized"). The actual spec has 12 steps. Document this discrepancy and use 12 as the correct count.
- Step 9 (File Watcher) was the last step added — it may have the least complete implementation in the command file.
- Steps 10 (Reranking), 11 (Chunking), and 12 (Server & Deployment) were added after the original 9-step design — verify they are fully specified and implemented.
- The `ab-setup-check.sh` script is referenced in Step 2 — verify it exists and its output format matches what the SPEC documents.
</specifics>

<deferred>
## Deferred Ideas

- Config validation command (`agent-brain config validate`) — future phase
- Config migration tool for upgrading between config schema versions — future phase
- Interactive config diff showing what changed — future phase
</deferred>

---

*Phase: 34-config-command-spec*
*Context gathered: 2026-03-20 via Claude assumptions*
