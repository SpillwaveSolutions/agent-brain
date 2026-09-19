# Integration test of v10.7.0, issue #236 reproduction, and multi-host parity

## Context

Main is clean at v10.7.0. Nothing has exercised the installed product end to end since the 10.7.0 release. You asked for three things:

1. A full integration test of the current version against a committed sample project, on Ollama, with no cloud keys.
2. A reproduction attempt for issue #236 (the reported `mcp` dependency conflict on 10.3.0 and later). Ping the reporter if it does not reproduce. Close after two weeks of silence.
3. Multi-host parity with the OKF plugins (Claude Code, Codex, Cursor, Grok, and the Agent Plugins 1.0 universal manifest). File issues for gaps, put them first on the roadmap, and port them.

Findings from exploration that shape the plan:

- **Multi-host packaging already shipped in PR #243.** All five manifests exist under `agent-brain-plugin/` and CI checks their versions. `install-agent` supports claude, opencode, codex, cursor, grok, and skill-runtime. Agent Brain is ahead of the OKF plugins on MCP wiring (`mcp.json`) and the CLI installer. The real gaps are stale docs that still mention Gemini, no per-host install instructions in the READMEs, no `docs/HOSTS.md`, no Cursor rules file, and no plugin-facing `AGENTS.md`.
- **Issue #236 has no comments since 2026-08-30.** Published metadata for `agent-brain-ag-mcp` is identical at 10.2.1 and 10.3.0 (`mcp<2.0.0,>=1.12.0`). The reporter filed the parent issue on 2026-06-24, before `mcp` 2.0.0 shipped on 2026-07-28. The earlier investigation used `uv`, not `pip`, and skipped 10.3.0 and 10.3.1. A new risk exists now: `mcp` 2.x is current, and our cap `mcp<2.0.0` blocks co-install with any tool that needs 2.x.
- **No cloud keys in the shell.** Ollama runs locally with `nomic-embed-text`. No local chat model is pulled. Cloud models (`kimi-k2.5:cloud`, `deepseek-v3.2:cloud`) are listed.
- **Existing scripts are stale.** `scripts/quick_start_guide.sh` uses `poetry run` and indexes the whole monorepo. `.claude/commands/ag-install-local.md` points at a script path that does not exist. The `uat-tester` agent uses legacy `DOC_SERVE_*` names. This plan installs wheels by hand instead.

## Step 0: Branch and plan file

1. `git checkout -b chore/v10.7-integration-test-and-host-parity` from main.
2. Copy this plan to `docs/plans/2026-09-19-integration-test-236-host-parity.md` (CLAUDE.md planning rule).

## Part 1: Integration test on the installed product

### Create the sample project

Create `e2e/sample-project/` as a small, coherent Python project. Keep it under 300 lines total.

```
e2e/sample-project/
  CLAUDE.md                 project rules, points agents at agent-brain search
  README.md
  docs/architecture.md      three-layer design: api -> service -> repository
  docs/runbook.md           start, stop, and reset procedures
  docs/adr/0001-sqlite-store.md
  src/inventory/__init__.py
  src/inventory/models.py   Item dataclass
  src/inventory/repository.py  InMemoryRepository, SqliteRepository
  src/inventory/service.py  InventoryService with reserve_stock and restock
  src/inventory/api.py      FastAPI-style handlers that call the service
  tests/test_service.py
  .gitignore                ignores .agent-brain/
```

Each doc states one fact that a query can target. Examples: "reserve_stock raises OutOfStock when quantity exceeds on-hand", "the runbook reset command deletes the sqlite file", "ADR 0001 picks sqlite over postgres for single-node installs".

### Install v10.7.0 into a clean venv

```bash
for p in agent-brain-server agent-brain-uds agent-brain-mcp agent-brain-cli; do (cd $p && poetry build); done
uv venv /tmp/ab-int --python 3.11
source /tmp/ab-int/bin/activate
uv pip install agent-brain-server/dist/agent_brain_rag-10.7.0-*.whl \
  agent-brain-uds/dist/agent_brain_uds-10.7.0-*.whl \
  agent-brain-mcp/dist/agent_brain_ag_mcp-10.7.0-*.whl \
  agent-brain-cli/dist/agent_brain_cli-10.7.0-*.whl
agent-brain --version   # expect 10.7.0
```

The venv lives in the scratchpad dir, not `/tmp`. The install must pull `agent-brain-rag` from the local wheel, not PyPI. Check with `uv pip show agent-brain-rag`.

### Configure ollama

1. Write `e2e/sample-project/.agent-brain/config.yaml` from `e2e/fixtures/config_ollama_only.yaml`. Set `graphrag.enabled: true`, `use_llm_extraction: false`, `use_code_metadata: true`.
2. Pick the chat model for summaries. Try `ollama run deepseek-v3.2:cloud "say ok"`. If that fails, run `ollama pull llama3.2` (about 2 GB) and use it. Summaries are optional. Skip them if neither model works, and record that in the report.

### Run the flow

Run from `e2e/sample-project/`:

1. `agent-brain init` then `agent-brain start --json`. Check `.agent-brain/runtime.json` and `agent-brain status`.
2. `agent-brain doctor`.
3. `agent-brain index . --include-code` then `agent-brain jobs --watch` until done. Record the elapsed time and chunk count from `agent-brain status --json`.
4. `agent-brain folders list` and `agent-brain types list`.
5. Queries, one per mode, each with a known expected hit:
   - `query "what happens when you reserve more stock than is on hand" --mode hybrid` expects `service.py` or `architecture.md`.
   - `query "OutOfStock" --mode bm25 --source-types code` expects `service.py`.
   - `query "why sqlite instead of postgres" --mode vector` expects the ADR.
   - `query "how do I reset the store" --mode hybrid --source-types doc` expects the runbook.
   - `query "InventoryService" --mode graph` and `--mode multi` expect graph hits on the class.
   - `query "reserve_stock" --explain --scores` to check the explain path.
6. MCP: `agent-brain mcp start --json`, then `agent-brain --transport mcp resources list`, `resources read corpus://status`, and `agent-brain prompt explain-architecture`. Run one search through the MCP transport: `agent-brain --transport mcp query "reserve stock"`.
7. UDS: `agent-brain --transport uds status`.
8. Summaries, if a chat model works: `agent-brain index . --include-code --generate-summaries --force`, then repeat the bm25 query and confirm summaries appear with `--full`.
9. `agent-brain reset --yes`, confirm count is zero, then `agent-brain mcp stop` and `agent-brain stop`.

### Report

Write `docs/plans/2026-09-19-v10.7.0-integration-test-report.md`. One table: step, expected, actual, pass or fail, time. List every defect found. File a GitHub issue for each real defect with the exact command and output.

Do not fix product defects in this branch unless the fix is under about 20 lines and the test proves it. Larger fixes get an issue.

## Part 2: Reproduce issue #236

### Reproduction matrix

Use `pip`, not `uv`, in fresh venvs on `python3.10` (Homebrew 3.10.14). Run each case in its own venv under the scratchpad dir. Capture full resolver output.

| Case | Command | Purpose |
|---|---|---|
| A | `pip install agent-brain-rag==10.3.0 agent-brain-cli==10.3.0 agent-brain-ag-mcp==10.3.0` | The version the reporter named. |
| B | `pip install agent-brain-rag==10.7.0 agent-brain-cli==10.7.0 agent-brain-ag-mcp==10.7.0` | Current release. |
| C | `pip install agent-brain-rag==10.2.0 agent-brain-cli==10.2.0 agent-brain-ag-mcp==10.2.0` then `pip install -U agent-brain-rag agent-brain-cli agent-brain-ag-mcp` | The upgrade path from the reporter's pinned version. |
| D | `pip install "mcp==1.9.4"` then `pip install agent-brain-ag-mcp==10.4.0` | Pre-existing old `mcp` pin. Expect a conflict. |
| E | `pip install "mcp>=2"` then `pip install agent-brain-ag-mcp==10.7.0` | Pre-existing `mcp` 2.x. Expect a conflict on our `<2.0.0` cap. |
| F | `pip install --dry-run agent-brain-cli==10.3.0 agent-brain-rag==10.3.0` with no MCP package | Rules out the CLI-only path. |

Use `pip install --dry-run` first for speed, then a real install for A and B only.

### Outcome handling

- If A, B, C, or F fail: the issue is real. Capture the resolver error, find the offending pin, and file the fix as a follow-up with a plan. Report before you change any pin.
- If only D or E fail: post a comment on #236 with the matrix results, state that a fresh venv resolves clean, and ask the reporter for the four items already listed in the issue. State the two-week window in the comment. Add the comment text to the report.
- If E fails: open a new issue "Evaluate mcp 2.x support" with the resolver output, labeled `enhancement`. `mcp` 2.x changes `httpx` to `httpx2` and raises `pydantic` to 2.12, so this is a real migration, not a pin bump.

Do not close #236 in this session. Record the close date (2026-10-03) in the project-state memory.

## Part 3: Multi-host parity with the OKF plugins

### File the issue

Open one issue: "Plugin: multi-host parity with the OKF plugins (docs, Cursor rules, AGENTS.md)". Labels: `enhancement`, `roadmap`. Body states that manifests and installers shipped in #243, then lists the gaps as a checklist:

1. Remove Gemini and add cursor and grok in `agent-brain-plugin/commands/agent-brain-install-agent.md` and `docs/PLUGIN_GUIDE.md` (runtime table near line 333 and line 548).
2. Add per-host install sections to `README.md` and `agent-brain-plugin/README.md`, in the same shape as `okf-graph-eng/README.md` lines 108 to 123.
3. Add `docs/HOSTS.md`: one table of host, manifest read, install command, and MCP config target.
4. Add `agent-brain-plugin/.cursor/rules/agent-brain.mdc` with `alwaysApply: true`. Add `"rules": ".cursor/rules/"` to `agent-brain-plugin/.cursor-plugin/plugin.json`. Extend `CursorConverter.install()` in `agent-brain-cli/agent_brain_cli/runtime/cursor_converter.py` to copy `.cursor/rules/`.
5. Add `agent-brain-plugin/AGENTS.md`: the host compatibility contract that Cursor cloud and Grok sessions read.
6. Skipped on purpose: `hosts/*/SKILL.md` and per-host hooks. Agent Brain has no hooks and no shared write protocol, so there is nothing to bind. Note this in the issue so it does not come back.

State in the body that this issue is first on the roadmap, ahead of #219. Update the project-state memory to match.

### Implement items 1 through 5 on the same branch

- Reuse the OKF files as templates. Reference copies are at `~/.claude/plugins/cache/spillwave-second-brain/okf-graph-eng/0.8.2/` (`AGENTS.md`, `.cursor/rules/*.mdc`, `docs/HOSTS.md`, `docs/CURSOR.md`).
- Keep one shared payload. Do not copy skills per host.
- Add one test for the converter change in `agent-brain-cli/tests/` next to the existing cursor converter tests. Assert that the rules file lands in the target dir.
- `scripts/check_plugin_manifest_versions.sh` needs no change. The new files carry no version string.
- Run `task before-push`.
- Prove the install path after the change with the venv from Part 1: `agent-brain install-agent --agent cursor --dry-run` and `--agent grok --dry-run` from the sample project. Add the output to the report.

## Validation before push

1. `task before-push` exits 0.
2. `task pr-qa-gate` exits 0.
3. The integration report has no unexplained FAIL rows.
4. `git status` shows only `e2e/sample-project/`, the docs and plugin files from Part 3, the converter change and its test, the plan, the report, and a CHANGELOG entry under Unreleased.

Then push and open one PR titled `chore: v10.7.0 integration test fixture, host parity docs and Cursor rules`. Link the new parity issue with `Closes`. Link #236 with `Refs`.

## Deliverables

- `e2e/sample-project/` committed fixture.
- `docs/plans/2026-09-19-v10.7.0-integration-test-report.md`.
- Comment on #236, plus a new `mcp` 2.x issue if case E fails.
- New parity issue, labeled `roadmap`, listed first.
- Items 1 to 5 of the parity issue implemented and merged in one PR.
- Memory update: parity issue first on roadmap, #236 close date 2026-10-03.
