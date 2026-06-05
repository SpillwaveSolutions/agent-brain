# Phase 53 Plan: Streamable HTTP transport

**Goal:** `agent-brain-mcp` supports Streamable HTTP transport alongside stdio. Loopback-only bind, explicit `--transport` selection, no silent fallback. Auth is reserved for v4.
**Requirements:** HTTP-01, HTTP-02, HTTP-03
**Plan count:** 3
**Phase depends on:** Phase 50 (v2 design doc must mention HTTP transport in "Architecture deltas vs v1"); independent of Phase 52 (can execute in parallel).
**Prerequisite for:** MCP v3 (#187) framework adapter matrix.

## Plans

| #  | Title                                             | Requirements    | Depends on      | Parallel-safe with     | Est. LOC |
|----|---------------------------------------------------|-----------------|-----------------|------------------------|----------|
| 01 | CLI transport flags + dispatch refactor           | HTTP-01, HTTP-03 | none — first     | none (touches CLI/server) | ~110 prod + ~120 test |
| 02 | HTTP listener with loopback enforcement + /healthz | HTTP-01, HTTP-02 | Plan 01         | none (extends Plan 01's stub) | ~150 prod + ~160 test |
| 03 | SDK round-trip smoke + Taskfile + docs            | HTTP-01, HTTP-02, HTTP-03 | Plan 02 | none (validates Plans 01-02) | ~30 prod + ~200 test + ~80 docs |

**Total estimate:** ~290 LOC production code + ~480 LOC test code + ~80 LOC docs/Taskfile = ~850 LOC.

## Execution Order

- **Wave 1 (sequential):** Plan 01 → Plan 02 → Plan 03
- All three plans are sequential because each consumes the previous plan's surface (Plan 02 fills the stub Plan 01 leaves; Plan 03 drives both Plan 01's flags and Plan 02's listener via the SDK HTTP client).
- No parallelism within Phase 53. Phase 53 itself runs in parallel with Phase 52 (subscriptions).

## Coverage Check

Every requirement maps to at least one plan:

- **HTTP-01** (`--transport http` starts MCP server reachable by official SDK HTTP client; stdio mode unchanged): Plans 01 (flag wiring + dispatch), 02 (actual listener), 03 (SDK round-trip proof)
- **HTTP-02** (loopback-only bind; no auth in v2): Plans 02 (host whitelist + SDK auto DNS-rebinding protection), 03 (loopback assertion test)
- **HTTP-03** (explicit transport selection; no silent fallback): Plans 01 (`click.Choice` rejection, dispatch contract), 02 (port-in-use raises ClickException, no fallback), 03 (negative-path tests for bogus values and conflicts)

## Cross-Phase Dependencies

- **Phase 50 → Phase 53:** Phase 50's VAL-05 design doc MUST land before Plan 01 starts coding. The doc has a Phase-53-specific subsection ("Architecture deltas vs v1 → HTTP transport") and the two-axis (`backend transport` vs `listen transport`) diagram referenced by Plan 01's design rationale and Plan 03's docs.
- **Phase 53 → Phase 54:** Phase 54's 9 new tools must reach over HTTP. Phase 53 ships before Phase 54 so Phase 54's tools land on both transports simultaneously (no dependency inversion).
- **Phase 53 → Phase 55:** Phase 55 (VAL-03) folds Plan 03's HTTP smoke into the parameterized SDK contract sweep. Plan 03 keeps its test names and surface explicit (no internal-only helpers) so Phase 55 can import / parameterize without refactor.
- **Phase 53 ↮ Phase 52:** Phase 53 must NOT assume subscription support exists. Plan 03's smoke asserts only the v1-equivalent surface over HTTP (7 tools / 5 resources / 6 prompts). Lets Phase 52 land in either order.

## Risk Register

1. **`mcp = "^1.12.0"` may not actually ship `StreamableHTTPSessionManager` at the resolved version.** Mitigation: Plan 01's first task verifies `poetry show mcp` in `agent-brain-mcp/.venv` resolves to >= 1.12.0 with `StreamableHTTPSessionManager` importable. If absent, file a follow-up ADR before continuing.
2. **uvicorn is not currently a direct dep of `agent-brain-mcp`** — it comes in transitively via the MCP SDK. Mitigation: Plan 02 confirms `python -c "import uvicorn"` works in the MCP venv; if not, add `uvicorn = "^0.32"` as a direct dep with a one-line ADR.
3. **DNS-rebinding default may change between MCP SDK minor versions.** Mitigation: Plan 02 asserts via test that the loopback host yields the expected auto-enabled `TransportSecuritySettings` (defensive pin against silent SDK regression).
4. **In-process uvicorn shutdown ordering** — the `httpx.Client` for the backend must close after uvicorn drains. Mitigation: Plan 02 nests the uvicorn run inside the `try/finally` that owns the httpx client (mirrors stdio path's existing structure).
5. **Port-in-use must not silently rebind.** Mitigation: Plan 02 catches `OSError(EADDRINUSE)` at `uvicorn.Server.serve()` call site and raises `click.ClickException` with exit code 2; Plan 03 has a regression test that occupies the port via a sibling socket then drives the CLI.
6. **#179 (Bearer-token API auth on FastAPI) lands mid-flight.** Concern: developer might assume MCP HTTP also needs Bearer auth. Mitigation: Plan 03's USER_GUIDE.md update draws the two-axis diagram (backend axis vs listen axis); the two are orthogonal and the MCP HTTP listener stays unauthenticated in v2 per HTTP-02 / OAUTH-01 (v4).
7. **Click flag ordering with default subcommand.** Mitigation: Plan 01 keeps `--backend`/`--backend-url`/`--state-dir` untouched and adds `--transport`/`--host`/`--port` as additional options on the same `main` Click command — no Click group restructure.

## Plan Coverage Notes

- Plan 01 leaves a stub `run_http(server, host, port)` that raises `NotImplementedError`. This keeps the CLI flag wiring testable independently from the listener implementation and prevents Plan 01 from being non-atomic (a half-implemented HTTP server in main).
- Plan 02 fills the stub. After Plan 02 lands, `--transport http` starts a working server.
- Plan 03 wraps with the SDK round-trip proof and Taskfile / docs.

---
*Phase plan generated: 2026-06-02*
