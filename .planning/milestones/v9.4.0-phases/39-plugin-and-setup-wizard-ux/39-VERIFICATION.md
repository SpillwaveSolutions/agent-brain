---
phase: 39-plugin-and-setup-wizard-ux
verified: 2026-03-20T01:59:19Z
status: human_needed
score: 5/6 must-haves verified
human_verification:
  - test: "Run /agent-brain:agent-brain-config and /agent-brain:agent-brain-install in a real Claude plugin session"
    expected: "Expected setup operations complete without repeated permission approvals for script execution and config edits"
    why_human: "Approval UX depends on runtime permission gate behavior that static analysis/tests cannot fully simulate"
  - test: "Run `agent-brain config wizard` interactively in a clean project"
    expected: "Step 7 shows AST+LangExtract option, Step 12 suggests discovered 8000-8300 free port, and written config persists graphrag/api selections"
    why_human: "Interactive prompt flow and operator UX quality need manual confirmation"
---

# Phase 39: Plugin & Setup Wizard UX Verification Report

**Phase Goal:** The setup wizard and plugin commands work without approval fatigue, have correct permission configurations, and offer AST+LangExtract as a first-class GraphRAG extraction option with automatic port discovery.
**Verified:** 2026-03-20T01:59:19Z
**Status:** human_needed
**Re-verification:** No - initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Running setup/install/config commands no longer triggers repeated runtime permission prompts for expected script execution and config edits | ? UNCERTAIN | Static evidence is strong (`setup-assistant` allowed tools + command routing + script-backed calls), but prompt-fatigue UX must be validated in a real plugin runtime |
| 2 | setup-assistant has scoped Bash permission for scripts and Write/Edit for config paths | ✓ VERIFIED | `agent-brain-plugin/agents/setup-assistant.md:23`-`33` includes scoped `Bash(...)`, `Write(...)`, `Edit(...)` entries including `~/.agent-brain/**` |
| 3 | Setup commands route through setup-assistant policy island | ✓ VERIFIED | `context: fork` + `agent: setup-assistant` present in all six setup-flow command files (`agent-brain-config.md`, `agent-brain-install.md`, `agent-brain-setup.md`, `agent-brain-init.md`, `agent-brain-start.md`, `agent-brain-verify.md`) |
| 4 | Wizard Step 7 exposes AST+LangExtract as first-class GraphRAG mode | ✓ VERIFIED | CLI prompt includes explicit option text in `agent-brain-cli/agent_brain_cli/commands/config.py:199`-`207`; plugin spec mirrors it in `agent-brain-plugin/commands/agent-brain-config.md:557`-`562` |
| 5 | Wizard Step 12 auto-discovers an available API port in configured range | ✓ VERIFIED | `_find_available_api_port(8000, 8300)` implemented in `agent-brain-cli/agent_brain_cli/commands/config.py:34`-`45` and used as prompt default at `:209`-`:241` |
| 6 | Wizard persists selected GraphRAG extraction mode and discovered/suggested port to config output | ✓ VERIFIED | Config write contains `graphrag` and `api` blocks in `agent-brain-cli/agent_brain_cli/commands/config.py:243`-`291`; covered by passing tests in `agent-brain-cli/tests/commands/test_config_wizard.py:117`-`189` |

**Score:** 5/6 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `agent-brain-plugin/agents/setup-assistant.md` | Setup assistant tool permission contract | ✓ VERIFIED | Exists, substantive policy block, referenced by command frontmatter via `agent: setup-assistant` |
| `agent-brain-plugin/commands/agent-brain-config.md` | Script-first setup flow and updated Step 7/12 wizard contract | ✓ VERIFIED | Uses direct `ab-setup-check.sh` invocation and contains AST+LangExtract + auto-port docs |
| `agent-brain-plugin/commands/agent-brain-install.md` | Script-backed install checks | ✓ VERIFIED | References `ab-pypi-version.sh` and `ab-uv-check.sh`; bound to setup-assistant |
| `agent-brain-plugin/scripts/ab-pypi-version.sh` | Canonical PyPI version resolver | ✓ VERIFIED | Exists, executable (`-rwxr-xr-x`), non-stub error-handled implementation |
| `agent-brain-plugin/scripts/ab-uv-check.sh` | Canonical uv availability checker | ✓ VERIFIED | Exists, executable (`-rwxr-xr-x`), returns availability + install hint |
| `agent-brain-plugin/tests/test_setup_permissions_spec.py` | Regression checks for policy island and script wiring | ✓ VERIFIED | Exists and passes (`5 passed`) |
| `agent-brain-cli/agent_brain_cli/commands/config.py` | Wizard implementation for extraction mode + port discovery | ✓ VERIFIED | Implements GraphRAG options, port scan, persisted `api`/`graphrag` config |
| `agent-brain-cli/tests/commands/test_config_wizard.py` | Regression coverage for Step 7/12 behavior | ✓ VERIFIED | Exists and passes (`6 passed`), includes extraction + port assertions |
| `agent-brain-plugin/tests/test_plugin_wizard_spec.py` | Plugin wizard markdown contract checks | ✓ VERIFIED | Exists and passes (`17 passed`), includes Step 7/12 assertions |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `agent-brain-plugin/commands/agent-brain-config.md` | `agent-brain-plugin/scripts/ab-setup-check.sh` | Direct script command substitution | ✓ WIRED | `SETUP_STATE=$("$SCRIPT")` present at `agent-brain-plugin/commands/agent-brain-config.md:60` (no `bash "$SCRIPT"`) |
| `agent-brain-plugin/commands/agent-brain-install.md` | `agent-brain-plugin/scripts/ab-pypi-version.sh` + `ab-uv-check.sh` | Script-backed resolver/check flow | ✓ WIRED | Script names referenced and used in install logic at `agent-brain-plugin/commands/agent-brain-install.md:66` and `:150` |
| Setup-flow command frontmatter | `agent-brain-plugin/agents/setup-assistant.md` | `context: fork` + `agent: setup-assistant` | ✓ WIRED | Present in all six command files; enforces policy-island routing |
| `agent-brain-cli/agent_brain_cli/commands/config.py` | `agent-brain-cli/tests/commands/test_config_wizard.py` | Prompt/output + persisted config assertions | ✓ WIRED | Tests explicitly assert AST+LangExtract and discovered API port persistence |
| `agent-brain-plugin/commands/agent-brain-config.md` | `agent-brain-plugin/tests/test_plugin_wizard_spec.py` | Markdown contract assertions | ✓ WIRED | Test asserts Step 7 AST+LangExtract wording and Step 12 auto-port text |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| _None declared_ | `39-01-PLAN.md`, `39-02-PLAN.md` | `requirements: []` in both plans | ✓ SATISFIED | `39-01-PLAN.md:19`, `39-02-PLAN.md:13` |
| _Orphaned requirement check_ | `.planning/REQUIREMENTS.md` | Additional Phase 39 requirement IDs mapped in requirements doc | ✓ SATISFIED | No Phase 39 mappings present; REQUIREMENTS scope is v9.2.0 doc-audit phases |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| _None detected_ | - | No TODO/FIXME/placeholders/empty impl stubs in phase-modified files | ℹ️ Info | No blocker or warning anti-patterns found |

### Human Verification Required

### 1. Plugin Approval-Fatigue Runtime Check

**Test:** Run `/agent-brain:agent-brain-config` and `/agent-brain:agent-brain-install` end-to-end in a real Claude plugin session.
**Expected:** Expected script execution and config edits run without repeated approval prompts.
**Why human:** Approval UX is enforced by runtime permission gates and cannot be fully validated by static checks.

### 2. Interactive Wizard UX Check

**Test:** Run `agent-brain config wizard` in a clean project and complete Step 7 and Step 12.
**Expected:** Step 7 offers AST+LangExtract as explicit option; Step 12 suggests discovered free port in 8000-8300; resulting `.agent-brain/config.yaml` contains selected `graphrag` + `api` values.
**Why human:** Interactive prompt clarity and real operator flow are user-experience validations.

---

_Verified: 2026-03-20T01:59:19Z_
_Verifier: Claude (gsd-verifier)_
