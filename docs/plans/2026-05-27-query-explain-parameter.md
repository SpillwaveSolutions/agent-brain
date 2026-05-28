# Plan — Implement Issue #159 (`explain=true` query parameter)

## Context

The repo sits at v10.0.7 with no active milestone and 13 open feature issues filed from the 2026 strategic recommendations doc. Triage (see appendix at bottom) selected issue **#159 explain=true** as the next ticket because: every score it needs is already on `QueryResult`, it has no upstream dependencies, and it makes future retrieval work (#160 GraphRAG schema, #154 agentic, #155 per-source embedding) much easier to validate.

The goal is an opt-in `explain` flag on `/query` that returns structured per-result explanations: matching terms (BM25), entity paths (graph), fusion breakdown (hybrid/multi), rerank movement, and a "why this rank" one-liner — all pure-additive, with default `explain=false` keeping the wire format byte-identical.

## Critical Design Decisions (decided)

| Decision | Choice | Reason |
|---|---|---|
| `explain` location | POST body field on `QueryRequest` | Route is `POST /` and uses Pydantic; the issue's `?explain=true` phrasing is aspirational. Matches `alpha`, `top_k`, `mode` |
| Backward-compat for `explanation=null` | Conditional serialization in router (`exclude={"explanation"} if not request.explain`) | Issue says "wire format must be unchanged"; `null` is technically a change |
| BM25 matched terms | Backend responsibility, via new `SearchResult.matched_terms` field | Tokenization differs by backend (`bm25s` stems vs Postgres `ts_headline`); naive `split()` intersection is wrong |
| Per-retriever ranks (multi) and weighted scores (hybrid) | Stashed on `QueryResult.metadata["_explain_scratch"]` before rerank, drained at end of `execute_query` | Otherwise rerank overwrites/discards them |
| Query cache interaction | Strip `explanation` on cache write so a single cache entry serves both shapes | Cheaper than dual-keying |
| `reason` string determinism | Fixed priority order (rerank > dominant fusion source > matched terms > fallback) | Otherwise snapshot tests flake |
| Graph→vector fallback | Explanation states the fallback explicitly | Don't claim a graph path that doesn't exist |

## Implementation — 5 Commits, 1 PR

Each commit is independently reviewable and self-contained. PR is opened after commit 5.

### Commit 0 — Clean feature branch
- `git checkout main && git pull && git checkout -b feat/query-explain`
- Verify clean tree.

### Commit 1 — Models + wire-format plumbing (safe ABI commit)

**Files:**
- `agent-brain-server/agent_brain_server/models/query.py` — add `ResultExplanation` model; add `explanation: ResultExplanation | None = None` to `QueryResult`; add `explain: bool = False` to `QueryRequest`. Update the OpenAPI example block (lines 109-132).
- `agent-brain-server/agent_brain_server/api/routers/query.py` — in the handler at line 20, when `not request.explain` serialize response with `exclude={"explanation"}` recursively per result so the field is *absent*, not `null`.
- `agent-brain-cli/agent_brain_cli/client/api_client.py:265-276` — forward `explain` flag in request body; parse `explanation` if present.

**Test (1):**
- `tests/contract/test_query_explain_default.py` — POST with no `explain` field, assert `"explanation"` key not present in any result.

Commit message: `feat(query): add explain field to QueryRequest/Result (refs #159)`

### Commit 2 — Service-layer reason builder, rerank movement, cache fix

**Files:**
- `agent-brain-server/agent_brain_server/services/query_service.py`:
  - In `_execute_hybrid_query` (380-505), when `request.explain`, stash `{vector_score_weighted, bm25_score_weighted, alpha, fused_score}` into result `metadata["_explain_scratch"]` before final return.
  - In `_execute_multi_query` (623-730), stash `{vector_rank, bm25_rank, graph_rank, rrf_score}` (the values computed at 668/688/703).
  - In `_execute_graph_query` (507-621), record whether the fallback-to-vector path fired (lines 565/574/617-619) into scratch.
  - In `_rerank_results` (820-915), change loop to `for new_index, (original_index, rerank_score) in enumerate(reranked):` and stash `rerank_movement = original_index - new_index`. Guard the no-rerank path (lines 870-875, 908-915) so movement is `None` there.
  - In `execute_query` (169-314), after rerank (line 293), add a final pass that drains `_explain_scratch` into a `ResultExplanation` per result and clears the scratch from metadata. Build the `reason` one-liner deterministically (priority: rerank-movement-with-context > top-of-mode > fusion-dominant > "matched query terms" > "vector similarity").
  - Update `cache_params` (203-213) — strip `explanation` from cached responses before storing so an `explain=true` cache hit can serve `explain=false` and vice versa.

**Tests (5):**
- One unit test per mode: BM25, vector, graph, hybrid, multi+rerank. Each asserts that when `explain=true`, `explanation` is populated with the mode-appropriate shape; when `explain=false`, it's `None`. Mirror the fixture pattern in `tests/unit/services/test_query_service_reranking.py:22-99` (AsyncMock for the reranker, sample results dataclasses).
- One test for the graph→vector fallback path asserting `reason` mentions the fallback.

Commit message: `feat(query): build ResultExplanation in query_service (refs #159)`

### Commit 3 — `SearchResult.matched_terms` + backend implementations

**Files:**
- `agent-brain-server/agent_brain_server/storage/protocol.py:13-25` — add `matched_terms: list[str] | None = None` to `SearchResult`. Verify `@runtime_checkable` still passes.
- `agent-brain-server/agent_brain_server/storage/chroma/backend.py` — in `keyword_search()`, when caller passes `explain=True` (new optional kwarg, default False), replicate the `bm25s` tokenizer (lowercase + Porter stem + English stopword strip) on both query and result text, intersect to produce `matched_terms`. Reuse existing tokenizer if `bm25s` exposes it directly via `bm25s.tokenize` — check the lib's public API before reimplementing.
- `agent-brain-server/agent_brain_server/storage/postgres/keyword_ops.py:122-200` — when `explain=True`, augment the SELECT with `ts_headline(...)` and parse the `<b>...</b>` markup to extract matched terms.
- Wire `explain=True` through `_execute_bm25_query`, `_execute_hybrid_query`, `_execute_multi_query` calls to `keyword_search`.

**Tests (2):**
- One unit test per backend (Chroma, Postgres) asserting that for a query like `"authentication setup"` against a doc containing both, `matched_terms` includes the stemmed/normalized hits and excludes stopwords.

**Risk note:** This is the riskiest commit (storage protocol surface). If `bm25s` tokenizer API isn't easily reachable, scope-cut: ship matched-terms for Postgres only and file a follow-up for Chroma. Document the gap in CHANGELOG.

Commit message: `feat(storage): expose matched_terms from BM25 backends (refs #159)`

### Commit 4 — CLI `--explain` rendering

**Files:**
- `agent-brain-cli/agent_brain_cli/commands/query.py:63-65` — add `--explain` click flag mirroring `--scores`.
- `agent-brain-cli/agent_brain_cli/commands/query.py:179-194` — add a sub-panel render: `reason` as the panel title, then a Rich `Table` with `matched_terms` (highlighted via `Text.highlight_words`), `fusion` breakdown if present, `graph_path` joined with `→`, and `rerank_movement` if non-null.

**Test (1):**
- Snapshot test asserting the `--explain` render block appears under each result and `--explain` absence keeps the existing output unchanged.

Commit message: `feat(cli): add --explain flag to query command (refs #159)`

### Commit 5 — Docs

**Files:**
- `docs/API_REFERENCE.md` — document the `explain` request field and `ResultExplanation` response shape.
- `docs/USER_GUIDE.md` — short section under "Querying" with a `--explain` example and sample output.
- `CHANGELOG.md` — entry under unreleased.

Commit message: `docs(query): document explain flag and ResultExplanation (refs #159)`

## Critical Files (recap)

- `agent-brain-server/agent_brain_server/models/query.py` — model additions
- `agent-brain-server/agent_brain_server/api/routers/query.py` — conditional serialization
- `agent-brain-server/agent_brain_server/services/query_service.py` — scratch + reason builder + rerank movement + cache fix
- `agent-brain-server/agent_brain_server/storage/protocol.py` — `SearchResult.matched_terms`
- `agent-brain-server/agent_brain_server/storage/chroma/backend.py` + `storage/postgres/keyword_ops.py` — backend matched-terms
- `agent-brain-cli/agent_brain_cli/commands/query.py` + `client/api_client.py` — flag + forward + render

## Reuse Notes

- `--scores` flag pattern at `query.py:63-65,179-194` is the template for `--explain`. Don't invent a new convention.
- `tests/unit/services/test_query_service_reranking.py:22-99` fixture pattern (AsyncMock + sample `QueryResult` list) is what each new unit test should mirror.
- Reranker movement: the index needed is already available — just change `for original_index, rerank_score in reranked:` at line 879 to `for new_index, (original_index, rerank_score) in enumerate(reranked):`. Don't add a parallel loop.
- `relationship_path` (already populated) is the source for `ResultExplanation.graph_path` — don't recompute.

## Verification

Mandatory per CLAUDE.md — every push must clear these:

```bash
task before-push    # MUST exit 0 — Black, Ruff, mypy strict, pytest
task pr-qa-gate     # MUST exit 0 — coverage and full lint/type
```

End-to-end manual checks:
```bash
# 1. Fresh index for verification
rm -rf /tmp/explain-verify && mkdir /tmp/explain-verify && cd /tmp/explain-verify
agent-brain init && agent-brain start
agent-brain index ~/clients/spillwave/src/agent-brain/docs

# 2. Default path — confirm wire format unchanged
agent-brain query "graph search" | jq 'first(.results[]) | keys' # no "explanation" key

# 3. Explain path — confirm structured payload
agent-brain query "graph search" --explain
# Expect: reason, matched_terms highlighted, no graph_path (BM25/vector mode)

agent-brain query "AuthManager methods" --mode graph --explain
# Expect: reason mentions graph hit, graph_path shows relationship chain

agent-brain query "auth flow" --mode hybrid --explain
# Expect: fusion table showing vector_score_weighted + bm25_score_weighted + alpha

# 4. With rerank enabled (ENABLE_RERANKING=true)
ENABLE_RERANKING=true agent-brain query "auth" --mode multi --explain
# Expect: rerank_movement shown for results that moved

# 5. Quick-start smoke
./scripts/quick_start_guide.sh
```

## Open Questions / Scope Guards

- **`bm25s` tokenizer accessibility** — if `bm25s.tokenize` isn't a stable public API, fall back to "Postgres-only matched_terms in commit 3; Chroma deferred to follow-up issue." Decide during commit 3 implementation, not now.
- **`ResultExplanation` schema versioning** — explicitly not adding a version field. If the shape changes in v11, that's a separate breaking-change conversation. The `explain` flag itself is the version gate (default false = no schema exposure).
- **Performance** — building explanations adds O(n) work per result where n is small (≤top_k). The BM25 tokenizer reuse in Chroma is the only hot spot worth measuring; if it blows past 50ms p99 on 100-result queries, cache the stemmed query tokens per request.

## PR

After all 5 commits land locally and `task before-push && task pr-qa-gate` exit 0:

```bash
gh pr create --title "feat(query): add explain=true parameter (closes #159)" \
  --body-from-stdin <<EOF
## Summary
Closes #159. Adds an opt-in `explain` flag on POST /query that returns structured per-result explanations: matched terms (BM25), entity paths (graph), fusion breakdown (hybrid/multi), rerank movement, and a deterministic "why this rank" one-liner.

When `explain=false` (default), the wire format is byte-identical to today — the `explanation` field is excluded from serialization, not `null`.

## Test plan
- [ ] task before-push && task pr-qa-gate pass
- [ ] Each mode (BM25/vector/graph/hybrid/multi+rerank) has a unit test
- [ ] Backward-compat test asserts no `explanation` key when `explain=false`
- [ ] Graph→vector fallback test asserts `reason` reflects the fallback
- [ ] CLI snapshot test for --explain render
- [ ] Manual: scripts/quick_start_guide.sh smoke
EOF
```

After PR opens, this plan file gets copied to `docs/plans/2026-05-27-query-explain-parameter.md` per repo convention (CLAUDE.md planning rule).

---

## Appendix: Why #159 over the other 12

| Tier | Issues | Why deferred |
|---|---|---|
| Decision-gated | #167 MCP, #164 Claude-native (depends on #167), #161 UDS, #162 Rust CLI | Transport strategy decision not yet made (issue #167 body explicitly says "Do not start until UDS reassessed") |
| Multi-week | #156 LiveVectorLake, #157 federated, #158 VS Code, #154 agentic, #155 per-source-type | Each is its own milestone, not a single PR |
| Medium scope | #160 GraphRAG schema, #163 batch query | Touch ingestion/migration (#160) or two surfaces (#163); good follow-ups |
| Smaller adjacent ticket | #152 Voyage embedding | Comparable size to #159 but adds an SDK dependency + extras config; #159 is purely server-internal |
| **Selected** | **#159 explain=true** | **All scores already computed; pure-additive; unlocks better debugging for every other retrieval ticket in this list** |
