# Review: MCP Server + UDS Transport Design Plan (2026-05-28)

**Reviewer:** Grok 4.3 (xAI)  
**Date of review:** 2026-05-28  
**Plan under review:** Claude's "Agent Brain: MCP Server + UDS Transport — Design & Implementation Plan" (the long document provided in the query)  
**Status of this review:** Ready for owner decision. No code was edited during this review.

---

## Executive Summary

The submitted plan is **one of the most thorough and ambitious** design documents in the repo. It correctly identifies the single-seam `Backend` protocol, respects the "no silent fallback" principle established in the prior MCP scoping work, and does a good job mapping both northbound (LLM framework) and southbound (Agent Brain HTTP/UDS) contracts.

**Overall assessment:** 8.5/10. Excellent architecture and layering. **Needs strengthening in the verification, security-adversarial, and incremental-stability dimensions** before it is safe to execute as a 12-phase multi-package effort that will touch the release process, Taskfile gates, and plugin surface.

**Critical blocker for execution:** The plan as written would immediately fold two new packages into `task before-push` and `task pr-qa-gate`. Historical precedent (the existing `2026-mcp-server-design.md`) deliberately kept MCP out of the root QA gate until stable. This plan must adopt the same caution or provide an explicit exception with risk acceptance.

---

## 1. Reconciliation with Prior Work (Must Do Before Implementation)

The repository already contains:

- `docs/plans/2026-mcp-server-design.md` (2026-05-26) — a deliberate **scoping-only** artifact that:
  - Names only 4 tools + 4 resources
  - Explicitly defers prompts
  - Defers implementation behind a "MCP vs UDS decision"
  - Recommends **not** wiring the package into root `before-push` until stable (Phase 2/3 language)

**The new plan is a superset** (16 tools, 7 resources, 6 prompts, full CLI multi-transport, dedicated `agent-brain-uds` package, OAuth roadmap).

**Required action:**
- On approval of the combined plan, the 2026-05-26 scoping doc should be marked **SUPERSEDED** with a one-line tombstone at the top and a pointer to this reviewed plan.
- Any design decisions that differ (e.g., 4 vs 16 tools, embedded vs always-external backend, `search` vs `search_documents` naming) must be explicitly called out as "updated by the 2026-05-28 combined transport plan."

---

## 2. Validation & Verification Gaps (Highest Priority)

### 2.1 Missing Dedicated "Verification" Section (Pattern Violation)

Recent high-quality plans (e.g. `2026-05-27-query-explain-parameter.md`) contain a top-level `## Verification` section with:

- Mandatory `task before-push && task pr-qa-gate` invocations
- 5–8 concrete manual E2E commands with expected output shapes
- A PR template checklist

**The submitted plan buries verification** in §18 ("Verification & Acceptance") and mixes functional acceptance criteria with commands. It is good but not at the same standard.

**Recommended graft (copy this section structure into the plan at the end of §18):**

```markdown
## Verification (Mandatory — insert here)

### Pre-flight (every commit that touches new packages)
task install
task uds:test
task mcp:test
task cli:test
task before-push          # MUST exit 0
task pr-qa-gate           # MUST exit 0

### UDS transport parity (run on every transport change)
agent-brain start --uds &
AB_PID=$!
sleep 1
agent-brain --transport uds query "test" > /tmp/uds.json
agent-brain --transport http query "test" > /tmp/http.json
jq -S 'del(.execution_time_ms, .took_ms)' /tmp/uds.json > /tmp/uds-norm.json
jq -S 'del(.execution_time_ms, .took_ms)' /tmp/http.json > /tmp/http-norm.json
diff /tmp/uds-norm.json /tmp/http-norm.json || (echo "Transport parity failure"; exit 1)
kill $AB_PID || true

### MCP stdio subprocess hygiene (critical — do not weaken)
python -c '
import subprocess, time, psutil, os
for i in range(50):
    p = subprocess.Popen(["agent-brain", "--transport", "mcp", "--mcp-transport", "stdio", "status"],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    p.wait(timeout=15)
    time.sleep(0.1)
children = [c for c in psutil.process_iter(["cmdline"]) if "agent-brain-mcp" in " ".join(c.info["cmdline"] or [])]
assert len(children) == 0, f"Orphan MCP processes remain: {[c.pid for c in children]}"
print("MCP stdio hygiene: PASS")
'

### Contract schema drift (new task target)
task mcp:contract   # must be wired; see §15 improvement below

### Framework matrix (nightly or opt-in)
task mcp:framework-matrix || echo "Some optional framework adapters missing — acceptable for first release"

### Manual Claude Desktop smoke (owner-executed before tagging 10.1.0)
# 1. Add to ~/Library/Application Support/Claude/claude_desktop_config.json
# 2. Restart Claude Desktop
# 3. In a fresh project with .agent-brain/ and indexed content:
#    "Use the find-callers prompt on QueryService"
#    "Run search_documents with mode=hybrid, explain=true"
#    "Subscribe to a job:// resource while indexing"
```

### 2.2 Per-Phase Verification Is Too Vague

The 12 phases list deliverables but lack **exit criteria per phase**.

**Improvement:** Add to each phase a bullet:

> **Phase N exit gate:** `task before-push` green + at least N new contract or integration tests committed + one manual E2E scenario from the Verification section above passes on the reviewer's machine.

### 2.3 Performance Claim Lacks Measurement Specification (§18 acceptance item 1)

"≥1.3x throughput" is a good north star but is not reproducible as written.

**Required addition to §18:**

- Specify benchmark harness (new file? `scripts/bench_uds_vs_http.py` using the existing `scripts/query_benchmark.py` as template).
- Corpus size (recommend: the `docs/` directory of this repo + one 50-file Python project).
- Query mix (30% vector, 30% bm25, 25% hybrid, 15% multi).
- Warmup + measurement iterations.
- Hardware note (macOS M-series vs Linux x86).
- Require the actual numbers (p50, p95, p99) to be recorded in the PR description and CHANGELOG.

Without this, the acceptance criterion is not falsifiable.

---

## 3. Security & Adversarial Testing Gaps (UDS Is a New Trust Boundary)

### 3.1 UDS Permissions Validation Is Described But Not Adversarially Tested

§6.5 and §13 describe good checks (owner uid, 0600, parent 0700). This is necessary but insufficient for a security review.

**Add explicit test requirements in Phase 1 (agent-brain-uds):**

In `agent-brain-uds/tests/test_permissions.py` (or equivalent):

- `test_symlink_attack_socket_points_outside_state_dir`
- `test_world_readable_socket_rejected`
- `test_parent_dir_world_writable_rejected`
- `test_different_uid_socket_rejected` (mock `os.stat().st_uid`)
- `test_pointer_file_symlink_attack` (the `/tmp/agent-brain-<sha>.sock.path` fallback path)

Use `pytest-mock` or `unittest.mock` for `os.stat` / `os.getuid`. These tests must be **red** until the real `permissions.py` validation exists.

### 3.2 MCP stdio Attack Surface Is Under-analyzed

When the CLI does `--transport mcp --mcp-transport stdio`, it spawns `agent-brain-mcp` as a child. The plan correctly calls for hygiene, but does not discuss:

- Environment variable leakage to the MCP subprocess (especially `OPENAI_API_KEY` etc. if the user has them in the shell).
- Working directory of the spawned process.
- Signal handling (SIGINT during a long `wait_for_job`).

**Add to §13 (Security Model) and to the MCP client backend implementation checklist:**

> The `McpStdioBackend` must:
> 1. Spawn with `env={k:v for k,v in os.environ if not k.endswith(("_KEY","_TOKEN","_SECRET")) or k in ALLOWLIST}`
> 2. Explicitly set `cwd` to the project root or state_dir (never inherit).
> 3. Wire a timeout + `terminate()` + `kill()` escalation on cancellation.

---

## 4. Package & Dependency Hygiene Improvements

### 4.1 Import Cycle / Layering Enforcement Is Missing

The plan claims "strict layering: server → uds → mcp → cli (no cycles)". This is excellent intent but is currently only a social contract.

**Required addition:**

- Add `import-linter` (or a lightweight `pydeps` + `grep` check) to the new packages' Taskfiles.
- New root task: `task check:layering` (or `task vet:imports`).
- Fail the build if `agent_brain_mcp` imports anything from `agent_brain_cli`, or if `agent_brain_uds` imports from `agent_brain_mcp`, etc.

This is cheap insurance for a 4-package dependency graph.

### 4.2 Root Taskfile Gate Inclusion Is Too Eager

Current plan (§15, §16) folds `uds` and `mcp` into the root `before-push` and `pr-qa-gate` in the first release.

**Historical counter-example:** The 2026-mcp-server-design.md explicitly says:

> "not wired into root `task before-push` or `task pr-qa-gate` until the package is stable."

**Recommendation (pick one):**

A. (Preferred for risk reduction) Keep new packages on **opt-in tasks only** for the 10.1.0 release:
   - `task uds:test`
   - `task mcp:test`
   - `task test:uds-mcp` (aggregator)
   - Document that they will be promoted into the root gate in 10.2 or 10.3 after real usage data.

B. Or add an explicit risk acceptance in the plan: "We accept that a flaky new-package test can block all development for the first 4–6 weeks."

The plan currently does not acknowledge this tension.

---

## 5. Release Process & Versioning Gaps

### 5.1 Lockstep Decision Needs a Rationale Box

The plan says "lockstep ... start at the next minor (10.1.0)".

This has real consequences:
- A bug in the MCP server now forces a server + CLI release even if the server itself is untouched.
- Independent users who only want the MCP package cannot get patches on their cadence.

**Add a one-paragraph "Versioning Decision Record"** (new subsection in §5 or §17):

> **Decision:** All four packages (server, cli, uds, mcp) share a single version line for 10.x.
> **Rationale:** Simplifies the mental model for users ("Agent Brain 10.1.0"), reduces matrix testing, and the MCP/UDS packages are tightly coupled to the server surface anyway.
> **Revisit trigger:** When we have 3+ external MCP-only consumers or when OAuth v2 work begins (at which point a standalone `agent-brain-mcp` with its own version may be extracted).

Update `.claude/commands/ag-brain-release.md` and the agent release file to reference the 4 new version locations (already called out in §16 — good).

### 5.2 Plugin Command Surface for `agent-brain mcp start`

§16 and §9.4 mention a new CLI helper `agent-brain mcp start`. This will almost certainly need a corresponding plugin command (`agent-brain-plugin/commands/agent-brain-mcp-start.md` or similar) so Claude Code users can invoke it.

The plan should explicitly list the new plugin command files it will create (or state "CLI-only for 10.1.0; plugin delegation deferred").

---

## 6. Structural & Documentation Improvements

1. **Split the OAuth section (§11)** into its own design doc (`docs/plans/2026-oauth-remote-agent-brain.md`) and keep only a 1-page summary + migration table in the main plan. The current OAuth section is excellent but makes the main document ~25% longer and most readers will not implement it in v1.

2. **Add a "Success Metrics" table** (separate from acceptance tests):
   - Median UDS query latency p50 < 15 ms on macOS for cached 20-result hybrid queries on the `docs/` corpus.
   - MCP stdio spawn-to-first-tool-call < 800 ms (cold) on M-series.
   - Zero increase in `task before-push` wall time on a clean tree after the new packages stabilize (target: < 8% regression).

3. **Add a one-paragraph "Rollback Plan"** subsection:
   - If UDS socket permission bugs generate > 3 support issues in the first month, the `--uds` / `--uds-only` flags can be removed in a patch release with zero impact on the HTTP path.
   - The MCP package can be uninstalled independently; the CLI will simply lose the `mcp` transport option.

4. **Clarify plugin vs MCP command overlap.** The plan should state whether the long-term vision is:
   - Plugin slash commands remain thin wrappers that shell out to the local CLI (current reality), or
   - The plugin eventually becomes a pure MCP client that talks to `agent-brain-mcp` (preferred for consistency).
   This decision affects how many duplicate implementations we are willing to carry.

5. **E2E integration.** The repo has a mature `e2e/` and `e2e-cli/` harness. The plan should contain an explicit line item: "Add at least one new e2e scenario (`mcp_uds_flow.sh`) that exercises the full stdio → UDS → server path using the existing adapter pattern."

---

## 7. Minor but Actionable Polish Items

- §7.3 tool names: `search_documents` is good, but consider also registering a short alias `search` for human typing in Claude (MCP clients usually show the full name anyway).
- The `wait_for_job` tool + `wait: true` convenience flag on `index_folder` is useful but increases surface area. Make the "convenience arg" explicitly documented as "syntactic sugar; the canonical form is the dedicated tool."
- In §8.1 (Claude Desktop config), add the exact path for Linux (`~/.config/Claude/claude_desktop_config.json` or whatever the actual community path is in 2026).
- §14 (Observability) should mention that the new packages must emit the same structured log keys (`tool_id`, `backend`, `duration_ms`) so existing log dashboards continue to work.

---

## 8. Proposed Insertion Points (for the plan owner)

| Location | What to insert |
|----------|----------------|
| After §2 (Goals) | New subsection "Relationship to prior 2026-mcp-server-design.md scoping doc" |
| End of §5 (Package Layout) | "Versioning Decision Record" box (lockstep rationale) |
| §6.5 (Permissions) | Explicit adversarial test list |
| Each of the 12 phases | "Exit gate" bullet with test count + manual command |
| §13 (Security) | 3–4 paragraph "Adversarial scenarios considered" |
| §15 (Testing Strategy) | "Layering / import cycle enforcement" paragraph + new `task check:layering` |
| §18 | Full grafted "Verification" section (see 2.1 above) |
| §19 (Risks) | New rows for "root QA gate coupling", "performance claim not reproducible", "plugin/MCP command duplication debt" |
| New top-level section after §19 | "Rollback & Decommission Plan" (1 page) |

---

## 9. Final Recommendation

**Do not start Phase 0 until the owner has:**

1. Written the "Verification" section modeled on the query-explain plan.
2. Decided on root-Taskfile gate inclusion (opt-in vs immediate) and documented the decision.
3. Added the adversarial UDS permission tests as Phase 1 deliverables.
4. Produced (or explicitly deferred) the performance benchmark harness spec.
5. Added the one-paragraph reconciliation note for the 2026-05-26 MCP scoping doc.

Once those five items are addressed, the plan will be at the same (or higher) level of execution readiness as the best plans currently in `docs/plans/`.

The architecture itself is sound. The risk is in the **verification and incremental rollout discipline**, not the technical vision.

---

**End of review.** This document may be copied into the approved plan or kept as a companion review artifact. No implementation files were modified during the production of this review.