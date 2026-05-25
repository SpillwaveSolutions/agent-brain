# Plan: Close out open GitHub issues + surface setup state

## Context

Nine open issues on `SpillwaveSolutions/agent-brain` cluster into three themes:

1. **Things break silently when the project is half-configured** — graph index
   silently produces zero triplets (#129), `graphrag:` YAML section is ignored
   (#126), `status` quietly hits the wrong port (#128), file watcher loops
   forever (#123), CLI talks to the wrong server in a mono-repo (#124).
2. **Install fails before the user ever runs anything** — the hard `cohere`
   dependency drags in a broken `tokenizers==0.20.3` wheel on macOS/M1 (#122,
   #125).
3. **One genuine indexing bug** — tiktoken rejects `<|endoftext|>`-style
   tokens in source text (#114).

The user asked us to (a) fix these and (b) make setup state *visible* — detect
when an install isn't ready and tell the user what to do, rather than failing
silently or with a confusing trace. A plugin-side `ab-setup-check.sh` already
exists; the canonical version belongs in the CLI so plain `pip install`
users get it too, and so other CLI commands can call it when they hit a
suspicious failure.

Issue #106 is a strategic roadmap thread, not a bug — close-out is out of
scope here.

## Shape of the change

```
         ┌──────────────────────────────────────────────────────────┐
         │  agent-brain CLI                                         │
         │                                                          │
         │   ┌──────────────────────┐    ┌────────────────────────┐ │
         │   │ project_resolver.py  │◄───┤ init / start / status  │ │
         │   │  (NEW shared module) │    │ query / index / jobs   │ │
         │   │  prefers local       │    └────────────────────────┘ │
         │   │  .agent-brain/ over  │                ▲              │
         │   │  git root            │                │ on error,    │
         │   └──────────────────────┘                │ run subset   │
         │                                           ▼              │
         │   ┌────────────────────────────────────────────────────┐ │
         │   │ commands/doctor.py  (NEW)                          │ │
         │   │   reuses ab-setup-check checks, returns JSON or    │ │
         │   │   pretty table, suggests next action               │ │
         │   └────────────────────────────────────────────────────┘ │
         └──────────────────────────────────────────────────────────┘
                                  │
                                  ▼
         ┌──────────────────────────────────────────────────────────┐
         │  agent-brain-server                                      │
         │   project_root.py  ──►  prefers local .agent-brain/      │
         │   provider_config.py ─► reads graphrag: section          │
         │   graph_extractors.py ─► uses lx.extract() not           │
         │                          extract_relations()             │
         │   file_watcher_service.py ─► ignores .agent-brain/       │
         │                              .claude/                    │
         │   storage_paths.py ─► resolves GRAPH_INDEX_PATH          │
         └──────────────────────────────────────────────────────────┘
```

The three project-root resolvers (cli/config.py, cli/commands/init.py,
cli/commands/start.py, server/project_root.py) all share the same bug; we
unify on one module per package and change the resolution order in one place.

## Work items, in dependency order

### 1. Shared project-root resolver — fixes #124 and #128

Currently four copies of `resolve_project_root()` all do
`git rev-parse --show-toplevel` first, then walk up looking for
`.agent-brain/`. In a mono-repo with `projects/my-app/.agent-brain/`, the
git step jumps to the top and skips the local state dir, so `runtime.json`
isn't found and `get_server_url()` falls back to `http://127.0.0.1:8000`.

- Rename `agent-brain-cli/agent_brain_cli/config.py:_find_project_root`
  into a new public function `resolve_project_root()` and reorder it: walk
  up from cwd looking for `.agent-brain/` (and legacy `.claude/agent-brain/`),
  return the first match; only fall back to `git rev-parse` and the
  pyproject/. claude markers if no local state dir is found.
- Delete the duplicate `resolve_project_root` in
  `agent-brain-cli/agent_brain_cli/commands/init.py` and
  `commands/start.py`; import from the shared module.
- Apply the same reorder to
  `agent-brain-server/agent_brain_server/project_root.py:resolve_project_root`.
  The server uses it in the lifespan fallback at
  `api/main.py:248-260`, so the fix also helps direct `uvicorn` runs.
- Add tests in `agent-brain-cli/tests/` covering: nested `.agent-brain/`
  in a git repo, no git repo, only git root has `.agent-brain/`, no state
  dir anywhere.

### 2. File watcher ignore list — fixes #123

In `agent-brain-server/agent_brain_server/services/file_watcher_service.py`
add `.agent-brain` and `.claude` to `_EXTRA_IGNORE_DIRS` (lines 35–44).
That's the minimum to break the loop where job logs trigger new jobs.
Add a regression test asserting that mutations under
`<watched>/.agent-brain/logs/` don't fire the `enqueue_callback`.

### 3. LangExtract v1.x API migration — fixes #129

`agent-brain-server/agent_brain_server/indexing/graph_extractors.py:716`
imports `extract_relations`, which doesn't exist in langextract ≥1.0.

- Replace the import with `import langextract as lx`.
- Build a single module-level `_EXAMPLES` list of `lx.data.ExampleData`
  showing one or two subject/predicate/object extractions.
- Replace the `extract_relations(...)` call with
  `lx.extract(text_or_documents=text, prompt_description=..., examples=_EXAMPLES, model_id=self.model or <default>, language_model_params={...})`.
- Adapt `_convert_relations` to read from the returned
  `result.extractions` list (each item has `extraction_class`,
  `extraction_text`, `attributes`); build `GraphTriple` from the
  attributes dict (subject / predicate / object).
- Replace the broad `except ImportError` catch with two distinct
  branches so a real ImportError still says "install with --extras
  graphrag" but a *missing-attribute* failure surfaces clearly. Today the
  AttributeError is swallowed as "langextract not installed."
- Update `agent-brain-server/tests/unit/test_graph_extractors.py` to
  patch `langextract.extract` rather than `extract_relations`.

### 4. GraphRAG YAML schema — fixes #126

Right now `ENABLE_GRAPH_INDEX` and friends are only readable from env vars
(`config/settings.py:65-81`). The wizard writes `graphrag:` into
`config.yaml` but `provider_config.py` never parses it.

- Add a `GraphRAGConfig` Pydantic model in
  `agent-brain-server/agent_brain_server/config/provider_config.py`
  alongside `StorageConfig`. Fields mirror the env-var settings:
  `enabled`, `store_type`, `index_path`, `extraction_model`,
  `max_triplets_per_chunk`, `doc_extractor`, `langextract_provider`,
  `langextract_model`, `traversal_depth`, `rrf_k`.
- Add `graphrag: GraphRAGConfig` to `ProviderSettings`.
- Where existing code reads `settings.ENABLE_GRAPH_INDEX` etc. (see
  list at `services/query_service.py:516,621`,
  `services/indexing_service.py:704`, `api/routers/index.py:186-190`,
  `storage/graph_store.py:66-86,170`), introduce a small accessor in
  `provider_config.py` (`get_graphrag_config()`) that prefers the YAML
  value and falls back to the env-var `Settings` value. Update call
  sites to use it. Keep env vars working — they remain the override.
- Fix path resolution: when `index_path` is relative, resolve it under
  the state directory using the existing `storage_paths.resolve_storage_paths`
  helper rather than CWD. The hook is in `storage/graph_store.py:66`.
- Surface a clear warning at server startup if `graphrag.enabled: true`
  but `langextract` import fails — log once with the install hint, not
  silently per chunk.

### 5. Make `cohere` optional — fixes #122 and #125

The install failure is `tokenizers==0.20.3` (malformed pyproject) pulled
in by `cohere ^5.0.0`, which `agent-brain-server/pyproject.toml:46`
declares as a hard dep even though most users never enable Cohere
embeddings.

- Move `cohere` from `[tool.poetry.dependencies]` to an `extras` block
  next to `graphrag`: `cohere = ["cohere"]`.
- Make
  `agent-brain-server/agent_brain_server/providers/embedding/cohere.py`
  import lazily inside `__init__` (it already imports at module top,
  line 6) and raise a clear error
  `"Cohere provider selected but cohere is not installed. Run: pip install 'agent-brain-rag[cohere]'"`.
- Pin `cohere = ">=5.21.0"` inside the extra to avoid the bad
  tokenizers transitive (5.21.x lines pull `tokenizers>=0.21` which has
  a fixed pyproject).
- Update `docs/PROVIDER_CONFIGURATION.md` to mention the extras install
  for Cohere users.
- Refresh `poetry.lock` (`poetry lock --no-update` then `poetry install`).

### 6. Disallowed special tokens switch — fixes #114

When indexing text that contains `<|endoftext|>` (e.g. vLLM docs), tiktoken
raises *"Encountered text corresponding to disallowed special token"*.
Currently no knob exists. Two changes:

- Add `ALLOW_SPECIAL_TOKENS_IN_TEXT: bool = False` to
  `agent-brain-server/agent_brain_server/config/settings.py` plus
  `special_tokens` field on the embedding `GraphRAGConfig` sibling
  `EmbeddingConfig` so it's also settable via YAML.
- Where chunks are sent for embedding/token-counting (find the call
  sites that touch tiktoken — currently inside llama-index's openai
  embedding wrapper; we wrap the input), preprocess: if
  `allow_special_tokens_in_text` is true, call
  `tiktoken.Encoding.encode(text, disallowed_special=())`. Otherwise,
  replace the literal special tokens with a placeholder (e.g.
  `[SPECIAL_TOKEN]`). Put the preprocessing in
  `services/indexing_service.py` before chunks are handed to the
  embedding provider.
- Test with a fixture document containing `<|endoftext|>` and assert
  that indexing completes both with the flag on and off.

### 7. `agent-brain doctor` command — the "is my setup OK?" surface

A first-class CLI command that consolidates everything we already
check in `agent-brain-plugin/scripts/ab-setup-check.sh` plus a few
agent-brain-specific things.

- New file `agent-brain-cli/agent_brain_cli/commands/doctor.py`.
  Registered as `cli.add_command(doctor_command, name="doctor")` in
  `agent_brain_cli/cli.py`.
- Checks (each returns OK / WARN / FAIL + a one-line fix hint):
  1. Python ≥ 3.10.
  2. `agent-brain --version` resolves and matches expected.
  3. Project root resolved via the shared resolver (item 1) — show
     which directory was picked and *why* (local `.agent-brain/` vs
     git root vs cwd).
  4. `.agent-brain/config.json` exists.
  5. `config.yaml` parses cleanly, list active embedding +
     summarization providers.
  6. Required API key for the active provider is in env (boolean — never
     print value).
  7. `runtime.json` present → server is reachable on
     `runtime.base_url`; if reachable, hit `/health` and surface
     the indexing status.
  8. If GraphRAG enabled: `langextract` importable; warn if not.
  9. If active embedding provider is Cohere: `cohere` importable;
     hint to install with the extra.
  10. `.gitignore` excludes `.agent-brain/` (warn if not).
- Flags: `--json` (machine-readable, mirrors the bash script schema),
  `--fix` (run safe auto-fixes only: create missing dirs, add
  `.agent-brain/` to `.gitignore`, copy `config.yaml.example`).
- Exit code 0 only when all critical checks pass; non-zero otherwise.

Reuse: the bash script can stay for the plugin's permissionless flow,
but the CLI version becomes the source of truth. Update
`scripts/ab-setup-check.sh` to shell out to `agent-brain doctor --json`
when the CLI is installed, falling back to its current standalone logic
otherwise.

### 8. Auto-suggest doctor on suspicious failures

The cheap, high-impact piece. Today when `agent-brain status` can't
reach the server, it prints a red `Connection Error:` and exits. Wrap
that — and the equivalent paths in `query`, `index`, `jobs` — to print
one extra line:

> Tip: run `agent-brain doctor` to diagnose your setup.

Implementation: a tiny helper `_print_doctor_hint(console)` in
`agent_brain_cli/client/api_client.py` or in a new
`agent_brain_cli/diagnostics.py`. Called from the `ConnectionError`
branches in
`commands/status.py`,
`commands/query.py`,
`commands/jobs.py`,
`commands/index.py`,
`commands/reset.py`.

Also: if `runtime.json` is missing and the user didn't pass `--url`,
the connection failure message should say so directly ("no
`.agent-brain/runtime.json` found — have you run `agent-brain init`
and `agent-brain start`?") instead of just "connection refused on
127.0.0.1:8000."

## Files touched (representative)

- `agent-brain-cli/agent_brain_cli/config.py` — unified resolver
- `agent-brain-cli/agent_brain_cli/commands/init.py` — delete dup
- `agent-brain-cli/agent_brain_cli/commands/start.py` — delete dup
- `agent-brain-cli/agent_brain_cli/commands/status.py` — hint on fail
- `agent-brain-cli/agent_brain_cli/commands/doctor.py` — NEW
- `agent-brain-cli/agent_brain_cli/cli.py` — register doctor
- `agent-brain-server/agent_brain_server/project_root.py` — same reorder
- `agent-brain-server/agent_brain_server/services/file_watcher_service.py` — ignore dirs
- `agent-brain-server/agent_brain_server/indexing/graph_extractors.py` — langextract API
- `agent-brain-server/agent_brain_server/config/provider_config.py` — GraphRAGConfig
- `agent-brain-server/agent_brain_server/config/settings.py` — special-tokens flag
- `agent-brain-server/agent_brain_server/storage/graph_store.py` — path resolution
- `agent-brain-server/agent_brain_server/services/indexing_service.py` — token preprocess
- `agent-brain-server/agent_brain_server/providers/embedding/cohere.py` — lazy import
- `agent-brain-server/pyproject.toml` — cohere extra
- `agent-brain-plugin/scripts/ab-setup-check.sh` — delegate to CLI when present
- `docs/PROVIDER_CONFIGURATION.md`, `docs/QUICK_START.md` — note doctor + cohere extra

## Verification

Per-issue acceptance, run from a checkout:

- **#124 / #128**: in a mono-repo fixture (`tests/fixtures/monorepo/`)
  create `projects/app/.agent-brain/` with a `runtime.json` pointing at
  port 8042; `cd projects/app && agent-brain status --json` must hit
  8042, not 8000. Add a pytest covering the resolver directly.
- **#123**: start the server on a tmpdir with `--watch auto`, write a
  file under `.agent-brain/logs/`, confirm no new job appears in
  `agent-brain jobs` after 5 s.
- **#129**: `ENABLE_GRAPH_INDEX=true poetry run pytest
  tests/unit/test_graph_extractors.py -k langextract` — and run
  `scripts/quick_start_guide.sh` with langextract installed; verify
  triplet count > 0 in `agent-brain status`'s graph_index section.
- **#126**: write `config.yaml` with `graphrag: { enabled: true,
  store_type: simple }` and *no* `ENABLE_GRAPH_INDEX` env var; start
  server; `agent-brain status -v` should show graph index enabled.
- **#122 / #125**: in a fresh venv, `pip install agent-brain-rag` must
  succeed without dragging in tokenizers; `pip install
  'agent-brain-rag[cohere]'` succeeds and the cohere provider loads.
- **#114**: index a file containing `<|endoftext|>` — with the flag off
  the chunk gets the placeholder; with the flag on the document indexes
  cleanly.
- **Doctor**: `agent-brain doctor` on a fresh checkout reports missing
  init; after `agent-brain init && agent-brain start`, doctor returns
  all green. `agent-brain doctor --json` schema matches the existing
  bash script keys (so plugin code keeps working).
- **End-to-end**: `task before-push` and
  `./scripts/quick_start_guide.sh` both pass.

Once verified, save this plan to `docs/plans/2026-05-issues-cleanup-and-doctor.md`
per the repo's planning rule, and open a PR.
