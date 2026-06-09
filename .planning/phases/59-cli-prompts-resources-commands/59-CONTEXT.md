# Phase 59: CLI prompts + resources commands - Context

**Gathered:** 2026-06-08 (auto mode)
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers human-friendly CLI surfaces for the MCP **prompts** and **resources** capabilities:

1. **`agent-brain prompt <name> [--arg key=value]...`** — Calls MCP `prompts/get` and prints the expanded prompt text. All 6 v1 prompts must be invokable: `audit_indexed_folders`, `compare_search_modes`, `explain_architecture`, `find_callers`, `find_implementation`, `onboard_to_codebase`. Unknown names exit non-zero with the available list in the error.
2. **`agent-brain resources list`** — Enumerates all 5 static URIs + 4 templated URI schemes (`chunk://`, `graph-entity://`, `job://`, `file://`) via `resources/list` + `resources/templates/list`, printed as a table with URI and mime type.
3. **`agent-brain resources read <uri>`** — Calls MCP `resources/read` and prints content with correct content-type handling: JSON pretty-printed, text passed through, binary blobs gated behind `--output-file` (no raw bytes to stdout).
4. **`McpBackend` Protocol** — A NEW companion Protocol in `agent-brain-cli/agent_brain_cli/client/protocol.py` (alongside the existing `BackendClient` Protocol) that exposes the 5 MCP-only methods needed by this phase. `McpStdioBackend` and `McpHttpBackend` satisfy it structurally; `DocServeClient` deliberately does NOT (the UDS/HTTP transports don't speak MCP prompts/resources — that's an architectural fact, not an omission).
5. **`agent-brain prompt` / `agent-brain resources *` require `--transport mcp`** explicitly. No silent fallback; without the flag, exit 2 with a UsageError that includes a concrete example invocation. Mirrors v10.2 HTTP-03 + Phase 57 contract.

Out of phase scope (deferred to later phases or out of milestone):
- Adding new MCP prompts or resources → out of v10.3 (the 6 prompts + 5 static + 4 templated URIs are the v2 surface; v10.3 adds CLI access, not new server capabilities)
- CLI-layer file:// sandbox pre-check → out (let the MCP server's `outside_indexed_roots` error be the authoritative source)
- `agent-brain resources subscribe` → out of v10.3 (subscriptions are an MCP-spec concept but CLI subscription UX is its own design problem; held for v10.4+)
- `agent-brain prompt --inspect` (show argument schema) → out (let users `cat` the prompt source files or read MCP server docs)
- Tab completion for prompt names / URIs → out (nice-to-have, not DoD)
- Streaming output for large resource reads → out (resources/read returns full content; if size becomes a problem, that's a server-side concern)

</domain>

<decisions>
## Implementation Decisions

### Protocol architecture: new `McpBackend` Protocol (NOT extending BackendClient)
- **NEW `McpBackend` Protocol** in `agent-brain-cli/agent_brain_cli/client/protocol.py`, alongside the existing `BackendClient` Protocol. `@runtime_checkable`. Methods (5):
  - `get_prompt(name: str, arguments: dict[str, str] | None = None) -> dict` — calls MCP `prompts/get`, returns the result dict (messages + metadata).
  - `list_prompts() -> list[dict]` — calls MCP `prompts/list`, returns the list of prompt descriptors.
  - `list_resources() -> list[dict]` — calls MCP `resources/list`, returns static URI descriptors.
  - `list_resource_templates() -> list[dict]` — calls MCP `resources/templates/list`, returns templated URI descriptors.
  - `read_resource(uri: str) -> dict` — calls MCP `resources/read`, returns the result dict (contents list with mimeType + text or blob).
- **DocServeClient does NOT satisfy McpBackend.** This is the intentional architectural boundary — UDS/HTTP transports don't speak MCP prompts/resources, period. Adding 5 NotImplementedError-stubs to DocServeClient would mirror reset()-inverse but pollute the dominant transport with always-failing methods. The clean alternative is two Protocols: one for the "tools surface" (BackendClient), one for the "prompts+resources surface" (McpBackend).
- **`McpStdioBackend` and `McpHttpBackend` extend with 5 new methods** in `agent-brain-mcp/agent_brain_mcp/client.py`, mirroring the Pattern A `asyncio.run` sync facade established in Plan 57-02. Wire calls: `stdio_client` / `streamablehttp_client` → `ClientSession.get_prompt(...)` / `list_prompts()` / `list_resources()` / `list_resource_templates()` / `read_resource(...)`.
- **Pinning test:** `isinstance(McpStdioBackend(...), McpBackend) == True` AND `isinstance(McpHttpBackend(...), McpBackend) == True` AND `isinstance(DocServeClient(...), McpBackend) == False`. The negative case is load-bearing — it pins the architectural boundary.

### Click command structure
- **`agent-brain prompt <name>`** — flat top-level command (NOT a sub-group). Single subcommand-style verb because there's only one operation: expand a named prompt.
- **`agent-brain resources` Click sub-group** with `list` and `read` subcommands. Mirrors the Phase 58 `agent-brain mcp start/stop` pattern.
- **All three commands are MCP-only:** they require `--transport mcp` explicitly. They internally dispatch via a NEW factory `open_mcp_backend(ctx) -> McpBackend` (alongside `open_backend(ctx) -> BackendClient` from Phase 57). The new factory raises `click.UsageError` if `ctx.obj["transport_hint"] != "mcp"`.
- **New files:**
  - `agent-brain-cli/agent_brain_cli/commands/prompt.py` — `@cli.command("prompt")` with `<name>` positional + `--arg KEY=VALUE` (multi) + `--json` flag.
  - `agent-brain-cli/agent_brain_cli/commands/resources.py` — `@cli.group("resources")` with `list` + `read` subcommands.
- **`agent-brain-cli/agent_brain_cli/client/transport.py`** gets a new function `open_mcp_backend(ctx, *, timeout: float = 30.0) -> McpBackend` next to `open_backend`.

### `--transport mcp` requirement (no silent fallback)
- **Force explicit selection.** If `agent-brain prompt foo` runs WITHOUT `--transport mcp`, raise `click.UsageError("agent-brain prompt requires --transport mcp; example: agent-brain --transport mcp --mcp-transport stdio prompt {name}")` with exit code 2.
- **Carries the Phase 57 §3.5 contract:** every MCP-only command surfaces the missing-transport failure loudly; no auto-fallback to UDS/HTTP. The same exit code 2 + verbatim messaging.
- **`open_mcp_backend(ctx)` is the single enforcement point** — every MCP-only command calls it instead of `open_backend(ctx)`, so the transport check lives in one place.

### `agent-brain prompt <name>` UX
- **Positional arg:** `<name>` — required, must be one of the 6 v1 prompts (or whatever `prompts/list` returns at call time; we don't hard-code the 6 names CLI-side).
- **Repeatable `--arg KEY=VALUE`** flag for prompt arguments (Click `multiple=True`). Example: `agent-brain --transport mcp --mcp-transport stdio prompt find_callers --arg symbol=parse_query --arg file=query_service.py`.
- **Argument parsing:** `--arg KEY=VALUE` strings are parsed CLI-side into `{KEY: VALUE}` dict; passed to MCP `prompts/get` verbatim. Whether the prompt accepts/requires those args is the MCP server's call — we do not validate the schema CLI-side.
- **Output format:**
  - Default: render the expanded prompt text to stdout (concatenated `messages[].content.text` from the `prompts/get` response, joined with `\n---\n` between messages if there are multiple).
  - With `--json` flag: print the raw `prompts/get` response as JSON, pretty-printed with 2-space indent.
  - Both modes go to stdout — easy to pipe.
- **Unknown prompt name handling:** the CLI does NOT pre-validate the name against `prompts/list`. It passes the name to the server. When the server raises an MCP error (-32602 or similar for unknown prompt), the CLI catches it, queries `prompts/list` to enumerate available names, and exits 2 with: `"Unknown prompt '{name}'; available: {comma-separated list from prompts/list}"`.

### `agent-brain resources list` UX
- **Calls both `resources/list` AND `resources/templates/list`** then merges output in a single table.
- **Default output:** table with columns `URI`, `Mime Type`, `Type` (static vs templated). Sorted alphabetically by URI for stable output.
- **With `--json` flag:** print the merged result as JSON, pretty-printed.
- **No filtering flags in v3** — Phase 59 ships the simple full enumeration; filtering can come later if needed.

### `agent-brain resources read <uri>` UX
- **Positional arg:** `<uri>` — required, any MCP URI scheme.
- **Content-type handling:**
  - **JSON (mimeType matches `application/json` or starts with `application/` and content parses as JSON):** pretty-print to stdout with 2-space indent.
  - **Text (mimeType starts with `text/` OR matches `application/text` OR has `text` content from `resources/read`):** pass content through to stdout as-is.
  - **Binary (anything else with `blob` content from `resources/read`):** REJECT writing to stdout. Exit 2 with: `"Resource is binary ({mimeType}); pass --output-file PATH to save"`.
  - **With `--output-file PATH` flag:** ALWAYS write content (text or binary) to the file, no stdout output beyond a one-line confirmation `"wrote {bytes} bytes to {path}"`. This is the universal escape hatch — works for text AND binary.
- **No raw bytes to stdout, ever.** This protects terminal state from binary blob injection.

### `file://` sandbox enforcement
- **Server-only.** The CLI does NOT pre-check the URI against an indexed-roots list. The MCP server's `outside_indexed_roots` error (from v10.2 Phase 51 Plan 03 via the Phase 50 sandbox helpers) is the authoritative source.
- **CLI surfaces the server's error verbatim:** `agent-brain resources read file:///disallowed/path` → CLI sees server's `outside_indexed_roots` reason → exit 2 with that exact reason string surfaced via `click.echo(err=True)`.
- **Why server-only:** CLI-layer pre-check would duplicate the v10.2 Phase 50 sandbox logic (canonical path resolution, 10 MiB cap, 4 deny reasons) and inevitably drift. Phase 50 already validated the sandbox is correct; CLI just reports the verdict.

### Output encoding
- **All stdout text output uses UTF-8.** Click's default encoding handling is acceptable. No manual encoding tricks.
- **`--output-file` writes raw bytes** (open with `"wb"` mode) for binary safety. For text-only paths, the same `"wb"` mode receives the UTF-8-encoded bytes — uniform.

### Claude's Discretion
- **Exact column widths for `agent-brain resources list` table** — planner picks; use rich.Table or plain `tabulate` consistent with existing CLI commands.
- **Whether `--json` flag mirrors across all three commands** — recommend yes (consistent UX) but planner may decide.
- **Specific exit codes for non-UsageError cases** (server-side errors, network failures): planner aligns with existing CLI patterns. Recommend: exit 1 for server errors, exit 2 for usage errors, exit 3 for I/O errors on `--output-file`.
- **Pretty-printer choice** — `json.dumps(..., indent=2, sort_keys=False)` is fine; planner may use rich.print_json if cleaner.
- **Whether `prompt <name> --arg KEY=VALUE` validates KEY=VALUE shape before sending** — recommend yes (split on first `=`, error if no `=`). Planner picks the error message wording.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### v3 design doc — the architectural anchor
- `docs/plans/2026-06-05-mcp-v3-cli-via-mcp.md` §3.5 (no-silent-fallback contract — Phase 59 carries it for the MCP-only commands).
- `docs/plans/2026-06-05-mcp-v3-cli-via-mcp.md` §4.4 (Phase 59 scope: prompts + resources commands).

### MCP v2 prompts + resources surfaces (the server side this phase wraps)
- `agent-brain-mcp/agent_brain_mcp/prompts/__init__.py` — Prompt registry mapping name → handler. The 6 v1 prompts are listed via `prompts/list` (no hard-coded CLI-side names).
- `agent-brain-mcp/agent_brain_mcp/prompts/{audit_indexed_folders,compare_search_modes,explain_architecture,find_callers,find_implementation,onboard_to_codebase}.py` — individual prompt implementations (read to understand argument shapes if planner needs context).
- `agent-brain-mcp/agent_brain_mcp/resources/__init__.py` — Static + parameterized URI dispatcher.
- `agent-brain-mcp/agent_brain_mcp/resources/corpus.py` — 5 static URIs (`corpus://status`, `corpus://folders`, etc.).
- `agent-brain-mcp/agent_brain_mcp/resources/parameterized.py` — 4 templated URI schemes (`chunk://`, `graph-entity://`, `job://`, `file://`).
- `agent-brain-mcp/agent_brain_mcp/server.py` — Where `prompts/get`, `resources/list`, `resources/read`, `resources/templates/list` are registered with the MCP SDK; understanding the error shapes the server emits is important for the CLI's error surfacing.

### Phase 57 carry-forward (the Protocol + dispatcher pattern Phase 59 mirrors)
- `agent-brain-cli/agent_brain_cli/client/protocol.py` — Existing `BackendClient` Protocol (the model for the new `McpBackend` Protocol next to it).
- `agent-brain-cli/agent_brain_cli/client/transport.py` — `open_backend(ctx)` dispatcher (the model for the new `open_mcp_backend(ctx)`).
- `agent-brain-mcp/agent_brain_mcp/client.py` — `McpStdioBackend` + `McpHttpBackend` (where 5 new MCP-only methods get added, mirroring the Pattern A `asyncio.run` sync facade established in Plan 57-02).

### v10.2 Phase 50 sandbox (the `outside_indexed_roots` error CLI surfaces)
- `agent-brain-server/agent_brain_server/security/file_sandbox.py` — Hard whitelist policy with 4 deny reasons (`outside_indexed_roots`, `path_traversal`, `symlink_escape`, `over_size_limit`); 10 MiB cap. CLI does NOT duplicate this; it surfaces the server's verdict.
- `.planning/PROJECT.md` line 104 — `URI-04` validated decision: "agent_brain_server/security/file_sandbox.py — hard whitelist policy with 4 deny reasons, 10 MiB cap — v10.2 (Phase 50)".

### Phase 58 helper commands (the structural template for `commands/resources.py` sub-group)
- `agent-brain-cli/agent_brain_cli/commands/mcp.py` — `@click.group("mcp")` with `start`/`stop` subcommands. Phase 59's `commands/resources.py` mirrors this structure.

### Existing CLI patterns
- `agent-brain-cli/agent_brain_cli/commands/__init__.py` — How commands are registered with the top-level `cli` group. Phase 59 adds `cli.add_command(prompt)` + `cli.add_command(resources)`.
- `agent-brain-cli/agent_brain_cli/cli.py` — Top-level Click group + `--transport`/`--mcp-transport`/`--mcp-url` flags from Phase 57. Phase 59 commands read `ctx.obj["transport_hint"]` for the explicit-mcp-required check.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`McpStdioBackend` + `McpHttpBackend`** (`agent-brain-mcp/agent_brain_mcp/client.py`) — Both already have `asyncio.run` sync facades around the MCP SDK for `query`/`health`/`status`/etc. Phase 59 adds 5 more methods following the same pattern verbatim (just different MCP SDK calls).
- **Existing `_async_query` / `_async_*` helpers** in `client.py` — Template for `_async_get_prompt`, `_async_list_prompts`, `_async_list_resources`, `_async_list_resource_templates`, `_async_read_resource`.
- **`BackendClient` Protocol pattern** — Direct template for the new `McpBackend` Protocol. Same `@runtime_checkable` + same forward-string return-type style.
- **`open_backend(ctx)` dispatcher** — Template for `open_mcp_backend(ctx)`. The new factory is simpler (only McpStdioBackend OR McpHttpBackend dispatch, no UDS/HTTP branches).
- **`agent-brain mcp start/stop` Click sub-group** (Phase 58 `commands/mcp.py`) — Template for `commands/resources.py` Click sub-group.
- **MCP server prompts + resources registries** (`agent-brain-mcp/agent_brain_mcp/{prompts,resources}/`) — The 6 prompts + 5 static URIs + 4 templated URIs are already implemented and contract-tested via v10.2 Phase 55. Phase 59 doesn't touch them; it consumes them through the MCP SDK.

### Established Patterns
- **Pattern A `asyncio.run` sync facade per call** (Phase 57 decision) — Phase 59's 5 new methods use this verbatim. NOT a candidate for Pattern B persistent loop here (Phase 60 hygiene work owns that decision if at all).
- **No-silent-fallback** (v10.2 HTTP-03 + Phase 57 §3.5) — `agent-brain prompt` and `agent-brain resources *` raise UsageError if `--transport mcp` not set.
- **Click sub-group naming** (`@click.group("mcp")` from Phase 58) — Phase 59 uses `@click.group("resources")` identically.
- **`task before-push` is mandatory** — Every plan ends with the QA gate.

### Integration Points
- **Top-level Click group** (`agent-brain-cli/agent_brain_cli/cli.py`) — Register `prompt` command and `resources` sub-group via `cli.add_command(...)`.
- **`agent-brain-cli/agent_brain_cli/commands/__init__.py`** — Add `from .prompt import prompt` and `from .resources import resources_group`.
- **`agent-brain-cli/agent_brain_cli/client/protocol.py`** — Add new `McpBackend` Protocol class after `BackendClient`.
- **`agent-brain-cli/agent_brain_cli/client/transport.py`** — Add `open_mcp_backend(ctx, *, timeout) -> McpBackend` function next to `open_backend`.
- **`agent-brain-mcp/agent_brain_mcp/client.py`** — Add 5 methods to both `McpStdioBackend` and `McpHttpBackend` classes (10 method additions total + 10 `_async_*` helpers).

</code_context>

<specifics>
## Specific Ideas

- **The Protocol split is the load-bearing architectural decision.** Two Protocols (`BackendClient` for tools, `McpBackend` for prompts+resources) cleanly encodes the fact that UDS/HTTP transports don't and shouldn't speak MCP prompts/resources. The negative-case pinning test (`isinstance(DocServeClient(...), McpBackend) == False`) makes this explicit and lasting.
- **`--transport mcp` requirement is enforced at a single point:** `open_mcp_backend(ctx)`. Every Phase 59 command calls it. Future MCP-only commands inherit the contract for free.
- **Server-side sandbox surfacing (not duplication)** is the right call for `file://` — duplicating the Phase 50 sandbox logic CLI-side would create drift. Trust the server's verdict and surface it verbatim.
- **Plans should be sequenced:**
  - Plan 59-01 (wave 1): `McpBackend` Protocol in `protocol.py` + 5 method skeletons on both `McpStdioBackend` and `McpHttpBackend` raising `NotImplementedError("Wired in Phase 59 method-wire plans")` (skeleton-first like Phase 56 pattern) + pinning test asserting both backends satisfy McpBackend AND DocServeClient does NOT. `open_mcp_backend(ctx)` factory with `--transport mcp` enforcement. CLI-MCP-05 prereq foundation.
  - Plan 59-02 (wave 2, depends_on: ['59-01']): Wire 5 methods on both backends end-to-end via MCP SDK (`asyncio.run` Pattern A): `get_prompt`, `list_prompts`, `list_resources`, `list_resource_templates`, `read_resource`. Add `commands/prompt.py` with `<name>` positional + `--arg KEY=VALUE` multi + `--json` flag. CLI-MCP-05 closes.
  - Plan 59-03 (wave 3, depends_on: ['59-02']): `commands/resources.py` Click sub-group with `list` (merged static + templated, table or `--json`) + `read` (content-type handling: JSON pretty-print, text passthrough, binary requires `--output-file`); end-to-end integration test covering all 4 success criteria including `file://` sandbox surfacing. CLI-MCP-06 + CLI-MCP-07.
- **Test layering matches Phase 57:** Layer 1 unit tests use a fake MCP backend (httpx fake or in-process mock); Layer 2 integration tests use a real `agent-brain-mcp --transport stdio` subprocess (reuse the Phase 57 corpus seeder pattern from `tests/integration/_corpus.py`).

</specifics>

<deferred>
## Deferred Ideas

- **New MCP prompts or resources** — out of v10.3 (6 prompts + 5 static + 4 templated URIs are the v2 surface).
- **CLI-layer file:// sandbox pre-check** — out (server-only is the architectural decision; revisit if telemetry shows users hit the same wall repeatedly).
- **`agent-brain resources subscribe`** — out of v10.3 (subscription UX is a separate design problem; held for v10.4+).
- **`agent-brain prompt --inspect`** to show argument schema — out (users can read prompt source files).
- **Tab completion** for prompt names / URIs — out (nice-to-have, not DoD).
- **Streaming output for large reads** — out (resources/read returns full content; server-side concern if size becomes a problem).
- **Filtering flags for `resources list`** (e.g., `--scheme chunk`) — out for v3, easy to add later if patterns emerge.
- **A unified `McpBackend(BackendClient)` Protocol** combining both surfaces — explicitly NOT done. The split is the architectural decision.
- **`--arg JSON_OBJECT`** as an alternative to repeated `--arg KEY=VALUE` — out (multi-flag pattern is uniform with existing CLI conventions).

</deferred>

---

*Phase: 59-cli-prompts-resources-commands*
*Context gathered: 2026-06-08 (auto mode — recommended defaults selected)*
