# Phase 55: Validation, contract tests & QA gate integration — Context

**Gathered:** 2026-06-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 55 is the v10.2 MCP v2 exit gate. It does not ship new MCP features — it
verifies the surface that Phases 50–54 shipped against the official MCP Python
SDK and folds the new packages into the root quality gates so future regressions
are caught locally before push.

Specifically Phase 55 delivers:

1. A **parameterized contract test suite** that drives all 16 MCP tools
   (7 v1 + 9 v2) through the official MCP SDK client (stdio AND Streamable HTTP
   transports) and asserts each tool's `inputSchema`, `outputSchema`,
   `content` + `structuredContent` shape, and error semantics (VAL-01).
2. An **end-to-end resource subscription test** that exercises
   `resources/subscribe` → `notifications/resources/updated` → `unsubscribe`
   plus the server-side cleanup that fires on client disconnect (VAL-02,
   closes SUB-05 verification).
3. A **Streamable HTTP transport test** that runs the full
   initialize → tools/list → tools/call → resources/list → resources/read flow
   via the SDK's HTTP client against `agent-brain-mcp --transport http`
   (VAL-03).
4. Root **`task before-push` and `task pr-qa-gate` integration** for both
   `agent-brain-mcp` and `agent-brain-uds`, closing **DR-5** from the v1
   design (`docs/plans/2026-05-28-mcp-uds-transport-design.md` §14 #5).

Phase 55 is explicitly the LAST phase of v10.2 — it cannot start until Phases
50–54 are merged. Nothing in v3 (CLI-via-MCP, framework matrix) or v4 (OAuth)
falls into scope; if a v2 surface is broken at audit time, fix it in its
originating phase, do not patch it here.

</domain>

<decisions>
## Implementation Decisions

### A. Contract-test architecture (VAL-01)
- **D-01:** **Two-layer test suite.** Layer 1 = in-process parametrized
  per-tool tests using the existing `fake_httpx_client` pattern from
  `tests/test_each_tool.py` — fast, runs in `task mcp:test`, covers schema +
  shape for every tool. Layer 2 = SDK-driven contract tests that spawn the
  real `agent-brain-mcp` subprocess and exercise tools via
  `mcp.ClientSession` over both stdio and HTTP transports — slower, runs in
  `task mcp:contract` and gated to `task mcp:test:all` / `task before-push`.
  Rationale: Layer 1 gives sub-second feedback per tool; Layer 2 catches
  protocol-level regressions the in-process tests can't see (transport
  framing, capability negotiation, error code wire format).
- **D-02:** **Parametrize over `(tool_name, sample_arguments, expected_shape)`
  matrix** with 16 entries plus 1 negative-arg entry per tool. Total target:
  ~32 contract assertions per transport × 2 transports = 64 contract runs.
  Each entry asserts: tool is listed in `tools/list`; `inputSchema` validates
  the sample; `outputSchema` (when declared) validates the result;
  `content[0]` is `TextContent`; `structuredContent` is a dict matching the
  declared output shape.
- **D-03:** **MCP SDK pin** stays at `mcp = "^1.12.0"` (current v1 pin). If
  the SDK has shipped a newer minor since Phase 50, bump in Phase 55 and
  document in the v2 design doc's "Spec versions" section — do not float.
- **D-04:** **Backend is the in-memory fake** (existing `fake_httpx_client`
  conftest fixture), NOT a real `agent-brain-serve` subprocess, for the SDK
  contract tests. The full server-in-the-loop E2E test already exists at
  `tests/e2e/`; Phase 55 contract tests verify the MCP layer's protocol
  conformance, not the server's behavior. Keeps contract suite under 30s.

### B. Subscription E2E test scope (VAL-02)
- **D-05:** Test matrix covers **all three subscription URIs from Phase 52**
  in one parametrized test: `job://<id>` (1s cadence), `corpus://status`
  (30s cadence), `corpus://folders` (watcher-driven). Each scenario:
  subscribe → assert ≥1 `notifications/resources/updated` arrives within
  cadence × 2 → unsubscribe → assert no further notifications arrive within
  cadence × 2.
- **D-06:** **Disconnect cleanup** asserted by spawning a second SDK client,
  subscribing it, killing its stdio pipe (`session.__aexit__()` without
  unsubscribe), waiting one cadence, then asserting via an HTTP debug
  endpoint or server log scrape that the per-client subscription count
  dropped to 0. Use whichever observability surface Phase 52 exposed — if
  none, request a `GET /mcp/subscriptions` debug endpoint via a Phase 52
  follow-up note in the v2 design doc rather than adding it in Phase 55.
- **D-07:** **Cadence tolerance:** assert notifications arrive within
  `cadence × 1.5` on the upper bound (so 1s cadence has a 1.5s deadline).
  Below 1s cadence the test is flaky on CI runners; raise issue if a tool
  requires it.
- **D-08:** Subscription tests run **stdio only** in Phase 55. The HTTP
  transport's SSE/event-stream framing for `notifications/resources/updated`
  is verified by the HTTP test in D-09, but the cadence/cleanup correctness
  test only needs one transport — stdio is faster and deterministic.

### C. Streamable HTTP transport test (VAL-03)
- **D-09:** Test spawns `agent-brain-mcp --transport http --port <auto>`
  via subprocess, polls `/health` (or the MCP HTTP `initialize` endpoint)
  until ready with a 10s timeout, then drives one full client session via
  `mcp.client.streamable_http.streamablehttp_client(...)`. Asserts:
  initialize succeeds, `tools/list` returns 16 tools, `tools/call` on a
  smoke-test tool returns `content` + `structuredContent`, `resources/list`
  returns expected URIs, `resources/read` on `corpus://config` succeeds.
- **D-10:** **Loopback assertion:** Phase 55 test does NOT attempt to
  exercise external-bind rejection (e.g., `--host 0.0.0.0` must fail). That
  test lives in Phase 53. Phase 55 only confirms the loopback-only
  configuration works end-to-end via the SDK HTTP client.
- **D-11:** **Port allocation:** test fixture asks the OS for a free port
  (`socket.bind(("127.0.0.1", 0))` → release → reuse) rather than hardcoding
  a port range. Avoids collisions with multi-instance Agent Brain servers
  the developer may have running locally.

### D. Root QA gate integration (VAL-04, closes DR-5)
- **D-12:** **Add `task uds:before-push` and `task mcp:before-push` as
  sub-tasks of root `task before-push`** (and the same for `pr-qa-gate`).
  Specifically: insert `task: uds:before-push` and `task: mcp:before-push`
  into the existing root `before-push` recipe AFTER the existing
  format/lint/typecheck/test cycle and BEFORE the `--- All checks passed
  ---` echo. Same edit for `pr-qa-gate` (`uds:pr-qa-gate`, `mcp:pr-qa-gate`).
- **D-13:** **Layering check (`task check:layering`)** stays where it is in
  the root taskfile — it already covers all 4 packages including
  `agent_brain_mcp` and `agent_brain_uds`, so no new contract is needed.
  Just verify Phase 55's audit lists `check:layering` as a passing gate.
- **D-14:** **Coverage floor for MCP package = 80%** (already enforced in
  `agent-brain-mcp/Taskfile.yml::pr-qa-gate --cov-fail-under=80` — security
  boundary). UDS coverage floor = 80% as well (matches MCP — both packages
  are security-boundary code per v1 plan §9). Root `before-push` already
  uses `task test:cov` per-package, so this gets pulled in automatically.
- **D-15:** **CI matrix:** the existing GitHub Actions workflow that runs
  `task before-push` (or `task pr-qa-gate`) on PRs picks up the MCP/UDS
  packages automatically once D-12 lands. No new workflow YAML. Verify in
  Phase 55 audit that the workflow run includes MCP test output.

### E. Test fixtures & corpus reuse
- **D-16:** **Reuse the existing `tiny_corpus` fixture** at
  `agent-brain-mcp/tests/e2e/fixtures/tiny_corpus/` for the SDK contract
  suite that needs a real backend. Do NOT add a new corpus. If a 16-tool
  test path needs additional fixture content (e.g., `inject_documents`
  needs an enrichment script), add one file under the same fixtures dir
  and document it in `tests/e2e/fixtures/README.md`.
- **D-17:** **Subprocess teardown contract:** every fixture that spawns
  `agent-brain-serve` or `agent-brain-mcp` MUST register a finalizer that
  (a) sends SIGTERM, (b) waits ≤5s, (c) SIGKILLs if still alive,
  (d) asserts the UDS socket path is unlinked, (e) scans `ps` for orphan
  `agent-brain-*` processes and fails the test if any survive. Inherit
  from the Phase 4 pattern in `tests/e2e/conftest.py::indexed_server`.

### F. Audit & sign-off
- **D-18:** Phase 55 produces a short **`VALIDATION.md`** under
  `.planning/phases/55-validation-and-qa-gate/` that checks off VAL-01..04
  with a link to the PR(s), the coverage delta, and a "task before-push
  exit code: 0" attestation copied from the CI run. This is the milestone's
  exit gate — `gsd-complete-milestone` reads it.
- **D-19:** **No new requirements** introduced in Phase 55. If the audit
  finds a Phase 50–54 deliverable is broken, file a follow-up patch PR
  under the originating phase, do not park the fix in Phase 55. Phase 55
  ships when 50–54 are clean.

### Claude's Discretion
- Exact split between `test_contract_tools.py`, `test_contract_resources.py`,
  `test_contract_subscriptions.py`, `test_contract_http_transport.py` files
  vs. one consolidated `test_v2_contract.py` — planner decides based on
  pytest collection times
- Whether subscription cadence assertions use `asyncio.wait_for` with the
  cadence × 1.5 deadline or a polling loop with a TaskGroup
- Exact name of the debug endpoint if Phase 52 didn't expose subscription
  counts (recommend `GET /mcp/subscriptions/__debug` gated behind
  `AGENT_BRAIN_DEBUG=1`)
- Whether to gate the SDK contract suite behind `AGENT_BRAIN_E2E=1` or run
  it inline in `task mcp:test` — recommend inline, since it uses the fake
  httpx backend and stays under 30s
- Diagram (if any) in the v2 design doc's §5 (Test strategy) showing the
  two-layer test architecture

</decisions>

<specifics>
## Specific Ideas

- **Use the existing `tests/test_each_tool.py` parametrize idiom verbatim**
  as the Layer 1 starter — it already covers 7 tools cleanly, just extend
  the matrix to 16 once Phase 54 lands. The pattern is at
  `tests/test_each_tool.py:30-60`.
- **Mirror `tests/test_e2e_stdio.py` for the Layer 2 SDK contract tests** —
  the file demonstrates the correct fixture chain
  (`StdioServerParameters` → `stdio_client` → `ClientSession`) without the
  full subprocess server. Subscription tests need the real
  `agent-brain-mcp` subprocess via this same pattern.
- **DR-5 closure language**: the audit report and v2 design doc §1 must
  explicitly cite `docs/plans/2026-05-28-mcp-uds-transport-design.md §14 #5`
  and note "Resolved in v10.2 Phase 55" so reviewers see the cycle is
  closed. Anyone scanning the v1 design later sees the resolution date.
- **`task before-push` lock guard precedent**: root `before-push` runs
  `./scripts/before_push_lock_guard.sh start` first to snapshot poetry.lock
  state and `defer:` a check. The MCP/UDS sub-tasks both invoke
  `poetry install` transitively, so the guard pattern already covers them
  — verify in Phase 55 that no in-tree `poetry.lock` drift slips through.
- **Layering contract regression risk**: when MCP gains the Streamable HTTP
  transport, it may pull in a new dep (e.g., `uvicorn` for the HTTP
  server). Phase 55 audit must re-run `task check:layering` and confirm
  the existing `mcp must never call server internals` contract still
  passes — this is the same contract that DR-5 makes inviolate.
- **CI cost**: adding MCP+UDS to root `before-push` lengthens local
  pre-push by approximately +60-90s (per-package install + tests).
  Document this in the CHANGELOG and v2 design doc §5 so devs aren't
  surprised. No CI cost change — workflow already runs full monorepo.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & roadmap (mandatory)
- `.planning/REQUIREMENTS.md` §Validation & Quality (VAL) — VAL-01, VAL-02,
  VAL-03, VAL-04 acceptance criteria + traceability table
- `.planning/ROADMAP.md` §Phase 55 — phase goal, depends-on list, four
  success criteria (lines 119-128)
- `.planning/PROJECT.md` §Current Milestone — v10.2 scope statement and
  the 16-tool / subscription / HTTP / contract-test deliverables list

### v2 scope contract (mandatory)
- `docs/roadmaps/mcp/v2-subscriptions-and-resources.md` §Definition of done —
  source contract for VAL-01..04; spells out "all 16 total tools (7 from v1
  + 9 new) covered by parameterized contract tests"
- `docs/roadmaps/mcp/v2-subscriptions-and-resources.md` §Prerequisites —
  cites DR-5 (`New packages folded into root task before-push`); Phase 55
  is the closure

### v1 design lineage (mandatory)
- `docs/plans/2026-05-28-mcp-uds-transport-design.md` §14 #5 — DR-5: deferred
  root QA-gate integration to "10.2.0 + one release cycle"; Phase 55 closes
  this debt
- `docs/plans/2026-05-28-mcp-uds-transport-design.md` §11 — version matrix
  (v1/v2/v3/v4) confirming v2 is the contract-tests milestone
- `docs/plans/2026-05-28-mcp-uds-transport-design.md` §15.1 — original v2
  issue body; same scope this phase validates

### Phase 50–54 context (mandatory; carry-forward)
- `.planning/phases/50-server-endpoint-prep-v2-design-doc/50-CONTEXT.md` —
  sandbox model (decision A), endpoint shapes (decisions B/C), v2 design
  doc structure (decision D). VAL-05 lives in Phase 50; Phase 55's audit
  verifies the doc covers all of v2.
- `.planning/phases/51-deferred-uri-schemes/51-CONTEXT.md` — URI scheme
  decisions (chunk://, graph-entity://, job://, file://) — Phase 55
  contract tests assert templates list returns these
- `.planning/phases/52-resource-subscriptions/52-CONTEXT.md` — subscription
  cadence + cleanup design — Phase 55 VAL-02 verifies this behavior
- `.planning/phases/53-streamable-http-transport/53-CONTEXT.md` — HTTP
  transport shape — Phase 55 VAL-03 verifies this via SDK HTTP client
- `.planning/phases/54-remaining-mcp-tools/54-CONTEXT.md` — tool schemas
  for the 9 v2 tools — Phase 55 VAL-01 contract tests bind to these schemas

### MCP package (existing patterns Phase 55 extends)
- `agent-brain-mcp/tests/test_each_tool.py` — Layer 1 parametrize template
  (currently 7 tools; extend to 16)
- `agent-brain-mcp/tests/test_e2e_stdio.py` — Layer 2 SDK contract test
  template (`StdioServerParameters` + `stdio_client` + `ClientSession`
  fixture chain)
- `agent-brain-mcp/tests/conftest.py` — `fake_httpx_client` fixture that
  backs the in-process contract tests
- `agent-brain-mcp/tests/e2e/conftest.py` — `indexed_server` + `mcp_client`
  fixture stubs (already documents the Phase 4 SIGTERM + socket-unlink
  teardown contract Phase 55 inherits)
- `agent-brain-mcp/tests/e2e/fixtures/tiny_corpus/` — shared E2E corpus
  (reuse; do not duplicate)
- `agent-brain-mcp/Taskfile.yml` — existing `contract`, `e2e`, `pr-qa-gate`
  tasks with `--cov-fail-under=80` (this is the gate Phase 55 wires up)
- `agent-brain-uds/Taskfile.yml` — UDS package's `pr-qa-gate` task to wire
  into root

### Monorepo gates (existing infrastructure Phase 55 modifies)
- `Taskfile.yml` (root) §before-push (lines 196-214) — recipe to extend
  with `task: uds:before-push` + `task: mcp:before-push`
- `Taskfile.yml` (root) §pr-qa-gate (lines 226-235) — recipe to extend
  with `task: uds:pr-qa-gate` + `task: mcp:pr-qa-gate`
- `Taskfile.yml` (root) §check:layering (lines 180-190) — existing
  4-package import-linter contract; Phase 55 audit verifies it still
  passes
- `.importlinter` — layering contracts for all 4 packages including
  `mcp must never call server internals`
- `scripts/before_push_lock_guard.sh` — poetry.lock drift guard already
  invoked by root `before-push`; covers the MCP/UDS additions transitively

### MCP SDK (external; pin in v2 design doc)
- `mcp = "^1.12.0"` (current pin in `agent-brain-mcp/pyproject.toml`).
  Specific symbols Phase 55 uses: `mcp.ClientSession`,
  `mcp.client.stdio.StdioServerParameters`, `mcp.client.stdio.stdio_client`,
  `mcp.client.streamable_http.streamablehttp_client`, `mcp.types.*`.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`agent-brain-mcp/tests/test_each_tool.py`** — Layer 1 contract test
  template. The `@pytest.mark.parametrize("tool_name,arguments", [...])`
  block is exactly the matrix Phase 55 extends from 7 → 16 entries; the
  `_call_tool` helper and the
  `result.root.content / result.root.structuredContent` assertions
  transfer 1:1.
- **`agent-brain-mcp/tests/conftest.py::fake_httpx_client`** — in-memory
  HTTP backend (`_DEFAULT_RESPONSES` dict keyed by `(method, path)`). New
  v2 endpoints (`/query/chunk/{id}`, `/graph/entity/{type}/{id}`) get one
  new entry each. New tools that call additional paths get default
  responses added here.
- **`agent-brain-mcp/tests/test_e2e_stdio.py`** — Layer 2 SDK test
  template. The `fake_server_module` fixture pattern (write a script,
  spawn via `StdioServerParameters`, wrap in `ClientSession`) is the
  Phase 55 baseline; subscription tests just swap the script for
  `agent-brain-mcp` itself.
- **`agent-brain-mcp/tests/e2e/conftest.py::short_state_dir`** — solves
  the macOS 104-byte sockaddr_un limit by mkdtemp under `/tmp/abmcp-e2e-*`.
  Any Phase 55 fixture that touches a real UDS socket inherits this.
- **`agent-brain-mcp/Taskfile.yml::contract`** — already exists as a
  placeholder ("MCP contract validation lands in Phase 4"). Phase 55 turns
  this into the real Layer 2 entry point: `poetry run pytest -m contract`.

### Established Patterns
- **Per-package `pr-qa-gate` with `--cov-fail-under=80`** (`agent-brain-mcp`
  + `agent-brain-uds`, both security-boundary packages). Root gate just
  invokes them; no new coverage logic in root.
- **Stdio SDK fixture chain**: `StdioServerParameters(command=sys.executable,
  args=[str(script)], cwd=..., env={"PYTHONPATH": ...})` → `stdio_client`
  → `ClientSession`. Used 4× in `test_e2e_stdio.py` lines 103-198 — Phase
  55 copies this idiom for the parametrized SDK contract tests.
- **Subprocess teardown**: `tests/e2e/conftest.py::indexed_server` documents
  the SIGTERM → 5s wait → SIGKILL → socket-unlink-check → orphan-ps-check
  contract. Phase 55 fixtures inherit this verbatim.
- **`task before-push` lock guard** — root `before-push` wraps the body in
  `./scripts/before_push_lock_guard.sh start` + `defer: check`. Adding
  MCP/UDS sub-tasks inside the wrapped section means poetry.lock drift
  from their installs is auto-detected.
- **Layering contract regression check** — `task check:layering` runs
  `lint-imports --config .importlinter` against all 4 packages from a
  single `PYTHONPATH` invocation. Already wired; Phase 55 just verifies
  it stays green when MCP gets the HTTP transport.

### Integration Points
- **Root `Taskfile.yml`** lines 196-214 (`before-push`) and 226-235
  (`pr-qa-gate`) are the only files Phase 55 edits in the gate-integration
  surface. Two-line additions each (`task: uds:before-push` +
  `task: mcp:before-push` for the first, the `pr-qa-gate` analogs for the
  second).
- **`.github/workflows/*.yml`** — existing CI workflows that invoke `task
  before-push` or `task pr-qa-gate` automatically pick up the MCP/UDS
  additions. No workflow YAML edits expected; Phase 55 audit confirms by
  inspecting one CI run.
- **`agent-brain-mcp/Taskfile.yml`** — Phase 55 wires the real Layer 2
  command into the existing `contract:` task (currently a stub that
  echoes "MCP contract validation lands in Phase 4"). Replace the echo
  with `poetry run pytest tests/contract -v -m contract`.
- **`agent-brain-uds/Taskfile.yml`** — already exports `before-push` and
  `pr-qa-gate` analogs; no changes needed beyond root wiring.

### Greenfield (no existing pattern)
- **No SDK HTTP-client test exists yet.** `test_e2e_stdio.py` covers stdio
  but `mcp.client.streamable_http.streamablehttp_client` has zero usages
  in the repo. Phase 55 introduces it. Recommend a new module
  `agent-brain-mcp/tests/contract/test_http_transport_contract.py` that
  parallels the stdio template's structure.
- **No subscription test exists yet.** `resources/subscribe` isn't yet
  exercised in any test. Phase 55 introduces the subscribe → notify →
  unsubscribe → disconnect pattern. Recommend
  `tests/contract/test_subscription_lifecycle.py`.
- **No per-client subscription count observability surface exists** on the
  server. If Phase 52 didn't expose one, Phase 55 D-06 falls back to log
  scraping. Document the gap in the Phase 55 plan; do NOT add the debug
  endpoint here — file as a Phase 52 follow-up.
- **No `tests/contract/` directory exists** in `agent-brain-mcp`. Phase 55
  creates it. Initial layout:
  `tests/contract/conftest.py` (subprocess + SDK client fixtures),
  `test_tools_contract.py`, `test_resources_contract.py`,
  `test_subscription_lifecycle.py`, `test_http_transport_contract.py`.

</code_context>

<specifics>
## Carry-forward from Phase 50

(These are decisions from Phase 50's CONTEXT that bind Phase 55's audit
scope. Phase 55 does NOT re-litigate them — it verifies they shipped.)

- **VAL-05 (v2 design doc) is a Phase 50 deliverable.** Phase 55 audit
  checks that the doc exists at `docs/plans/2026-06-{day}-mcp-v2-
  subscriptions.md` and that its §5 (Test strategy) reflects the two-layer
  contract approach decided here (D-01).
- **Sandbox `roots/list` policy** (Phase 50 decision A) — Phase 55 does
  NOT add a sandbox security test (that's a Phase 51 / file:// scheme
  concern); but Phase 55's contract test for `resources/templates/list`
  asserts `file://` appears in the templates response, which exercises
  the wiring.
- **`GET /query/chunk/{id}` and `GET /graph/entity/{type}/{id}`** (Phase
  50 decisions B/C) — Phase 55 contract tests for `chunk://` and
  `graph-entity://` resources implicitly verify these endpoints respond
  per the agreed shapes. Add `_DEFAULT_RESPONSES` entries to
  `fake_httpx_client` matching the Phase 50 response models.
- **#179 (API auth) and #178 (Kuzu SIGSEGV)** — Phase 50 flagged both for
  the v2 design doc's risk register. Phase 55 audit re-checks the doc
  still cites them — if the issues moved while v10.2 was in flight,
  update the design doc once before audit sign-off.
- **DR-5 closure** — Phase 50 documented this in the v2 design doc.
  Phase 55 IS the closure: D-12 lands the root-taskfile edit; D-18
  captures the attestation.

</specifics>

<deferred>
## Deferred Ideas

- **MCP sampling / completion contract tests** — out of v2 scope per
  PROJECT.md "Out of Scope"; revisit when v3 ships if framework adapters
  start exercising sampling. Track under v3 milestone.
- **OAuth 2.1 contract tests for the HTTP transport** — v4 (#188). Phase
  55 only verifies loopback-only behavior; auth tests land alongside
  OAuth implementation.
- **Cross-runtime MCP contract tests (Codex, OpenCode, Gemini)** — runtime
  parity was deferred from v9.6.0 and remains deferred. If v3 framework
  matrix revives it, contract tests get extended to those runtimes there.
- **Performance / latency contract assertions** — Phase 55 asserts
  correctness only. A latency budget for `wait_for_job` progress
  notifications (TOOL-04 says "at least every 2s") is asserted as a
  cadence assertion, but no broader perf budget. Consider an
  `MCP-PERF-01` requirement for v10.3.
- **Mutation / fuzz testing of MCP tool inputs** — out of scope; add to
  backlog as `MCP-FUZZ-01` if a CVE pattern shows up.
- **`/mcp/subscriptions/__debug` endpoint** — recommended fallback for
  D-06 disconnect-cleanup verification. File as a Phase 52 follow-up
  issue (`gh issue create`) rather than a Phase 55 task; planner
  decides if it's actually needed once Phase 52 lands.
- **Spec-version drift CI gate** — a CI job that fails if MCP SDK ships
  a new minor version that we haven't reviewed. Useful, but not v2 scope.
  Backlog as `MCP-CI-01`.
- **Contract test report artifact upload** — pretty HTML report of which
  16 tools passed which schema assertions, uploaded as a CI artifact.
  Nice-to-have; defer to v10.3 once the suite stabilizes.

</deferred>

---

*Phase: 55-validation-and-qa-gate*
*Context gathered: 2026-06-02*
