---
phase: 59-cli-prompts-resources-commands
verified: 2026-06-08T22:30:00Z
status: passed
score: 4/4 must-haves verified
re_verification:
  previous_status: incomplete
  previous_score: N/A
  note: "Prior verifier attempt failed mid-run due to API connectivity; this is a fresh initial verification."
---

# Phase 59: CLI prompts + resources commands Verification Report

**Phase Goal:** Expose the MCP `prompts/get` + `resources/list` + `resources/read` surfaces via human-friendly CLI commands. Operators can invoke any of the 6 v1 prompts, enumerate all static + templated URIs, and read content with correct sandboxing and binary/JSON content-type handling.
**Verified:** 2026-06-08T22:30:00Z
**Status:** passed
**Re-verification:** No — initial verification (prior attempt errored on connectivity, this run starts fresh).

## STATUS: passed

## Goal Achievement

### Observable Truths

| #   | Truth                                                                                          | Status     | Evidence                                                                                                                                                  |
| --- | ---------------------------------------------------------------------------------------------- | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `agent-brain prompt <name>` expands any of 6 v1 prompts; unknown names exit non-zero with available list | ✓ VERIFIED | `commands/prompt.py` line 74 declares `@click.command("prompt")`; lines 140-156 implement McpError → list_prompts() fallback → UsageError exit 2; `tests/test_prompt_command.py` (13 tests pass) |
| 2   | `agent-brain resources list` enumerates 5 static + 4 templated URIs with mime types            | ✓ VERIFIED | `commands/resources.py` line 72 `@resources_group.command("list")`; calls both `list_resources()` + `list_resource_templates()` (lines 91-92) and renders rich.Table with URI/Mime/Type columns |
| 3   | `agent-brain resources read <uri>` content-type dispatch (JSON pretty / text passthrough / binary refused without --output-file) | ✓ VERIFIED | `commands/resources.py` lines 232-264 implement dispatch matrix; binary-without-output-file raises `click.UsageError("Resource is binary ...; pass --output-file PATH to save")` exit 2; `_JSON_MIME_LITERALS` triggers `json.dumps(parsed, indent=2)` |
| 4   | `agent-brain resources read file:///disallowed/path` rejected with server `outside_indexed_roots` reason VERBATIM (no CLI pre-check) | ✓ VERIFIED | `commands/resources.py` lines 174-180 catch `McpError`, surface VERBATIM via `click.echo(f"Error reading {uri}: {exc}", err=True)` + `sys.exit(2)`; grep for `outside_indexed_roots` in resources.py = **0 occurrences** (architectural pin); test at `tests/test_resources_command.py:455` + e2e at `tests/integration/test_resources_e2e.py:171` |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact                                                                          | Expected                                                  | Status     | Details                                                                              |
| --------------------------------------------------------------------------------- | --------------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------ |
| `agent-brain-cli/agent_brain_cli/commands/prompt.py`                              | Click command for `prompts/get`                            | ✓ VERIFIED | 191 LOC, `@click.command("prompt")`, calls `open_mcp_backend(ctx)`, McpError → UsageError fallback wired |
| `agent-brain-cli/agent_brain_cli/commands/resources.py`                           | Click sub-group with `list` + `read`                       | ✓ VERIFIED | 268 LOC, `@click.group("resources")` + 2 subcommands, content-type dispatch matrix at lines 232-264 |
| `agent-brain-cli/agent_brain_cli/client/protocol.py` (McpBackend Protocol)        | 5-method Protocol; NO `__enter__/__exit__`                 | ✓ VERIFIED | Lines 131-170 declare McpBackend; verified NO `__enter__/__exit__` on McpBackend (only on BackendClient at lines 53-60 — distinct Protocol) |
| `agent-brain-cli/agent_brain_cli/client/transport.py` (`open_mcp_backend` factory) | Single-point `--transport mcp` enforcement                | ✓ VERIFIED | Used by both `prompt.py:133` and `resources.py:89,170`                                |
| `agent-brain-mcp/agent_brain_mcp/client.py` (10 wire bodies)                      | 5 methods × 2 backends wired via Pattern A                  | ✓ VERIFIED | `session.get_prompt/list_prompts/list_resources/list_resource_templates/read_resource` references count = 16; sentinel `"Wired in Phase 59 Plan 02"` count = **0** (removed) |
| `agent-brain-cli/agent_brain_cli/cli.py` (registration)                            | Both commands registered                                  | ✓ VERIFIED | Line 164: `cli.add_command(prompt_command, name="prompt")`; line 165: `cli.add_command(resources_group, name="resources")` |
| `agent-brain-cli/tests/test_prompt_command.py`                                    | CliRunner unit tests for prompt command                   | ✓ VERIFIED | 13 tests; runs as part of 545-test CLI suite (orchestrator confirmed)                |
| `agent-brain-cli/tests/test_resources_command.py`                                 | CliRunner unit tests for resources list/read              | ✓ VERIFIED | 20 tests (16 standalone + 4 parametrized mime dispatch matrix)                       |
| `agent-brain-cli/tests/integration/test_resources_e2e.py`                         | End-to-end test using real subprocess + seeded corpus     | ✓ VERIFIED | 3 e2e tests including `test_resources_read_file_outside_indexed_roots_exits_2` at line 171 (skips gracefully without OPENAI_API_KEY) |
| `agent-brain-mcp/tests/test_mcp_backend_protocol_skeleton.py` (negative pin)      | `DocServeClient ⊄ McpBackend` test                        | ✓ VERIFIED | `test_doc_serve_client_does_not_satisfy_mcp_backend` at line 57 with assertion message at line 69 |

### Key Link Verification

| From                                                       | To                                              | Via                                                     | Status   | Details                                                            |
| ---------------------------------------------------------- | ----------------------------------------------- | ------------------------------------------------------- | -------- | ------------------------------------------------------------------ |
| `prompt.py`                                                | `transport.open_mcp_backend`                    | import + call at line 133                               | ✓ WIRED  | Sole `--transport mcp` enforcement point                            |
| `resources.py` (list + read)                               | `transport.open_mcp_backend`                    | import + calls at lines 89, 170                         | ✓ WIRED  | Both subcommands inherit single-point contract                      |
| `prompt.py` McpError catch                                 | `backend.list_prompts()` fallback              | lines 140-156                                           | ✓ WIRED  | Builds sorted CSV of available names; defensive secondary-error path |
| `resources.py read` McpError                               | stderr verbatim                                 | `click.echo(f"Error reading {uri}: {exc}", err=True)`  | ✓ WIRED  | No CLI pre-check, no paraphrase (lines 174-180)                    |
| `cli.py` top-level group                                    | `prompt_command` + `resources_group`            | `cli.add_command(...)` at lines 164-165                | ✓ WIRED  | Both commands discoverable in `agent-brain --help`                  |
| `McpBackend` Protocol                                       | `McpStdioBackend` + `McpHttpBackend`            | Pattern A `asyncio.run(_async_*())` per method          | ✓ WIRED  | 10 wire bodies replace Plan 59-01 sentinels (sentinel count = 0)    |

### Requirements Coverage

| Requirement | Source Plan(s) | Description                                                                                                                | Status      | Evidence                                                                                                                |
| ----------- | -------------- | -------------------------------------------------------------------------------------------------------------------------- | ----------- | ----------------------------------------------------------------------------------------------------------------------- |
| CLI-MCP-05  | 59-01, 59-02   | `agent-brain prompt <name>` calls MCP `prompts/get`, prints expanded content (6 v1 prompts)                              | ✓ SATISFIED | Plan 59-02 ships `commands/prompt.py` + 13 CliRunner tests; REQUIREMENTS.md line 102 marked Complete                     |
| CLI-MCP-06  | 59-03          | `agent-brain resources list` enumerates 5 static + 4 templated URIs                                                       | ✓ SATISFIED | `resources_group.command("list")` merges `list_resources()` + `list_resource_templates()`; REQUIREMENTS.md line 103 marked Complete |
| CLI-MCP-07  | 59-03          | `agent-brain resources read <uri>` content-type dispatch + file:// sandbox respect                                        | ✓ SATISFIED | Content-type dispatch lines 232-264; sandbox surfacing verbatim at lines 174-180; REQUIREMENTS.md line 104 marked Complete |

All plan-declared requirement IDs accounted for. No orphans — REQUIREMENTS.md mapping for Phase 59 lists exactly CLI-MCP-05/06/07 and all three appear in the 3 plans' frontmatter.

### Architectural Decisions (Load-Bearing) — Survived

| Decision                                                                                       | Status     | Evidence                                                                                              |
| ---------------------------------------------------------------------------------------------- | ---------- | ----------------------------------------------------------------------------------------------------- |
| `DocServeClient ⊄ McpBackend` negative pin test exists                                          | ✓ PASSED   | `agent-brain-mcp/tests/test_mcp_backend_protocol_skeleton.py:57` with verbatim assertion message       |
| `McpBackend` Protocol does NOT declare `__enter__`/`__exit__` (Pattern A: fresh client per call) | ✓ PASSED   | `protocol.py` lines 131-170: only 5 method signatures (`get_prompt`, `list_prompts`, `list_resources`, `list_resource_templates`, `read_resource`); no context-manager surface |
| §3.5 no-silent-fallback: unknown prompt + outside-sandbox file:// both surface server verdict verbatim | ✓ PASSED   | `prompt.py:152-156` (alphabetized available list), `resources.py:179` (`click.echo(f"Error reading {uri}: {exc}", err=True)`); `outside_indexed_roots` grep in resources.py = 0 |
| Plan 59-02 deviation note that removed `with backend:` wrapper                                  | ✓ PASSED   | Neither `commands/prompt.py` nor `commands/resources.py` uses `with backend:` — confirmed via reading both files |
| Sentinel `"Wired in Phase 59 Plan 02"` removed from `client.py` after wiring                    | ✓ PASSED   | `grep -c` returns 0; 16 `session.*` SDK references confirm wire bodies present                         |

### Anti-Patterns Found

None. Spot-checks of `commands/prompt.py` and `commands/resources.py`:
- No TODO/FIXME/XXX/HACK markers in either source file
- No `return null`/empty-stub return shapes
- No `console.log`-only handlers
- All error paths surface real errors (UsageError exit 2, generic exit 1, base64-decode exit 3) — no swallowed exceptions

### Quality Gates (Confirmed by Orchestrator)

| Gate                                  | Status   | Source                              |
| ------------------------------------- | -------- | ----------------------------------- |
| `task before-push` exits 0            | ✓ PASSED | Wave 3 executor confirmed           |
| agent-brain-mcp tests pass            | ✓ PASSED | 514 tests pass                      |
| agent-brain-cli tests pass            | ✓ PASSED | 545 tests pass (excluding slow integration) |
| No regressions in prior phases        | ✓ PASSED | Phases 56-58 architectural pins survive (BackendClient + McpBackend isinstance pins, Plan 59-01 inverted sentinel tests) |

### Human Verification Required

None for `passed` status. All 4 must-haves verified programmatically. The e2e integration test at `tests/integration/test_resources_e2e.py` exercises the live subprocess path against a seeded UDS corpus — when run with `OPENAI_API_KEY` present, it provides production-equivalent confidence; orchestrator confirmed `task before-push` passes which includes the unit-test branch coverage.

### Gaps Summary

None. All 4 ROADMAP success criteria green; all 3 requirement IDs (CLI-MCP-05/06/07) marked Complete in REQUIREMENTS.md and traceable to specific code + tests; all load-bearing architectural decisions verified (negative pin test exists, Protocol surface unchanged, sentinel removed, no-silent-fallback contract honored). Phase 59 is shippable as documented.

---

_Verified: 2026-06-08T22:30:00Z_
_Verifier: Claude (gsd-verifier)_
