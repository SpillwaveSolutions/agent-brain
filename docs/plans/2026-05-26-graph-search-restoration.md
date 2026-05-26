# Plan: Restore graph search + indexing bug fixes (v10.0.4)

## Context

Three open issues block real-world v10 use:

- **#144** — `KuzuPropertyGraphStore.__init__()` rejects the `database_path=` kwarg because `llama-index-graph-stores-kuzu>=0.9.0` changed the constructor to take a positional `kuzu.Database` object. **Graph search is completely unusable when `graphrag.enabled: true`.** This supersedes the v9 `extract_relations` blocker (#129) which was already fixed in v10.
- **#142** — `_walk_pruned` in `document_loader.py:607` rewrites `**/dir/**` to `*/dir/*` via `pat.replace("**", "*")`, then `fnmatch` matches it against the directory's own absolute path (which lacks the trailing segment). Exclude patterns load and log but silently fail to prune, so users index everything and only discover it from `Empty document` warnings.
- **#143** — When the manifest diff sees N "new" files that all chunk to zero (empty placeholders, scaffolding), `BM25Retriever.from_defaults(nodes=[])` raises `Please pass exactly one of index, nodes, or docstore.` and fails the job. v9.6.0 silently no-oped here.

These three compound: an empty `chapter13/` dir that #142 fails to prune becomes the zero-chunk diff that crashes #143, and #144 means the graph half of any successful index is unreachable anyway. Fixing all three together is the minimum to call graph search "working."

#131 is largely already done — the Explore audit confirmed 8 of 9 sub-issues are fixed in v10.0.3 (langextract migration, GraphRAG YAML, project-root resolver, file watcher loop, cohere optional, tiktoken disallowed-tokens). The only stray is a duplicate `resolve_project_root` in `agent-brain-cli/commands/stop.py` — included here as cleanup. The aspirational `agent-brain doctor` command becomes a separate follow-up ticket.

#106 is the 2026 strategic roadmap doc (ColBERTv2 reranking, Voyage 4 embeddings, native MCP, agentic GraphRAG, etc.) — too large to break into tickets in this PR; leave open as the roadmap thread.

## Goal

**Ship v10.0.4 such that:**
1. `graphrag.enabled: true` + `store_type: kuzu` produces a working indexed graph that responds to `agent-brain query --mode graph "..."` with non-empty results.
2. `exclude_patterns` of the documented `**/dir/**` shape actually prune matching directories during indexing.
3. Indexing a folder containing only empty files completes as a successful no-op, not a failed job.
4. **A new integration test (`test_kuzu_graph_e2e.py`) proves the Kuzu graph DB works end-to-end and runs as part of `task before-push`** — this is the hard gate the user set as the goal.
5. All of `task before-push`, `task pr-qa-gate`, and `scripts/quick_start_guide.sh` pass.

## Scope

**In this PR:**
- Fix #144 — Kuzu constructor migration
- Fix #142 — exclude_patterns matcher
- Fix #143 — zero-chunk indexing no-op
- Cleanup — remove duplicate `resolve_project_root` in `cli/commands/stop.py`
- Update `docs/plans/2026-05-26-graph-search-restoration.md` (this plan) per repo planning rule

**Out of scope (file as new tickets, link from PR):**
- `agent-brain doctor` CLI command (lifted from #131)
- Auto-suggest doctor on connection failures (lifted from #131)

**Out of scope (leave as-is):**
- #106 strategic roadmap — too aspirational for atomic tickets

## Branch and prep

```bash
# Stash any local cruft first (the dirty .claude/settings.local.json and
# agent-brain-cli/poetry.lock changes are unrelated)
git stash -u

# Start from clean main
git checkout main && git pull
git checkout -b fix/graph-search-restoration-v10.1
```

Verify clean: `git status` should show no changes.

## Implementation

### 1. Fix #144 — Kuzu constructor (`storage/graph_store.py`)

**File:** `agent-brain-server/agent_brain_server/storage/graph_store.py`
**Location:** `_initialize_kuzu_store()` at lines 204–223.

**Approach:** The new `KuzuPropertyGraphStore` signature is `(db: kuzu.Database, relationship_schema=None, has_structured_schema=False, sanitize_query_output=True, use_vector_index=True, embed_model=None, ...)`. We pass:

- `db = kuzu.Database(str(kuzu_db_path))` (instantiate explicitly so we control lifetime)
- `use_vector_index=False` — agent-brain uses ChromaDB for vectors; Kuzu's optional vector index is a separate path we don't need and would force `embed_model` plumbing through `GraphStoreManager`. Keep this surface area minimal; revisit if we add native Kuzu vector search later.

```python
def _initialize_kuzu_store(self) -> None:
    """Initialize Kuzu graph store with fallback to simple."""
    try:
        import kuzu
        from llama_index.graph_stores.kuzu import KuzuPropertyGraphStore

        kuzu_db_path = self.persist_dir / "kuzu_db"
        kuzu_db_path.mkdir(parents=True, exist_ok=True)

        self._kuzu_db = kuzu.Database(str(kuzu_db_path))
        self._graph_store = KuzuPropertyGraphStore(
            self._kuzu_db,
            use_vector_index=False,
        )
        logger.debug(f"Initialized KuzuPropertyGraphStore at {kuzu_db_path}")
    except ImportError as e:
        logger.warning(
            f"Kuzu not available ({e}), falling back to SimplePropertyGraphStore. "
            "Install with: pip install 'agent-brain-rag[graphrag-kuzu]'"
        )
        self.store_type = "simple"
        self._initialize_simple_store()
```

The existing `hasattr`-guarded `add_triplet` / `upsert_triplet` / `_add_triplet` fan-out at lines 433–443 is already API-tolerant, so no further code changes are needed for the build path. Persistence is auto-managed by Kuzu (existing comment at line 229).

**Tests:** Two layers, both required.

1. **Unit test** — `agent-brain-server/tests/unit/test_graph_store_kuzu.py` (skip if `kuzu`/`llama-index-graph-stores-kuzu` not installed):
   - Initializes a `GraphStoreManager(store_type="kuzu")` against `tmp_path`
   - Calls `add_triplet("Alice", "knows", "Bob")` and asserts success returns True
   - Asserts `_kuzu_db` is a `kuzu.Database` instance and `kuzu_db/` directory exists

2. **Integration test (HARD GATE per /goal)** — `agent-brain-server/tests/integration/test_kuzu_graph_e2e.py`:
   - Opens `GraphStoreManager(store_type="kuzu")` in `tmp_path`
   - Ingests triplets end-to-end via `GraphIndexManager.build_from_documents` over a tiny synthetic doc set (or directly via `add_triplet` if the index manager pulls in too much config surface)
   - Queries the graph (via `GraphIndexManager.query` or the underlying store's `get_triplets`) and **asserts non-empty results with the expected subject/predicate/object**
   - Closes (releases the `kuzu.Database`) and reopens against the same `persist_dir`, asserts triplets survive
   - Must run in CI, not be skipped. Ensure `llama-index-graph-stores-kuzu` is in the dev-dep group (or the `graphrag-kuzu` extra is installed in CI) so `task before-push` exercises it locally too.

The integration test is the user's goal — passing it = graph DB is proven to work, not just to compile.

### 2. Fix #142 — exclude_patterns matcher (`indexing/document_loader.py`)

**File:** `agent-brain-server/agent_brain_server/indexing/document_loader.py`
**Location:** `_walk_pruned` at lines 607–620; constructor at lines 328–347.

**Approach:** Replace `fnmatch + pat.replace("**", "*")` with the `pathspec` library, which speaks gitignore-style globs faithfully (including `**` for recursive matches). Reuse exists across three call sites — they all flow through `_walk_pruned`, so a single fix at the iterator level catches all of them.

**Steps:**

1. Add `pathspec = "^0.12.0"` to `[tool.poetry.dependencies]` in `agent-brain-server/pyproject.toml`. Run `poetry lock` and commit `poetry.lock`.

2. In `DocumentLoader.__init__`, compile a `PathSpec` once from `self.exclude_patterns`:

   ```python
   from pathspec import PathSpec
   from pathspec.patterns.gitwildmatch import GitWildMatchPattern

   # in __init__ after self.exclude_patterns = ...
   self._exclude_spec: PathSpec | None = (
       PathSpec.from_lines(GitWildMatchPattern, self.exclude_patterns)
       if self.exclude_patterns
       else None
   )
   ```

3. Rewrite `_walk_pruned` to match relative-to-root paths (gitignore semantics):

   ```python
   def _walk_pruned(self, root: Path) -> Iterator[Path]:
       """Pruned os.walk: skips excluded dirs before descending."""
       spec = self._exclude_spec
       root_abs = root.resolve()
       for dirpath, dirnames, filenames in os.walk(root_abs):
           dp = Path(dirpath)
           if spec is not None:
               # Prune dirs in-place to avoid descending into them
               dirnames[:] = [
                   d for d in dirnames
                   if not spec.match_file(
                       (dp / d).relative_to(root_abs).as_posix() + "/"
                   )
               ]
               # Filter files too — fnmatch path was dir-only
               for f in filenames:
                   rel = (dp / f).relative_to(root_abs).as_posix()
                   if not spec.match_file(rel):
                       yield dp / f
           else:
               for f in filenames:
                   yield dp / f
   ```

   The trailing `/` on directory names is how gitignore-style matchers distinguish dirs from files for patterns like `**/dir/`.

4. The `os.walk(str(root))` → `os.walk(root_abs)` change is intentional: pathspec's relative-path semantics require a stable base. Existing callers pass `Path` already.

5. Keep the file-extension filter at line 391 (it's a separate concern from exclude patterns).

**Tests:** Extend `agent-brain-server/tests/unit/test_document_loader.py` with a parametrized test that builds a tmp tree (`reference/research/chapter13/empty.md`, `reference/other/keep.md`) and asserts:
- Pattern `**/chapter13/**` excludes `empty.md` (the documented shape)
- Pattern `**/chapter13` (no trailing) also excludes — backward-compat with the workaround in #142
- Pattern `**/*.log` excludes file-level matches
- Default patterns continue to exclude `__pycache__`, `.git`, `node_modules`, `.agent-brain`

### 3. Fix #143 — zero-chunk no-op (`services/indexing_service.py`)

**File:** `agent-brain-server/agent_brain_server/services/indexing_service.py`
**Location:** Just after `Created N total chunks` log (around line 564), before any embedding / vector / BM25 work.

**Approach:** Short-circuit when the chunk list is empty. The chunk_eviction step has already evicted stale chunks (its own work is correct); we just need to skip the build-the-world steps and mark the job done.

```python
chunks = all_chunks
self._state.total_chunks = len(chunks)
logger.info(f"Created {len(chunks)} total chunks")

if not chunks:
    logger.info(
        f"Indexing job {job_id}: zero-chunk diff (all new docs produced no chunks); "
        "skipping embedding/vector/BM25 build"
    )
    # Save manifest so we don't re-process these empty docs next run
    if self._state.manifest_to_save:
        self.chunk_eviction_service.save_manifest(
            folder_path, self._state.manifest_to_save
        )
    return  # let the existing job-completion path in the worker mark success
```

The exact `manifest_to_save` plumbing depends on what's already stored on `self._state` at that point — the implementer should verify the variable name during execution and align with how the success path on line ~660 does it. The principle: don't lose the manifest write; just skip the chunk-dependent steps.

**Tests:** Add `agent-brain-server/tests/integration/test_zero_chunk_indexing.py`:
- Create tmp folder with one zero-byte `.md` file
- Run indexing through `IndexingService`
- Assert job status is `completed`, not `failed`
- Assert `created_chunks == 0`, `docs_indexed == 1`
- Assert manifest persisted (so next run sees the file as unchanged)

### 4. Cleanup — remove duplicate resolver (`cli/commands/stop.py`)

**File:** `agent-brain-cli/agent_brain_cli/commands/stop.py` lines 26–55.

The Explore audit found that `stop.py` carries a stale copy of `resolve_project_root` that still does git-first resolution. `start.py` already imports the corrected version from `agent_brain_cli.config`. Make `stop.py` match.

```python
# Replace the in-file _resolve_project_root with:
from agent_brain_cli.config import resolve_project_root
```

Update any callers in the file to use the imported name. Run `task before-push` in the CLI package to catch any signature mismatches.

## Tickets to file before merge

Both lifted from the unfinished portion of #131, marked clearly as follow-ups and linked from this PR:

1. **"Add `agent-brain doctor` command for setup diagnosis"**
   Body: short summary of what it should check (Python version, project root resolution, config files, API keys for active provider, server reachability, GraphRAG/Cohere extras present if enabled, `.gitignore` entry). Mention it consolidates `agent-brain-plugin/scripts/ab-setup-check.sh`. Reference #131.

2. **"Auto-suggest `agent-brain doctor` on connection failures"**
   Body: small UX improvement — when `agent-brain status/query/index/jobs/reset` hits a `ConnectionError`, print one extra line `Tip: run \`agent-brain doctor\` to diagnose your setup.` If `runtime.json` is missing, surface that explicitly instead of just "connection refused on 127.0.0.1:8000." Reference #131.

## Comments to add to existing tickets

Use `gh issue comment <num> -F -` with a heredoc so the body is clean.

- **#142**: Comment that we're picking the `pathspec` migration (option 2 in the issue), not the doc-only workaround, because operator intuition expects gitignore semantics and the doc-only fix would leave the next operator who reaches for `**/dir/**` to trip the same wire.
- **#143**: Comment that we're adding the zero-chunk short-circuit before BM25 build and preserving manifest persistence so the empty files won't re-trigger on the next run.
- **#144**: Comment that we're passing `use_vector_index=False` deliberately (agent-brain uses ChromaDB for vectors; Kuzu vector index would require embed_model plumbing through the manager — out of scope).
- **#131**: After PR is open, comment with the verification table (8 of 9 sub-issues confirmed fixed in v10.0.3 with file:line evidence, the `stop.py` duplicate cleanup is in this PR, and the doctor command + auto-hint are in two new tracking issues). Close #131 once the PR merges.

## PR

Title: `fix: restore graph search with Kuzu, fix exclude patterns and zero-chunk indexing (v10.0.4)`

Body includes:

```
## Summary

- Fixes #144 — KuzuPropertyGraphStore constructor migrated to llama-index-graph-stores-kuzu >= 0.9.0 API
- Fixes #142 — exclude_patterns now use pathspec for faithful gitignore-style globs (**/dir/** works)
- Fixes #143 — zero-chunk indexing diff no longer fails the job; completes as no-op
- Refs #131 — removes duplicate resolve_project_root in cli/commands/stop.py; remaining items tracked in #<new-doctor-ticket> and #<new-hint-ticket>

## Test plan

- [ ] task before-push passes
- [ ] task pr-qa-gate passes
- [ ] scripts/quick_start_guide.sh passes
- [ ] New unit test test_graph_store_kuzu.py exercises the new constructor
- [ ] New unit tests in test_document_loader.py cover **/dir/**, **/dir, and file-level patterns
- [ ] New integration test_zero_chunk_indexing.py covers the no-op path
- [ ] Manual graph search smoke test: index a small project with graphrag.enabled: true, run a graph-mode query, see non-empty result
```

## Verification

Before push (MANDATORY per CLAUDE.md):

```bash
task before-push       # must exit 0
task pr-qa-gate        # must exit 0
```

End-to-end smoke for graph search (manual, before PR is marked ready):

```bash
# Fresh state dir
rm -rf .agent-brain-test
AGENT_BRAIN_STATE_DIR=.agent-brain-test agent-brain init
# Enable graphrag in .agent-brain-test/config.yaml: graphrag.enabled: true, store_type: kuzu
AGENT_BRAIN_STATE_DIR=.agent-brain-test agent-brain start
AGENT_BRAIN_STATE_DIR=.agent-brain-test agent-brain index docs/ --include-code --force
# Wait for job to finish via agent-brain jobs
AGENT_BRAIN_STATE_DIR=.agent-brain-test agent-brain query "what is agent brain" --mode graph
# Expect: non-empty result with relationships visible
AGENT_BRAIN_STATE_DIR=.agent-brain-test agent-brain stop
```

E2E pass + the graph-mode query returning non-empty results = the goal is met.

## Release

Out of scope for the PR. After merge to main, run the `/ag-brain-release` skill with the bump set to **patch** (10.0.3 → 10.0.4) — three bug fixes, no API changes. The CHANGELOG entry should call out clearly that graph search with Kuzu now works, since users tracking patch bumps may otherwise not notice the regression was fixed. Defer the final call to the release skill — it has its own checklist.

## Files touched (representative)

- `agent-brain-server/agent_brain_server/storage/graph_store.py` — Kuzu constructor
- `agent-brain-server/agent_brain_server/indexing/document_loader.py` — pathspec migration
- `agent-brain-server/agent_brain_server/services/indexing_service.py` — zero-chunk short-circuit
- `agent-brain-server/pyproject.toml` + `poetry.lock` — add pathspec
- `agent-brain-server/tests/unit/test_graph_store_kuzu.py` (NEW)
- `agent-brain-server/tests/unit/test_document_loader.py` — extend
- `agent-brain-server/tests/integration/test_zero_chunk_indexing.py` (NEW)
- `agent-brain-cli/agent_brain_cli/commands/stop.py` — use shared resolver
- `docs/plans/2026-05-26-graph-search-restoration.md` — copy of this plan, per repo planning rule
