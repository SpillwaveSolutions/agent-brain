# Phase 63: Tooling + docs + integration page - Context

**Gathered:** 2026-06-12
**Status:** Ready for planning
**Source:** plan-phase inline decisions (research disabled at config; mirrors Phase 61/62 planning path)

<domain>
## Phase Boundary

Land the operator-facing surface for v10.3 — the FINAL phase of the milestone. Three deliverables:

1. **`task mcp:framework-matrix`** (TOOLING-V3-01) — a Taskfile target that runs the full 7-framework
   smoke-test matrix (5 Python via Phase 61, 2 TypeScript via Phase 62), opt-in/gated, sequential,
   with per-framework setup + teardown.
2. **Nightly advisory CI** (TOOLING-V3-02) — `.github/workflows/framework-matrix.yml` running the task
   target against `main` on a nightly cron; ADVISORY ONLY (failure must NOT block PRs); results
   published as a GitHub status check tagged `advisory`.
3. **`docs/INTEGRATIONS.md`** (DOCS-V3-01) — one short copy-pasteable page per framework for all 7
   smoke-tested frameworks, PLUS a "config recipes" section for 5 editor-side integrations
   (Goose, Continue.dev, Cline, Cursor, Cody) that ship docs-only in v10.3, PLUS an SDK-pinning note.

In scope:
- Root Taskfile wiring (`mcp:framework-matrix` target + the per-package include idiom from Phase 60-03)
- A runner mechanism that bootstraps each framework's pinned deps then runs its smoke test
- The GitHub Actions nightly workflow (cron + advisory status check, non-blocking)
- `docs/INTEGRATIONS.md` authoring

Out of scope:
- Any change to the Phase 61 Python smoke tests or Phase 62 TS smoke tests themselves (consume as-is)
- Smoke tests for the 5 editor integrations (Goose/Continue.dev/Cline/Cursor/Cody) — DOCS-ONLY in v10.3
- OAuth 2.1 / remote MCP (held for v10.4)
- Making the matrix part of `task before-push` or PR-blocking CI — it stays opt-in + advisory

</domain>

<decisions>
## Implementation Decisions

### `task mcp:framework-matrix` behavior (LOCKED — user decision 2026-06-12)
- **Self-bootstrap then run.** The target installs/refreshes each framework's pinned deps BEFORE running
  its smoke test — fully turnkey so the nightly CI calls the SAME target with no extra setup steps:
  - For each of the 5 Python frameworks (`openai-agents`, `langchain`, `llama-index`, `pydantic-ai`,
    `autogen`): run `framework-matrix/bootstrap_venv.sh <framework>` (pinned install, exits 3 on drift),
    then run that framework's `pytest -m framework` in its isolated venv.
  - For TypeScript: `cd framework-matrix/ts && pnpm install --frozen-lockfile && pnpm test`.
  - **Sequential**, per-framework setup + teardown (each framework fully set up, run, torn down before
    the next) — so one framework's heavy deps don't collide and orphan subprocesses don't accumulate
    (inherits Phase 60 hygiene + Phase 61/62 fixtures).
- **Gating: `FRAMEWORK_MATRIX=1` env OR explicit `--force`** (per SC1). Without the gate, the target
  prints a one-line "slow + opt-in; set FRAMEWORK_MATRIX=1 to run" message and exits 0 (no-op) — so it
  NEVER accidentally runs in `task before-push` or a normal `task` invocation.
- Documented as slow + opt-in in BOTH the Taskfile (comment/desc) and `docs/INTEGRATIONS.md`.
- **Taskfile placement:** root `Taskfile.yml` under the `mcp:` namespace. Follow the Phase 60-03
  precedent EXACTLY — the per-package `includes: mcp:` alias prepends the namespace, so avoid the cyclic
  collision that bit 60-03 (`task: Found multiple tasks (mcp:...) included by "mcp"`). Prefer defining
  the target at root directly OR using a bare per-package name that the include aliases — replicate
  whatever 60-03's `stress:orphan-test` ended up doing. Read `agent-brain-mcp/Taskfile.yml` +
  root `Taskfile.yml` lines around the `mcp:` include before wiring.

### Nightly advisory CI (`.github/workflows/framework-matrix.yml`)
- **Trigger:** `schedule:` nightly cron (pick a low-traffic UTC hour, e.g. `cron: "0 7 * * *"`) PLUS
  `workflow_dispatch:` for manual runs. NOT on `push`/`pull_request` (must not block PRs).
- **Runs against `main`**, sets `FRAMEWORK_MATRIX=1`, calls `task mcp:framework-matrix`.
- **Advisory only:** the job must NOT be a required check and a failure must NOT block any PR. Achieve
  this by (a) only triggering on schedule/dispatch (never on PR events) AND (b) NOT marking it required.
  Publish the result as a GitHub status check/commit status tagged `advisory` (e.g. via
  `actions/github-script` posting a commit status with context `framework-matrix (advisory)`), so the
  outcome is visible on `main` without gating merges.
- Provide whatever secrets the smoke tests need (e.g. `OPENAI_API_KEY` from repo secrets) so the seeded
  corpus actually indexes; if a secret is absent the matrix should SKIP gracefully (Phase 61 precedent),
  not hard-fail the workflow.
- Install Task, Python/Poetry + uv, Node + pnpm (corepack) as workflow setup steps before the target.

### `docs/INTEGRATIONS.md` structure
- **Per-framework pages (7):** OpenAI Agents SDK, LangChain, LlamaIndex, Pydantic AI, Autogen/AG2,
  Mastra, Vercel AI SDK. Each a SHORT copy-pasteable page: the server command to launch
  (`agent-brain mcp start` / stdio `agent-brain-mcp`), the transport (stdio and/or streamable-http),
  capabilities (the `search_documents` tool + what else is exposed), and a minimal connect snippet that
  mirrors the corresponding smoke test in `framework-matrix/<fw>/` (Python) or `framework-matrix/ts/`.
- **Config recipes section (5, docs-only):** Goose, Continue.dev, Cline, Cursor, Cody. Each a short MCP
  server config snippet in that editor's config format. These have NO smoke test in v10.3 — clearly
  label them "config-only, not smoke-tested in v10.3".
- **SDK-pinning note (SC4):** a section pointing operators at the pinned versions — the per-framework
  `framework-matrix/<fw>/requirements.txt` (Python) and `framework-matrix/ts/package.json` +
  `framework-matrix/ts/PINS.md` (TS) — so they can align their environment with the tested versions.
- Cross-link from an existing docs entry point if natural (e.g. README or docs index), but the page
  itself is the deliverable.

### Claude's Discretion
- Exact runner mechanism for the task target (inline shell loop in the Taskfile vs a
  `scripts/run_framework_matrix.sh` helper that the task calls — a script is likely cleaner given the
  7-framework sequential bootstrap+run+teardown logic). Prefer a `scripts/` helper if the Taskfile
  inline grows unwieldy.
- Exact cron hour, status-check context string wording, and workflow step ordering.
- The exact prose/snippets per framework page and per editor config recipe — but these MUST be
  resolved at EXECUTION time via context7 (`npx ctx7@latest`) for current MCP-config formats of
  Goose/Continue.dev/Cline/Cursor/Cody and current connect snippets, since research is disabled. Do NOT
  hard-code guessed config schemas.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Framework matrix (the thing being wired + documented)
- `framework-matrix/README.md` — matrix layout + opt-in contract + bootstrap usage
- `framework-matrix/bootstrap_venv.sh` — the per-framework pinned-venv bootstrap (exits 3 on drift) the
  task target calls for the 5 Python frameworks
- `framework-matrix/pytest.ini` — the opt-in `framework` marker (Python smoke tests)
- `framework-matrix/<fw>/` for each of openai-agents, langchain, llama-index, pydantic-ai, autogen —
  `requirements.txt` (pins) + `test_*_smoke.py` + `README.md` (per-framework page source material)
- `framework-matrix/ts/README.md`, `framework-matrix/ts/package.json`, `framework-matrix/ts/PINS.md`,
  `framework-matrix/ts/test/{mastra,vercel-ai-sdk}.test.ts` — the TS half (`pnpm test`) + page source

### Taskfile wiring precedent (avoid the 60-03 cyclic-include trap)
- `Taskfile.yml` (root) — the `includes: mcp:` alias + existing `mcp:*` targets; see `mcp:before-push`
  and `mcp:stress:orphan-test`
- `agent-brain-mcp/Taskfile.yml` — per-package tasks; `stress:orphan-test:` shows the bare-name idiom
  that resolves the include-namespace collision (Phase 60-03 decision in STATE.md)

### CI precedent
- `.github/workflows/` — existing workflows (match the repo's setup-step conventions for Task /
  Poetry / uv / Node; the release + before-push workflows are the closest analogues)

### Roadmap / requirements
- `.planning/ROADMAP.md` — Phase 63 section (goal, 4 success criteria, TOOLING-V3-01/02 + DOCS-V3-01)
- `.planning/REQUIREMENTS.md` — TOOLING-V3-01, TOOLING-V3-02, DOCS-V3-01 definitions

</canonical_refs>

<specifics>
## Specific Ideas

- Requirements: **TOOLING-V3-01** (`task mcp:framework-matrix` target), **TOOLING-V3-02** (nightly
  advisory CI workflow), **DOCS-V3-01** (`docs/INTEGRATIONS.md`).
- 7 smoke-tested frameworks: OpenAI Agents, LangChain, LlamaIndex, Pydantic AI, Autogen (Python) +
  Mastra, Vercel AI SDK (TS).
- 5 docs-only config recipes: Goose, Continue.dev, Cline, Cursor, Cody.
- Gate: `FRAMEWORK_MATRIX=1` env or `--force`; sequential per-framework setup/teardown; self-bootstrap.
- Advisory CI = schedule/dispatch only, never on PR events, not a required check, status tagged `advisory`.

</specifics>

<deferred>
## Deferred Ideas

- Smoke tests for the 5 editor integrations (Goose/Continue.dev/Cline/Cursor/Cody) — docs-only in v10.3;
  promoting any to a real smoke test is a future-milestone decision.
- Making the framework matrix a required/PR-blocking check — explicitly out (advisory only; framework
  drift is expected).
- OAuth 2.1 / remote MCP — v10.4 (#188).

</deferred>

---

*Phase: 63-tooling-docs-integration-page*
*Context gathered: 2026-06-12 via plan-phase inline decisions (self-bootstrapping task target locked by user)*
