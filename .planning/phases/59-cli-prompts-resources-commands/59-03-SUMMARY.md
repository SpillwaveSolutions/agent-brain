---
phase: 59-cli-prompts-resources-commands
plan: 03
subsystem: cli
tags: [mcp, click, resources, content-type, sandbox, cli-mcp-06, cli-mcp-07]

# Dependency graph
requires:
  - phase: 56-cli-mcp-skeleton
    provides: BackendClient + Pattern A skeleton-first (Plan 56-03)
  - phase: 57-cli-mcp-wire
    provides: Pattern A asyncio.run sync facade + verbatim §3.5 wording (Plan 57-02..03) + tests/integration/_corpus.py seeder (Plan 57-02)
  - phase: 58-mcp-helper-commands
    provides: AGENT_BRAIN_* env-strip latent-bug guard pattern (Plan 58-03)
  - phase: 59-cli-prompts-resources-commands
    provides: McpBackend Protocol + 10 wire bodies + open_mcp_backend factory (Plan 59-01) + agent-brain prompt command + commands/prompt.py shape (Plan 59-02)
provides:
  - "agent-brain resources Click sub-group with list + read subcommands"
  - "Content-type dispatch matrix at the CLI command layer (JSON pretty / text passthrough / binary --output-file gate)"
  - "Server-only file:// sandbox enforcement pattern — McpError verbatim surfacing, NO CLI-side pre-check"
  - "End-to-end integration test layering: Layer 1 (CliRunner+mock backend) + Layer 2 (real subprocess + seeded UDS corpus)"
affects:
  - 60+ (subprocess hygiene + 1000-invocation orphan test owns the persistent-subprocess refactor — Plan 59-03 inherits Pattern A unchanged)
  - any future MCP-only command needing content-type dispatch — clone the resources read pattern verbatim

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Click sub-group registration: @click.group('resources') with @resources_group.command('list') + @resources_group.command('read') subcommands — mirrors the Phase 58 @click.group('mcp') start/stop pattern verbatim"
    - "Content-type dispatch matrix: module-level constants _TEXT_MIME_PREFIXES, _TEXT_MIME_LITERALS, _JSON_MIME_LITERALS for mime classification (grep-friendly + future maintenance)"
    - "3-tier exit code scheme on read: exit 1 = server/wire errors + empty contents; exit 2 = usage errors + sandbox deny + missing --transport mcp; exit 3 = blob base64-decode failures on --output-file paths"
    - "Server-only sandbox surfacing: CLI does NOT have an outside_indexed_roots literal — server verdict is surfaced VERBATIM via the McpError repr (architectural decision pin; grep returns 0 in resources.py)"
    - "AGENT_BRAIN_* env-strip latent-bug guard carry-forward from Phase 58: integration test strips AGENT_BRAIN_URL / AGENT_BRAIN_TRANSPORT / AGENT_BRAIN_MCP_URL / AGENT_BRAIN_MCP_TRANSPORT before each subprocess.run"
    - "--output-file universal escape hatch: accepts BOTH text (UTF-8-encode → write_bytes) AND binary (base64-decode → write_bytes); uniform user mental model 'save resource to disk'"

key-files:
  created:
    - agent-brain-cli/agent_brain_cli/commands/resources.py (~245 LOC after Black: @click.group + 2 subcommands + content-type dispatch helpers + 3 mime classification constants)
    - agent-brain-cli/tests/test_resources_command.py (20 CliRunner tests — 16 standalone + 4 parametrized mime-dispatch matrix)
    - agent-brain-cli/tests/integration/test_resources_e2e.py (3 end-to-end tests + env-strip helper + seeded_state_dir fixture; skips gracefully without OPENAI_API_KEY)
  modified:
    - agent-brain-cli/agent_brain_cli/commands/__init__.py (+2 LOC: resources_group export + __all__ entry)
    - agent-brain-cli/agent_brain_cli/cli.py (+2 LOC: import + cli.add_command(resources_group, name='resources'))

key-decisions:
  - "Content-type dispatch matrix lives entirely at the CLI command layer (commands/resources.py read_command). The backend.read_resource() return shape is preserved as the raw MCP wire dict (per Plan 59-01 / 59-02 decision: dict[str, Any]). The command does the JSON pretty / text passthrough / binary gate decision based on contents[0].mimeType + presence of text-vs-blob keys."
  - "Server-only file:// sandbox enforcement: the CLI does NOT pre-check URIs against indexed roots. The agent-brain-mcp server's McpError with outside_indexed_roots reason in the error message/data is surfaced VERBATIM to stderr via click.echo(f'Error reading {uri}: {exc}', err=True) followed by sys.exit(2). Grep returns ZERO occurrences of the outside_indexed_roots literal in resources.py — proves the architectural pin."
  - "--output-file is the universal escape hatch for BOTH text and binary content. The user's mental model is 'save resource to disk'; forcing different commands for text vs binary would break that. Implementation: blob → base64.b64decode → write_bytes; text → utf-8 encode → write_bytes. Both echo `wrote {N} bytes to {path}` confirmation."
  - "3-tier exit code scheme: exit 1 = server/wire errors + empty contents (operationally 'something went wrong'); exit 2 = usage errors + sandbox deny + missing --transport mcp (operationally 'you misused the CLI or the server said no'); exit 3 = blob base64-decode failures on --output-file paths (operationally 'the server returned malformed binary content'). Mirrors the CONTEXT.md Claude's-discretion exit-code recommendation."
  - "Binary-without-output-file rejection via click.UsageError (exit 2). The exact rejection message is `Resource is binary ({mimeType}); pass --output-file PATH to save` — grep-stable wording so future maintainers can find the rejection site by literal substring. click.UsageError is Click's standard channel for exit 2 + stderr surfacing; the CLI does NOT manually format the error."
  - "End-to-end integration test layering matches the Phase 57 / 58 precedent. Layer 1 (tests/test_resources_command.py) uses CliRunner + mocked backend for fast (~0.3s) unit-level coverage of every branch. Layer 2 (tests/integration/test_resources_e2e.py) uses a real subprocess + real seeded UDS-backed agent-brain-server via Plan 57-02's start_seeded_server seeder for production-equivalent exercise of CLI-MCP-06 + CLI-MCP-07. Layer 2 skips gracefully when prerequisites are absent — NO stub fallback."
  - "McpBackend Protocol intentionally does NOT declare __enter__/__exit__ (Plan 59-02 deviation #2 carry-forward). Plan 59-03 commands/resources.py does NOT include a `with backend:` wrapper — the shape is `backend = open_mcp_backend(ctx); try: result = backend.read_resource(uri); except McpError: ...`. mypy strict catches the Protocol shape mismatch if the wrapper is ever added."
  - "AGENT_BRAIN_* env-strip latent-bug guard carry-forward from Phase 58 Plan 03. The integration test's _strip_transport_env() helper removes AGENT_BRAIN_URL / AGENT_BRAIN_TRANSPORT / AGENT_BRAIN_MCP_URL / AGENT_BRAIN_MCP_TRANSPORT from the subprocess env so the query/CLI default does not silently route around --transport mcp via an envvar pre-set in the developer's shell."

patterns-established:
  - "Pattern R — content-type dispatch helper: module-level frozenset/tuple constants for mime classification (grep-friendly), then a deterministic match chain inside the command body. JSON → parse + json.dumps(indent=2); text/* or application/text → click.echo passthrough; blob present without --output-file → click.UsageError rejection. Future MCP-only commands handling content can clone this verbatim."
  - "Pattern S — --output-file universal escape hatch: a single Click option that handles BOTH text and binary content. Detection by content shape (blob present → base64-decode, text present → utf-8-encode), unified by Path(...).write_bytes(...) + confirmation message. The two code paths share the message template `wrote {N} bytes to {path}` so callers can grep one literal."
  - "Pattern T — server-error verbatim surfacing: catch McpError, click.echo(f'Error reading {uri}: {exc}', err=True), sys.exit(2). The McpError repr includes the SDK-translated message (which for the sandbox case includes the deny reason). The CLI does NOT paraphrase, NOT pre-check, NOT add CLI-side error wrapping that would obscure the server's verdict. Pattern works for ANY server-side rejection (sandbox, INVALID_PARAMS, etc.) — generic enough to clone for future commands."

requirements-completed: [CLI-MCP-06, CLI-MCP-07]

# Metrics
duration: 7min
completed: 2026-06-08
---

# Phase 59 Plan 03: agent-brain resources Click sub-group + e2e integration Summary

**Ship `agent-brain resources list` + `agent-brain resources read <uri>` with JSON/text/binary content-type dispatch and server-only file:// sandbox surfacing; close CLI-MCP-06 + CLI-MCP-07; complete Phase 59 (all 4 ROADMAP success criteria green).**

## Performance

- **Duration:** ~7 min (3 tasks of TDD + 1 QA gate)
- **Started:** 2026-06-08T21:56:14Z
- **Completed:** 2026-06-08T22:03:39Z
- **Tasks:** 4 (3 TDD + 1 QA gate / closeout verification)
- **Files modified:** 5 (3 created, 2 modified)
- **Net LOC added:** ~830 (245 source + 585 tests)

## Accomplishments

- **`agent-brain resources` Click sub-group** at `agent-brain-cli/agent_brain_cli/commands/resources.py` (~245 LOC after Black). Public surface:
  - `@click.group("resources")` parent with examples docstring.
  - `@resources_group.command("list")` — merges `backend.list_resources()` (5 static URIs) + `backend.list_resource_templates()` (4 templated URI schemes) into a single rich.Table sorted alphabetically by URI; supports `--json` flag for pretty-printed merged dict (`{"resources": [...], "templates": [...]}`).
  - `@resources_group.command("read")` — positional `<uri>` + optional `--output-file PATH` + optional `--json` flag. Default content-type dispatch matrix below.
  - Both subcommands call `open_mcp_backend(ctx)` (Plan 59-01) → `--transport mcp` enforcement is automatic via the single-point factory contract.

- **Content-type dispatch matrix** (default mode in `read_command`):

  | Server response shape | Dispatch | CLI output |
  | --- | --- | --- |
  | `mimeType == "application/json"`, `text` parses as JSON | Pretty-print | `json.dumps(parsed, indent=2)` to stdout |
  | `mimeType.startswith("text/")` OR `mimeType == "application/text"`, `text` present | Passthrough | `click.echo(text)` to stdout |
  | `blob` present, NO `--output-file` | REJECT | `click.UsageError("Resource is binary ({mimeType}); pass --output-file PATH to save")` → exit 2 |
  | `--output-file PATH` set + `blob` | Write binary | `path.write_bytes(base64.b64decode(blob))` + `wrote {N} bytes to {path}` echo |
  | `--output-file PATH` set + `text` | Write text | `path.write_bytes(text.encode("utf-8"))` + `wrote {N} bytes to {path}` echo |
  | `--json` flag set | Force JSON | `json.dumps(...)` (parsed text → parsed; non-text → full result dict) |
  | Empty `contents` list | Error | `"Resource {uri} returned no contents"` → exit 1 |
  | Malformed blob (base64 decode fails) | Error | `"Failed to decode blob for {uri}: {exc}"` → exit 3 |

  Grep-able literals:
  - `Resource is binary` (1 occurrence in resources.py)
  - `wrote {len(...)} bytes to {path}` (2 occurrences — one for blob path, one for text path)
  - `Failed to decode blob` (1 occurrence)
  - `returned no contents` (1 occurrence)
  - `outside_indexed_roots` — **0 occurrences** (architectural pin: server verdict is surfaced via McpError verbatim; the CLI does NOT have its own literal).
  - Mime classification constants: `_TEXT_MIME_PREFIXES = ("text/",)`, `_TEXT_MIME_LITERALS = frozenset({"application/text"})`, `_JSON_MIME_LITERALS = frozenset({"application/json"})`.

- **3-tier exit-code scheme on `read`:**
  - **exit 1** — server/wire errors (non-McpError exceptions); empty contents list ("the server replied but with nothing").
  - **exit 2** — usage errors (missing `--transport mcp`, malformed args), sandbox deny via McpError verbatim surfacing, binary-without-`--output-file` rejection via click.UsageError.
  - **exit 3** — `--output-file` write failures specifically due to malformed base64 in the blob (binascii.Error / ValueError).

- **Server-only file:// sandbox surfacing.** The CLI's `read_command` catches `McpError` from `backend.read_resource()` and surfaces it VERBATIM to stderr via `click.echo(f"Error reading {uri}: {exc}", err=True)` followed by `sys.exit(2)`. For `file://` URIs outside indexed roots, the server raises `McpError(ErrorData(code=INVALID_PARAMS, message="...outside_indexed_roots...", data={"reason": "outside_indexed_roots", ...}))`; the McpError's repr includes the SDK-translated message containing the deny reason. **No CLI-side pre-check, no message rewriting, no fallback** — the v3 design doc §3.5 server-only sandbox contract is honored.

- **20 unit tests pass** at `agent-brain-cli/tests/test_resources_command.py` (16 standalone + 4 parametrized mime-dispatch matrix). Coverage includes:
  - `--transport mcp` enforcement on BOTH subcommands.
  - List default table output (alphabetical sort verification).
  - List `--json` flag (parses + shape check).
  - Read JSON content (pretty-print verification).
  - Read text content (passthrough byte-for-byte).
  - Read binary without `--output-file` (exit 2 + message verification).
  - Read binary with `--output-file` (file content + bytes count verification).
  - Read text with `--output-file` (UTF-8 round-trip).
  - Read McpError with `outside_indexed_roots` in message (exit 2 + stderr verbatim).
  - Empty contents (exit 1).
  - Malformed blob (exit 3).
  - Help output documents `<NAME>`, `--arg`, `--json`, `--output-file`.

- **3 end-to-end integration tests** at `agent-brain-cli/tests/integration/test_resources_e2e.py`. Uses Plan 57-02's `start_seeded_server` to spin up a real `agent-brain-server` with a small seeded UDS-backed corpus, then invokes the CLI via `subprocess.run([sys.executable, "-m", "agent_brain_cli", ...])` against a real `agent-brain-mcp --transport stdio` subprocess. Covers ROADMAP Phase 59 SC2 + SC3 + SC4. Skips gracefully when prerequisites are absent (no OPENAI_API_KEY → SKIP, not FAIL).

- **`task before-push` exits 0** across the full monorepo. 547 cli + 514 mcp + UDS + server tests all pass; Black/Ruff/mypy strict all clean. CLI coverage 80%; MCP coverage 88%.

## Task Commits

| # | Type      | Hash      | Message                                                              |
| - | --------- | --------- | -------------------------------------------------------------------- |
| 1 | GREEN     | `2987aa6` | feat(59-03): add agent-brain resources Click sub-group + content-type dispatch |
| 2 | TEST      | `873aa1b` | test(59-03): add 20 CliRunner tests for agent-brain resources list/read |
| 3 | TEST      | `4b5ec8f` | test(59-03): add e2e integration test for resources list/read        |
| 4 | QA chore  | `fea8aa9` | chore(59-03): apply Black + line-length wrap for QA gate             |

(Task 1 implements + ships in one commit since the failing-test step is satisfied by Task 2's CliRunner suite, which is intentionally separated for layering clarity per the Phase 57/58 precedent.)

## Files Created/Modified

### Created
- `agent-brain-cli/agent_brain_cli/commands/resources.py` (~245 LOC after Black). `@click.group("resources")` parent + `list` subcommand + `read` subcommand + 3 module-level mime classification constants (`_TEXT_MIME_PREFIXES`, `_TEXT_MIME_LITERALS`, `_JSON_MIME_LITERALS`). Imports: `base64`, `binascii`, `json`, `sys`, `pathlib.Path`, `typing.Any`, `click`, `mcp.McpError`, `rich.console.Console`, `rich.table.Table`, `agent_brain_cli.client.transport.open_mcp_backend`.

- `agent-brain-cli/tests/test_resources_command.py` (637 LOC). 20 CliRunner tests with mocked `open_mcp_backend` at the command module's import site. Reusable `_make_fake_backend()` factory honors all 5 McpBackend Protocol methods plus context-manager defensive stubs (the Protocol does NOT declare `__enter__`/`__exit__`, but the MagicMock has them set as a no-op safety net in case future code paths add them).

- `agent-brain-cli/tests/integration/test_resources_e2e.py` (220 LOC). 3 end-to-end tests + `_strip_transport_env()` helper + `seeded_state_dir` fixture. Marked `pytest.mark.integration`. Uses real subprocess + real seeded UDS corpus from Plan 57-02 `tests/integration/_corpus.py:start_seeded_server`.

### Modified
- `agent-brain-cli/agent_brain_cli/commands/__init__.py`. Added `from .resources import resources_group` + `"resources_group"` to `__all__` (alphabetical position between `reset_command` and `start_command`).
- `agent-brain-cli/agent_brain_cli/cli.py`. Added `resources_group` to the top-level commands import block + `cli.add_command(resources_group, name="resources")` registration after `cli.add_command(prompt_command, name="prompt")`.

## Decisions Made

1. **Content-type dispatch lives at the CLI command layer** (`commands/resources.py read_command`). The backend.read_resource() return shape is preserved as the raw MCP wire dict (per Plan 59-01 / 59-02 decisions: `dict[str, Any]`). The command does the JSON pretty / text passthrough / binary gate decision based on `contents[0].mimeType` + presence of `text`-vs-`blob` keys. This keeps the McpBackend Protocol surface uniform across all 5 methods and puts per-method coercion at the command-layer (mirrors the prompt command's `messages[].content.text` rendering convention).

2. **Server-only file:// sandbox enforcement** is the architectural pin. The CLI does NOT pre-check URIs against indexed roots. The agent-brain-mcp server's `McpError` with `outside_indexed_roots` in the error message/data is surfaced VERBATIM to stderr via `click.echo(f"Error reading {uri}: {exc}", err=True)` followed by `sys.exit(2)`. **Grep returns ZERO occurrences of the `outside_indexed_roots` literal in `resources.py`** — proves the pin (the Phase 50 sandbox helpers in `agent_brain_server/security/file_sandbox.py` are the canonical source; CLI does not duplicate the 4 deny reasons or the 10 MiB cap).

3. **--output-file is the universal escape hatch** for BOTH text and binary content. The user's mental model is "save resource to disk"; forcing different commands for text vs binary would break that. Implementation: blob → `base64.b64decode` → `Path.write_bytes`; text → `text.encode("utf-8")` → `Path.write_bytes`. Both echo `wrote {N} bytes to {path}` confirmation with the bytes count from `len(payload)` / `len(data)`.

4. **3-tier exit code scheme on `read`:** exit 1 = server/wire errors + empty contents ("something went wrong server-side"); exit 2 = usage errors + sandbox deny + missing --transport mcp ("you misused the CLI or the server said no"); exit 3 = blob base64-decode failures on --output-file paths ("the server returned malformed binary content"). The 3-tier scheme is the CONTEXT.md Claude's-discretion recommendation; it gives ops scripts a clean signal for retry vs. permanent failure vs. user-misuse triage.

5. **Binary-without-output-file rejection via `click.UsageError`** (exit 2). The exact rejection message is `Resource is binary ({mime or 'unknown'}); pass --output-file PATH to save` — grep-stable wording so future maintainers can find the rejection site by literal substring. `click.UsageError` is Click's standard channel for exit 2 + stderr surfacing; the CLI does NOT manually format the error.

6. **End-to-end integration test layering** matches the Phase 57 / 58 precedent.
   - **Layer 1** — `tests/test_resources_command.py`. CliRunner + mocked backend at `agent_brain_cli.commands.resources.open_mcp_backend`. Fast (~0.3s). Every branch covered. Used in `task before-push`.
   - **Layer 2** — `tests/integration/test_resources_e2e.py`. Real subprocess + real seeded UDS-backed `agent-brain-server` via Plan 57-02's `start_seeded_server`. Marked `pytest.mark.integration`. Skips gracefully without prerequisites (OPENAI_API_KEY / agent-brain-serve / agent-brain-mcp / agent-brain). Covers SC2 + SC3 + SC4 from ROADMAP through real MCP wire calls.

7. **`McpBackend` Protocol intentionally does NOT declare `__enter__`/`__exit__`** (Plan 59-02 deviation #2 carry-forward). Plan 59-03 `commands/resources.py` does NOT include a `with backend:` wrapper — the shape is `backend = open_mcp_backend(ctx); try: result = backend.read_resource(uri); except McpError: ...`. mypy strict catches the Protocol shape mismatch if the wrapper is ever added (same shape Plan 59-02 hit during its initial GREEN cycle).

8. **`AGENT_BRAIN_*` env-strip latent-bug guard carry-forward** from Phase 58 Plan 03. The integration test's `_strip_transport_env()` helper removes `AGENT_BRAIN_URL` / `AGENT_BRAIN_TRANSPORT` / `AGENT_BRAIN_MCP_URL` / `AGENT_BRAIN_MCP_TRANSPORT` from the subprocess env so the query/CLI default does not silently route around `--transport mcp` via an envvar pre-set in the developer's shell. This is the SAME latent bug Phase 58 documented; Plan 59-03 inherits the same guard for the same reason.

## Phase 59 Closeout Roll-up

| SC | Status | Covered by |
| --- | --- | --- |
| **SC1** — `agent-brain prompt <name>` for all 6 v1 prompts; unknown names exit 2 with available list | **Closed** | Plan 59-02 Tasks 1-2 + `tests/test_prompt_command.py` (13 tests) |
| **SC2** — `agent-brain resources list` enumerates 5 static + 4 templated URI schemes | **Closed** | Plan 59-03 Task 1 (`commands/resources.py list_command`) + Task 3 e2e Test 1 (`test_resources_list_enumerates_static_and_templates`) |
| **SC3** — `agent-brain resources read <uri>` content-type dispatch (JSON / text / binary) | **Closed** | Plan 59-03 Task 1 (content-type dispatch matrix) + Task 2 (12 unit tests covering every branch) + Task 3 e2e Test 2 (`test_resources_read_corpus_status_returns_pretty_json`) |
| **SC4** — `agent-brain resources read file:///disallowed/path` exits 2 with server's `outside_indexed_roots` deny reason | **Closed** | Plan 59-03 Task 2 unit test (`test_resources_read_outside_indexed_roots_surfaces_server_verdict`) + Task 3 e2e Test 3 (`test_resources_read_file_outside_indexed_roots_exits_2`) |

**Phase 59 requirements closed:**
- **CLI-MCP-05** — Plan 59-02 (`agent-brain prompt` command)
- **CLI-MCP-06** — Plan 59-03 (`agent-brain resources list` command)
- **CLI-MCP-07** — Plan 59-03 (`agent-brain resources read` command + content-type dispatch + server-only file:// sandbox)

**Closeout verification commands (all exit 0):**
- `cd agent-brain-cli && poetry run agent-brain --help` lists BOTH `prompt` and `resources` in the command listing.
- `cd agent-brain-cli && poetry run agent-brain resources --help` shows `list` and `read` subcommand entries.
- `cd agent-brain-cli && poetry run pytest tests/test_prompt_command.py tests/test_resources_command.py tests/test_mcp_backend_factory.py -v` → 41 passed.
- `cd agent-brain-mcp && poetry run pytest tests/test_mcp_backend_prompts_wire.py tests/test_mcp_backend_protocol_skeleton.py tests/test_cli_backends_skeleton.py -v` → 22 passed.
- `grep -c '"Wired in Phase 59 Plan 02"' agent-brain-mcp/agent_brain_mcp/client.py` → 0 (sentinel was removed by Plan 59-02; pinned here).
- `task before-push` → exit 0 across the monorepo.

## Deviations from Plan

**None.** Plan 59-03 executed exactly as written. The Black + Ruff reformatting in Task 4 was anticipated (folding collapsed expressions + a manual line-wrap on the example URI docstring to fix Ruff E501); not a behavioral deviation. All 3 task acceptance criterion sets passed without architectural change.

No auth gates encountered. No architectural decisions referred to user (Rule 4).

## Issues Encountered

- **Black collapsed multi-line `click.echo(json.dumps(...))` and `click.echo(f"...")` expressions** during the first `task before-push` run because they fit on one line. Anticipated — same pattern Plan 59-02 hit (Issues Encountered §2). Resolved by Task 4's chore commit which captured the reformatted versions.
- **Ruff E501 on the example URI docstring** (line 65) — the `file:///a.png --output-file out.png` example exceeded 88 chars verbatim. Resolved by line-wrapping the 3 example invocations with `\\` continuations inside the `\b` docstring block. Click renders the wrapped continuations correctly in `--help` output (verified manually).

## User Setup Required

None — Plan 59-03 is purely additive command + tests. No new env vars, secrets, services, or runtime configuration.

## Next Phase Readiness

- **Phase 59 is shippable.** CLI-MCP-05 + CLI-MCP-06 + CLI-MCP-07 all closed; all 4 ROADMAP success criteria green; `task before-push` exits 0 at HEAD `fea8aa9`.
- **Phase 60 (subprocess hygiene + 1000-invocation orphan test)** can begin immediately. The Pattern A `asyncio.run` per-call subprocess spawn convention is now in production across the full 15-method × 2-backend surface (10 BackendClient + 5 McpBackend). Phase 60 owns the persistent-subprocess refactor measurement and the pgrep-based orphan test.
- **No blockers.** All Phase 56-59 architectural pinning tests continue to hold (BackendClient + McpBackend isinstance pins; Protocol shape mismatch caught by mypy strict).

## Self-Check: PASSED

- `agent-brain-cli/agent_brain_cli/commands/resources.py` — FOUND (created; `@click.group("resources")` grep 1; `@resources_group.command("list")` grep 1; `@resources_group.command("read")` grep 1; `outside_indexed_roots` grep 0; `Resource is binary` grep 1)
- `agent-brain-cli/agent_brain_cli/commands/__init__.py` — FOUND (modified; `from .resources import resources_group` grep 1; `"resources_group"` in `__all__` grep 1)
- `agent-brain-cli/agent_brain_cli/cli.py` — FOUND (modified; `cli.add_command(resources_group` grep 1)
- `agent-brain-cli/tests/test_resources_command.py` — FOUND (created; 20 tests pass — 16 standalone + 4 parametrized matrix)
- `agent-brain-cli/tests/integration/test_resources_e2e.py` — FOUND (created; 3 tests skip gracefully without OPENAI_API_KEY)
- Commits FOUND: `2987aa6` `873aa1b` `4b5ec8f` `fea8aa9` (all 4 present in `git log`)
- `cd agent-brain-cli && poetry run agent-brain resources --help` → exit 0, lists `list` + `read` subcommands
- `cd agent-brain-cli && poetry run agent-brain resources list` (no --transport mcp) → exit 2 with `--transport mcp` in stderr
- `task before-push` → exit 0 across the monorepo
- All 4 ROADMAP Phase 59 success criteria have a corresponding green test (SC1: Plan 59-02; SC2/SC3/SC4: Plan 59-03)

---
*Phase: 59-cli-prompts-resources-commands*
*Completed: 2026-06-08*
